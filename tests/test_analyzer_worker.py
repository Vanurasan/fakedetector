"""Spawn lifecycle, timeout escalation, and reap tests for analyzer workers."""

from __future__ import annotations

import json
import multiprocessing
import time
from collections.abc import Callable
from dataclasses import replace
from multiprocessing.process import BaseProcess
from pathlib import Path

import pytest

from fakedetector.analyzers._catalog import _resolve_worker_definition
from fakedetector.analyzers._errors import AnalyzerInfrastructureError
from fakedetector.analyzers._models import (
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._orchestrator import _with_duration
from fakedetector.analyzers._transport import (
    _MAX_RESPONSE_BYTES,
    _MAX_STAGE5_ANALYZER_RESULT_BYTES,
    _serialize_stage5_analyzer_result,
    _Stage5AnalyzerResultSizeError,
    _WorkerRequest,
    _WorkerResponseKind,
)
from fakedetector.analyzers._worker import (
    _encode_response,
    _execute_worker,
    _MultiprocessingSpawnBackend,
    _SpawnedWorkerRunner,
    _validate_completed_result,
    _worker_main,
    _WorkerReapBarrier,
    _WorkerRunKind,
)
from fakedetector.core._cleanup_safety import _CleanupSafetyInterruption
from fakedetector.domain import (
    AnalyzerResult,
    AnalyzerStatus,
    ImageTechnicalParameters,
    MediaType,
    ValidatedFileDescriptor,
)


class _FakeConnection:
    def __init__(self, *, poll_result: bool = False, response: bytes = b"") -> None:
        self.poll_result = poll_result
        self.response = response
        self.closed = False
        self.poll_timeouts: list[float] = []
        self.sent: list[bytes] = []

    def poll(self, timeout: float = 0.0) -> bool:
        self.poll_timeouts.append(timeout)
        return self.poll_result

    def recv_bytes(self, maxlength: int | None = None) -> bytes:
        assert maxlength is not None
        return self.response

    def send_bytes(
        self,
        buf: bytes,
        offset: int = 0,
        size: int | None = None,
    ) -> None:
        self.sent.append(buf[offset:] if size is None else buf[offset : offset + size])

    def close(self) -> None:
        self.closed = True


class _FakeProcess:
    def __init__(
        self,
        *,
        terminate_stops: bool,
        kill_stops: bool,
        join_stops: bool = False,
    ) -> None:
        self.alive = True
        self.terminate_stops = terminate_stops
        self.kill_stops = kill_stops
        self.join_stops = join_stops
        self.started = False
        self.terminated = False
        self.killed = False
        self.closed = False
        self.join_timeouts: list[float | None] = []

    @property
    def exitcode(self) -> int | None:
        return None if self.alive else 0

    def start(self) -> None:
        self.started = True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)
        if self.join_stops:
            self.alive = False

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated = True
        if self.terminate_stops:
            self.alive = False

    def kill(self) -> None:
        self.killed = True
        if self.kill_stops:
            self.alive = False

    def close(self) -> None:
        self.closed = True


class _JoinFailureProcess(_FakeProcess):
    def __init__(self) -> None:
        super().__init__(terminate_stops=False, kill_stops=False)
        self.alive = False
        self.join_fails = True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)
        if self.join_fails:
            raise OSError("PRIVATE join detail")


class _FakeBackend:
    def __init__(self, process: _FakeProcess) -> None:
        self.process = process
        self.receive = _FakeConnection()
        self.send = _FakeConnection()
        self.process_creations = 0

    def create_pipe(self) -> tuple[_FakeConnection, _FakeConnection]:
        return self.receive, self.send

    def create_process(
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
    ) -> _FakeProcess:
        assert callable(target)
        assert len(args) == 2
        self.process_creations += 1
        return self.process


class _BrokenProcessCreationBackend(_FakeBackend):
    def create_process(
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
    ) -> _FakeProcess:
        del target, args
        raise OSError


def _descriptor() -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name="source.png",
        extension="png",
        declared_mime_type=None,
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=6,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=ImageTechnicalParameters(
            width=1,
            height=1,
            format="PNG",
            color_mode="RGB",
            has_metadata=False,
        ),
    )


def _result_with_summary(
    summary: str,
    *,
    duration_ms: int = 0,
    raw_metrics: dict[str, object] | None = None,
    candidate_findings: list[object] | None = None,
) -> AnalyzerResult:
    return AnalyzerResult(
        analyzer_id="fake_image_analyzer",
        analyzer_version="1.0.0",
        media_type=MediaType.IMAGE,
        group="framework_test",
        status=AnalyzerStatus.COMPLETED,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=duration_ms,
        score=0.42,
        score_name="contract_signal",
        summary=summary,
        raw_metrics=raw_metrics or {},
        candidate_findings=candidate_findings or [],
        warnings=[],
        errors=[],
    )


def _result_at_stage5_size(
    size_bytes: int,
    *,
    summary_suffix: str = "",
    duration_ms: int = 0,
    raw_metrics: dict[str, object] | None = None,
    candidate_findings: list[object] | None = None,
) -> AnalyzerResult:
    base = _result_with_summary(
        summary_suffix,
        duration_ms=duration_ms,
        raw_metrics=raw_metrics,
        candidate_findings=candidate_findings,
    )
    remaining = size_bytes - len(_serialize_stage5_analyzer_result(base))
    assert remaining >= 0
    return base.model_copy(update={"summary": "x" * remaining + summary_suffix})


def _request(
    tmp_path: Path,
    worker_key: str = "framework_test.hang",
    *,
    applicable: bool = True,
) -> _WorkerRequest:
    source = tmp_path / "source.bin"
    source.write_bytes(b"source")
    definition = _resolve_worker_definition(worker_key)
    assert definition is not None
    settings = definition.settings_model.model_validate({"applicable": applicable})
    return _WorkerRequest(
        worker_key=worker_key,
        analysis_id="a" * 32,
        media_type=MediaType.IMAGE.value,
        file_facts_json=_AnalyzerFileFacts.from_validated_file(_descriptor()).model_dump_json(),
        source_path=str(source.resolve()),
        artifacts=(),
        metadata_json="{}",
        warnings=(),
        settings_json=settings.model_dump_json(),
        timeout_seconds=0.05,
    )


def test_timeout_terminate_path_is_bounded_reaped_and_closes_resources(
    tmp_path: Path,
) -> None:
    process = _FakeProcess(terminate_stops=True, kill_stops=True)
    backend = _FakeBackend(process)
    runner = _SpawnedWorkerRunner(backend=backend, monotonic=lambda: 0.0)

    outcome = runner.run(_request(tmp_path), 0.05)

    assert outcome.kind is _WorkerRunKind.TIMEOUT
    assert process.started and process.terminated
    assert not process.killed
    assert not process.alive
    assert process.closed
    assert backend.receive.closed and backend.send.closed
    assert all(timeout is not None for timeout in process.join_timeouts)
    assert max(timeout for timeout in process.join_timeouts if timeout is not None) <= 0.2


def test_process_creation_failure_closes_both_ipc_endpoints(tmp_path: Path) -> None:
    process = _FakeProcess(terminate_stops=True, kill_stops=True)
    backend = _BrokenProcessCreationBackend(process)
    runner = _SpawnedWorkerRunner(backend=backend)

    try:
        runner.run(_request(tmp_path), 0.05)
    except AnalyzerInfrastructureError as error:
        assert error.phase == "spawn_setup"
    else:
        raise AssertionError("process creation failure was not reported")

    assert backend.receive.closed and backend.send.closed
    assert not process.started


def test_timeout_uses_kill_fallback_and_confirms_reap(tmp_path: Path) -> None:
    process = _FakeProcess(terminate_stops=False, kill_stops=True)
    backend = _FakeBackend(process)
    runner = _SpawnedWorkerRunner(backend=backend, monotonic=lambda: 0.0)

    outcome = runner.run(_request(tmp_path), 0.05)

    assert outcome.kind is _WorkerRunKind.TIMEOUT
    assert process.terminated and process.killed
    assert not process.alive
    assert process.closed
    assert backend.receive.closed and backend.send.closed
    assert all(timeout is not None for timeout in process.join_timeouts)


def test_unreapable_worker_is_fatal_and_never_timeout(tmp_path: Path) -> None:
    process = _FakeProcess(terminate_stops=False, kill_stops=False)
    backend = _FakeBackend(process)
    runner = _SpawnedWorkerRunner(backend=backend, monotonic=lambda: 0.0)

    barrier = None
    try:
        runner.run(_request(tmp_path), 0.05)
    except AnalyzerInfrastructureError as error:
        assert error.phase == "worker_reap"
        barrier = error._cleanup_safety_barrier
    else:
        raise AssertionError("unreapable worker was incorrectly returned as timeout")

    assert barrier is not None
    assert process.terminated and process.killed
    assert process.alive
    assert not process.closed
    assert backend.receive.closed and backend.send.closed
    assert all(timeout is not None for timeout in process.join_timeouts)
    assert barrier.try_confirm_safe() is False
    process.alive = False
    assert barrier.try_confirm_safe() is True
    assert barrier.try_confirm_safe() is True
    assert process.closed
    assert max(timeout for timeout in process.join_timeouts if timeout is not None) <= 0.2


def test_stopped_worker_with_unconfirmed_join_defers_cleanup_safety(
    tmp_path: Path,
) -> None:
    process = _JoinFailureProcess()
    backend = _FakeBackend(process)
    runner = _SpawnedWorkerRunner(backend=backend, monotonic=lambda: 0.0)

    try:
        runner.run(_request(tmp_path), 0.05)
    except AnalyzerInfrastructureError as error:
        assert error.phase == "worker_reap"
        barrier = error._cleanup_safety_barrier
    else:
        raise AssertionError("unconfirmed worker join was not retained")

    assert barrier is not None
    assert barrier.try_confirm_safe() is False
    assert not process.closed
    process.join_fails = False
    assert barrier.try_confirm_safe() is True
    assert process.closed


def test_repeated_real_timeouts_leave_no_spawned_children(tmp_path: Path) -> None:
    baseline_pids = {child.pid for child in multiprocessing.active_children()}
    request = _request(tmp_path)
    runner = _SpawnedWorkerRunner()
    started_at = time.monotonic()

    outcomes = [runner.run(request, 0.05) for _ in range(2)]

    elapsed = time.monotonic() - started_at
    assert [outcome.kind for outcome in outcomes] == [
        _WorkerRunKind.TIMEOUT,
        _WorkerRunKind.TIMEOUT,
    ]
    assert elapsed < 5.0
    assert {child.pid for child in multiprocessing.active_children()} == baseline_pids


def test_runner_reaps_normal_response_and_closes_all_handles(tmp_path: Path) -> None:
    process = _FakeProcess(
        terminate_stops=True,
        kill_stops=True,
        join_stops=True,
    )
    backend = _FakeBackend(process)
    backend.receive.poll_result = True
    backend.receive.response = b'{"kind":"worker_error"}'
    runner = _SpawnedWorkerRunner(backend=backend, monotonic=lambda: 0.0)

    outcome = runner.run(_request(tmp_path), 0.05)

    assert outcome.kind is _WorkerRunKind.RESPONSE
    assert outcome.response == b'{"kind":"worker_error"}'
    assert process.closed
    assert not process.terminated and not process.killed
    assert backend.receive.closed and backend.send.closed
    assert all(timeout is not None for timeout in process.join_timeouts)


def test_worker_response_kinds_distinguish_framework_outcomes(tmp_path: Path) -> None:
    completed = _execute_worker(_request(tmp_path, "framework_test.image"))
    not_applicable = _execute_worker(_request(tmp_path, "framework_test.image", applicable=False))
    analyzer_error = _execute_worker(_request(tmp_path, "framework_test.error"))
    serialization_error = _execute_worker(_request(tmp_path, "framework_test.serialization"))
    unknown_worker = _execute_worker(
        replace(_request(tmp_path, "framework_test.image"), worker_key="not_trusted")
    )

    assert _decoded(completed)["result"]["status"] == "completed"
    assert _decoded(not_applicable)["result"]["status"] == "not_applicable"
    assert _decoded(analyzer_error) == {"kind": "analyzer_error"}
    assert _decoded(serialization_error) == {"kind": "serialization_error"}
    assert _decoded(unknown_worker) == {"kind": "worker_error"}


def test_worker_rejects_invalid_transport_settings_without_details(tmp_path: Path) -> None:
    request = replace(
        _request(tmp_path, "framework_test.image"),
        settings_json='{"applicable":"secret-invalid-value"}',
    )

    response = _execute_worker(request)

    assert _decoded(response) == {"kind": "worker_error"}
    assert b"secret-invalid-value" not in response


def test_generic_worker_validation_accepts_contractual_score_and_findings(
    tmp_path: Path,
) -> None:
    transport_request = _request(tmp_path, "framework_test.image")
    definition = _resolve_worker_definition(transport_request.worker_key)
    assert definition is not None
    analyzer = definition.factory()
    request = AnalyzerRequest(
        analysis_id=transport_request.analysis_id,
        media_type=MediaType.IMAGE,
        file_facts=_AnalyzerFileFacts.from_validated_file(_descriptor()),
        source=_ReadOnlyAnalyzerInput(Path(transport_request.source_path)),
        settings=definition.settings_model.model_validate_json(transport_request.settings_json),
        timeout_seconds=transport_request.timeout_seconds,
    )
    result = AnalyzerResult(
        analyzer_id=analyzer.analyzer_id,
        analyzer_version=analyzer.analyzer_version,
        media_type=request.media_type,
        group=analyzer.group,
        status=AnalyzerStatus.COMPLETED,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=0,
        score=0.42,
        score_name="contract_signal",
        summary="Contract probe completed.",
        raw_metrics={},
        candidate_findings=[{"type": "contract_probe", "confidence": 0.42}],
        warnings=[],
        errors=[],
    )

    _validate_completed_result(result, analyzer, request)


def test_worker_input_read_failure_is_a_safe_worker_error(tmp_path: Path) -> None:
    request = _request(tmp_path, "framework_test.image")
    Path(request.source_path).unlink()

    response = _execute_worker(request)

    assert _decoded(response) == {"kind": "worker_error"}
    assert str(tmp_path).encode() not in response
    assert b"OSError" not in response
    assert b"No such file" not in response


def test_worker_main_converts_unexpected_internal_failure_to_bounded_response() -> None:
    connection = _FakeConnection()

    _worker_main(connection, object())

    assert connection.closed
    assert [_decoded(response) for response in connection.sent] == [{"kind": "worker_error"}]


def test_stage5_result_exact_payload_and_final_envelope_bound() -> None:
    result = _result_at_stage5_size(_MAX_STAGE5_ANALYZER_RESULT_BYTES)

    result_payload = _serialize_stage5_analyzer_result(result)
    response = _encode_response(_WorkerResponseKind.RESULT, result=result)

    assert len(result_payload) == _MAX_STAGE5_ANALYZER_RESULT_BYTES == 65_509
    assert len(response) == _MAX_RESPONSE_BYTES == 65_536
    assert _decoded(response)["result"] == json.loads(result_payload)


def test_stage5_result_payload_limit_plus_one_is_rejected() -> None:
    exact = _result_at_stage5_size(_MAX_STAGE5_ANALYZER_RESULT_BYTES)
    oversized = exact.model_copy(update={"summary": exact.summary + "x"})

    with pytest.raises(_Stage5AnalyzerResultSizeError):
        _serialize_stage5_analyzer_result(oversized)


def test_stage5_result_bound_counts_multibyte_utf8_and_nested_fields() -> None:
    result = _result_at_stage5_size(
        _MAX_STAGE5_ANALYZER_RESULT_BYTES,
        summary_suffix="Ж",
        raw_metrics={"nested": {"values": [1, 2, {"signal": 0.42}]}},
        candidate_findings=[{"type": "contract_probe", "confidence": 0.42}],
    )

    payload = _serialize_stage5_analyzer_result(result)

    assert len(payload) == _MAX_STAGE5_ANALYZER_RESULT_BYTES
    assert b"\\u0416" not in payload
    assert json.loads(payload)["candidate_findings"] == result.candidate_findings


def test_stage5_result_bound_is_checked_after_framework_duration_normalization() -> None:
    target = _result_at_stage5_size(
        _MAX_STAGE5_ANALYZER_RESULT_BYTES,
        duration_ms=123_456,
    )
    worker_result = target.model_copy(update={"duration_ms": 0})

    normalized = _with_duration(worker_result, 123_456)

    assert len(_serialize_stage5_analyzer_result(normalized)) == (_MAX_STAGE5_ANALYZER_RESULT_BYTES)


def test_response_encoder_rejects_oversized_canonical_result_without_fallback() -> None:
    result = _result_with_summary("x" * 70_000)

    with pytest.raises(_Stage5AnalyzerResultSizeError):
        _encode_response(_WorkerResponseKind.RESULT, result=result)


def test_runner_uses_explicit_spawn_context() -> None:
    runner = _SpawnedWorkerRunner()

    assert isinstance(runner._backend, _MultiprocessingSpawnBackend)
    assert runner._backend._context.get_start_method() == "spawn"


@pytest.mark.parametrize(
    "phase", ["start", "send_close", "poll", "recv", "join", "deadline", "process_close"]
)
def test_real_worker_interruption_reaps_before_propagation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_worker_processes,
    process_interruption: BaseException,
    phase: str,
) -> None:
    backend = _MultiprocessingSpawnBackend()
    receive, send = backend.create_pipe()
    monkeypatch.setattr(backend, "create_pipe", lambda: (receive, send))
    injected = False

    def interrupt(*_args, **_kwargs):
        nonlocal injected
        assert len(real_worker_processes) == 1
        assert real_worker_processes[0].is_alive()
        injected = True
        raise process_interruption

    monotonic = time.monotonic
    if phase == "start":
        start_process = BaseProcess.start

        def interrupted_start(process):
            start_process(process)
            interrupt()

        monkeypatch.setattr(BaseProcess, "start", interrupted_start)
    elif phase == "process_close":
        close_process = BaseProcess.close

        def interrupted_close(process):
            nonlocal injected
            close_process(process)
            injected = True
            raise process_interruption

        monkeypatch.setattr(BaseProcess, "close", interrupted_close)
        monkeypatch.setattr(receive, "poll", lambda *_args: False)
    elif phase == "deadline":

        def monotonic():
            return interrupt() if real_worker_processes else 0.0

    elif phase == "send_close":
        close = send.close

        def interrupt_close():
            monkeypatch.setattr(send, "close", close)
            interrupt()

        monkeypatch.setattr(send, "close", interrupt_close)
    elif phase == "poll":
        monkeypatch.setattr(receive, "poll", interrupt)
    else:
        monkeypatch.setattr(receive, "poll", lambda *_args: True)
        if phase == "recv":
            monkeypatch.setattr(receive, "recv_bytes", interrupt)
        else:

            def response_before_interrupted_join(*_args):
                process = real_worker_processes[0]
                join = process.join

                def interrupt_join(*args, **kwargs):
                    monkeypatch.setattr(process, "join", join)
                    interrupt(*args, **kwargs)

                monkeypatch.setattr(process, "join", interrupt_join)
                return b'{"kind":"worker_error"}'

            monkeypatch.setattr(receive, "recv_bytes", response_before_interrupted_join)

    with pytest.raises(type(process_interruption)) as raised:
        _SpawnedWorkerRunner(backend=backend, monotonic=monotonic).run(_request(tmp_path), 5.0)

    assert raised.value is process_interruption
    assert injected
    # The fixture's close hook also verifies a real zero-time join and exitcode.
    assert real_worker_processes[0]._closed
    assert receive.closed and send.closed


def test_real_worker_interrupted_escalation_preserves_barrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_worker_processes,
    process_interruption: BaseException,
) -> None:
    backend = _MultiprocessingSpawnBackend()
    receive, send = backend.create_pipe()
    monkeypatch.setattr(backend, "create_pipe", lambda: (receive, send))

    def timeout_with_interrupted_termination(*_args):
        child = real_worker_processes[0]
        terminate = child.terminate

        def interrupt_once():
            monkeypatch.setattr(child, "terminate", terminate)
            assert child.is_alive()
            raise process_interruption

        monkeypatch.setattr(child, "terminate", interrupt_once)
        return False

    monkeypatch.setattr(receive, "poll", timeout_with_interrupted_termination)
    with pytest.raises(_CleanupSafetyInterruption) as raised:
        _SpawnedWorkerRunner(backend=backend).run(_request(tmp_path), 5.0)

    assert raised.value.interruption is process_interruption
    barrier = raised.value._cleanup_safety_barrier
    assert isinstance(barrier, _WorkerReapBarrier)
    assert real_worker_processes[0].is_alive()
    assert receive.closed and send.closed
    assert barrier.try_confirm_safe() is True
    assert barrier.try_confirm_safe() is True
    assert real_worker_processes[0]._closed


def _decoded(response: bytes) -> dict[str, object]:
    decoded = json.loads(response)
    assert isinstance(decoded, dict)
    return decoded
