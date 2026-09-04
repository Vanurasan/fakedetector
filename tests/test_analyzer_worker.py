"""Spawn lifecycle, timeout escalation, and reap tests for analyzer workers."""

from __future__ import annotations

import json
import multiprocessing
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from fakedetector.analyzers._catalog import _resolve_worker_definition
from fakedetector.analyzers._errors import AnalyzerInfrastructureError
from fakedetector.analyzers._models import AnalyzerRequest, _ReadOnlyAnalyzerInput
from fakedetector.analyzers._transport import (
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
    _WorkerRunKind,
)
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
        validated_file_json=_descriptor().model_dump_json(),
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
        validated_file=_descriptor(),
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


def test_oversized_worker_result_uses_bounded_serialization_failure_envelope() -> None:
    response = _encode_response(
        _WorkerResponseKind.RESULT,
        result={"oversized": "x" * 70_000},
    )

    assert response == b'{"kind":"serialization_error"}'


def test_runner_uses_explicit_spawn_context() -> None:
    runner = _SpawnedWorkerRunner()

    assert isinstance(runner._backend, _MultiprocessingSpawnBackend)
    assert runner._backend._context.get_start_method() == "spawn"


def _decoded(response: bytes) -> dict[str, object]:
    decoded = json.loads(response)
    assert isinstance(decoded, dict)
    return decoded
