"""Spawned analyzer worker, bounded IPC, and confirmed timeout reaping."""

from __future__ import annotations

import json
import math
import multiprocessing
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Protocol, cast

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.analyzers._catalog import (
    _resolve_worker_definition,
    _WorkerAnalyzerDefinition,
)
from fakedetector.analyzers._errors import (
    AnalyzerInfrastructureError,
    _AnalyzerInputReadError,
)
from fakedetector.analyzers._models import (
    Analyzer,
    AnalyzerArtifactInput,
    AnalyzerRequest,
    ApplicabilityResult,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._transport import (
    _MAX_RESPONSE_BYTES,
    _WorkerRequest,
    _WorkerResponseKind,
)
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, MediaType, ValidatedFileDescriptor

_TERMINATE_JOIN_SECONDS = 0.2
_KILL_JOIN_SECONDS = 0.2


class _Connection(Protocol):
    def poll(self, timeout: float = ...) -> bool: ...

    def recv_bytes(self, maxlength: int | None = ...) -> bytes: ...

    def send_bytes(
        self,
        buf: bytes,
        offset: int = ...,
        size: int | None = ...,
    ) -> None: ...

    def close(self) -> None: ...


class _WorkerProcess(Protocol):
    @property
    def exitcode(self) -> int | None: ...

    def start(self) -> None: ...

    def join(self, timeout: float | None = ...) -> None: ...

    def is_alive(self) -> bool: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def close(self) -> None: ...


class _SpawnBackend(Protocol):
    def create_pipe(self) -> tuple[_Connection, _Connection]: ...

    def create_process(
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
    ) -> _WorkerProcess: ...


class _MultiprocessingSpawnBackend:
    """Small adapter fixing multiprocessing to the cross-platform spawn context."""

    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")

    def create_pipe(self) -> tuple[_Connection, _Connection]:
        return cast(tuple[_Connection, _Connection], self._context.Pipe(duplex=False))

    def create_process(
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
    ) -> _WorkerProcess:
        return cast(
            _WorkerProcess,
            self._context.Process(target=target, args=args, daemon=False),
        )


class _WorkerRunKind(Enum):
    RESPONSE = auto()
    TIMEOUT = auto()


@dataclass(frozen=True, slots=True)
class _WorkerRun:
    kind: _WorkerRunKind
    duration_ms: int
    response: bytes | None = None


class _SpawnedWorkerRunner:
    """Run exactly one request in a fresh explicit-spawn child process."""

    def __init__(
        self,
        *,
        backend: _SpawnBackend | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._backend = backend or _MultiprocessingSpawnBackend()
        self._monotonic = monotonic

    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        """Return only after normal reap or a confirmed terminate/kill timeout path."""
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise AnalyzerInfrastructureError("worker_timeout")
        started_at = self._monotonic()
        try:
            receive_connection, send_connection = self._backend.create_pipe()
        except (OSError, RuntimeError, TypeError, ValueError):
            raise AnalyzerInfrastructureError("spawn_setup") from None
        try:
            process = self._backend.create_process(
                target=_worker_main,
                args=(send_connection, request),
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            _close_connection(receive_connection)
            _close_connection(send_connection)
            raise AnalyzerInfrastructureError("spawn_setup") from None

        process_started = False
        send_connection_open = True
        try:
            try:
                process.start()
                process_started = True
            except (OSError, RuntimeError, TypeError, ValueError):
                raise AnalyzerInfrastructureError("spawn_start") from None
            finally:
                if process_started:
                    _close_connection(send_connection)
                    send_connection_open = False

            deadline = started_at + timeout_seconds
            try:
                response_ready = receive_connection.poll(max(0.0, deadline - self._monotonic()))
            except (OSError, EOFError, ValueError):
                self._stop_and_reap(process)
                raise AnalyzerInfrastructureError("worker_ipc") from None

            if not response_ready:
                if not self._is_alive(process):
                    self._bounded_join(process, 0.0)
                    raise AnalyzerInfrastructureError("worker_no_response")
                self._stop_and_reap(process)
                return _WorkerRun(
                    kind=_WorkerRunKind.TIMEOUT,
                    duration_ms=_duration_ms(started_at, self._monotonic()),
                )

            try:
                response = receive_connection.recv_bytes(_MAX_RESPONSE_BYTES)
            except (OSError, EOFError, ValueError):
                self._stop_and_reap(process)
                raise AnalyzerInfrastructureError("worker_response") from None

            try:
                self._bounded_join(process, max(0.0, deadline - self._monotonic()))
            except AnalyzerInfrastructureError:
                self._stop_and_reap(process)
                raise
            if self._is_alive(process):
                self._stop_and_reap(process)
                return _WorkerRun(
                    kind=_WorkerRunKind.TIMEOUT,
                    duration_ms=_duration_ms(started_at, self._monotonic()),
                )
            self._bounded_join(process, 0.0)
            if process.exitcode != 0:
                raise AnalyzerInfrastructureError("worker_exit")
            return _WorkerRun(
                kind=_WorkerRunKind.RESPONSE,
                duration_ms=_duration_ms(started_at, self._monotonic()),
                response=response,
            )
        finally:
            _close_connection(receive_connection)
            if send_connection_open:
                _close_connection(send_connection)
            if not process_started or _known_stopped(process):
                with suppress(OSError, ValueError):
                    process.close()

    def _stop_and_reap(self, process: _WorkerProcess) -> None:
        if not self._is_alive(process):
            self._bounded_join(process, 0.0)
            return

        with suppress(OSError, RuntimeError, ValueError):
            process.terminate()
        self._bounded_join(process, _TERMINATE_JOIN_SECONDS, tolerate_failure=True)
        if not self._is_alive(process):
            self._bounded_join(process, 0.0)
            return

        with suppress(OSError, RuntimeError, ValueError):
            process.kill()
        self._bounded_join(process, _KILL_JOIN_SECONDS, tolerate_failure=True)
        if self._is_alive(process):
            raise AnalyzerInfrastructureError("worker_reap")
        self._bounded_join(process, 0.0)

    @staticmethod
    def _bounded_join(
        process: _WorkerProcess,
        timeout: float,
        *,
        tolerate_failure: bool = False,
    ) -> None:
        try:
            process.join(max(0.0, timeout))
        except (OSError, RuntimeError, ValueError):
            if not tolerate_failure:
                raise AnalyzerInfrastructureError("worker_join") from None

    @staticmethod
    def _is_alive(process: _WorkerProcess) -> bool:
        try:
            return process.is_alive()
        except (OSError, RuntimeError, ValueError):
            raise AnalyzerInfrastructureError("worker_state") from None


def _worker_main(send_connection: _Connection, request: _WorkerRequest) -> None:
    """Resolve trusted code in the child and return one bounded JSON envelope."""
    try:
        response = _execute_worker(request)
    except Exception:
        response = _encode_response(_WorkerResponseKind.WORKER_ERROR)
    try:
        send_connection.send_bytes(response)
    except (OSError, ValueError):
        pass
    finally:
        _close_connection(send_connection)


def _execute_worker(request: _WorkerRequest) -> bytes:
    definition = _resolve_worker_definition(request.worker_key)
    if definition is None:
        return _encode_response(_WorkerResponseKind.WORKER_ERROR)
    try:
        settings = definition.settings_model.model_validate_json(request.settings_json)
        validated_file = ValidatedFileDescriptor.model_validate_json(request.validated_file_json)
        metadata = json.loads(request.metadata_json)
        if not isinstance(metadata, dict):
            return _encode_response(_WorkerResponseKind.WORKER_ERROR)
        analyzer_request = AnalyzerRequest(
            analysis_id=request.analysis_id,
            media_type=MediaType(request.media_type),
            validated_file=validated_file,
            source=_ReadOnlyAnalyzerInput(Path(request.source_path)),
            settings=settings,
            timeout_seconds=request.timeout_seconds,
            artifacts=tuple(
                AnalyzerArtifactInput(
                    artifact_id=artifact.artifact_id,
                    artifact_type=artifact.artifact_type,
                    content=_ReadOnlyAnalyzerInput(Path(artifact.local_path)),
                    format=artifact.format,
                    start_time_seconds=artifact.start_time_seconds,
                    end_time_seconds=artifact.end_time_seconds,
                    frame_index=artifact.frame_index,
                )
                for artifact in request.artifacts
            ),
            metadata=metadata,
            warnings=request.warnings,
        )
        analyzer = definition.factory()
        _validate_analyzer_identity(analyzer, definition, analyzer_request.media_type)
    except (ValidationError, TypeError, ValueError):
        return _encode_response(_WorkerResponseKind.WORKER_ERROR)

    try:
        applicability = analyzer.check_applicability(analyzer_request)
        if not isinstance(applicability, ApplicabilityResult):
            raise TypeError("invalid applicability result")
        if not applicability.applicable:
            assert applicability.reason_code is not None
            result = _not_applicable_result(
                analyzer,
                analyzer_request,
                applicability.reason_code,
            )
        else:
            result = analyzer.analyze(analyzer_request)
            _validate_completed_result(result, analyzer, analyzer_request)
    except _AnalyzerInputReadError:
        return _encode_response(_WorkerResponseKind.WORKER_ERROR)
    except Exception:
        return _encode_response(_WorkerResponseKind.ANALYZER_ERROR)

    try:
        return _encode_response(
            _WorkerResponseKind.RESULT,
            result=json.loads(result.model_dump_json()),
        )
    except (PydanticSerializationError, TypeError, ValueError):
        return _encode_response(_WorkerResponseKind.SERIALIZATION_ERROR)


def _validate_analyzer_identity(
    analyzer: Analyzer,
    definition: _WorkerAnalyzerDefinition,
    media_type: MediaType,
) -> None:
    if (
        analyzer.analyzer_id != definition.analyzer_id
        or analyzer.analyzer_name != definition.analyzer_name
        or analyzer.analyzer_version != definition.analyzer_version
        or analyzer.group != definition.group
        or analyzer.supported_media_types != definition.supported_media_types
        or media_type not in analyzer.supported_media_types
    ):
        raise ValueError("analyzer identity mismatch")


def _validate_completed_result(
    result: object,
    analyzer: Analyzer,
    request: AnalyzerRequest,
) -> None:
    if not isinstance(result, AnalyzerResult):
        raise TypeError("analyzer returned a non-contract result")
    if (
        result.analyzer_id != analyzer.analyzer_id
        or result.analyzer_version != analyzer.analyzer_version
        or result.group != analyzer.group
        or result.media_type is not request.media_type
        or result.status is not AnalyzerStatus.COMPLETED
        or not result.applicable
    ):
        raise ValueError("analyzer returned inconsistent framework result")


def _not_applicable_result(
    analyzer: Analyzer,
    request: AnalyzerRequest,
    reason_code: str,
) -> AnalyzerResult:
    return AnalyzerResult(
        analyzer_id=analyzer.analyzer_id,
        analyzer_version=analyzer.analyzer_version,
        media_type=request.media_type,
        group=analyzer.group,
        status=AnalyzerStatus.NOT_APPLICABLE,
        applicable=False,
        started_at=None,
        finished_at=None,
        duration_ms=0,
        score=None,
        score_name=None,
        summary=f"Analyzer is not applicable ({reason_code}).",
        raw_metrics={},
        candidate_findings=[],
        warnings=[],
        errors=[],
    )


def _encode_response(
    kind: _WorkerResponseKind,
    *,
    result: object | None = None,
) -> bytes:
    envelope: dict[str, object] = {"kind": kind.value}
    if result is not None:
        envelope["result"] = result
    payload = json.dumps(
        envelope,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) <= _MAX_RESPONSE_BYTES:
        return payload
    fallback = b'{"kind":"serialization_error"}'
    return fallback


def _duration_ms(started_at: float, finished_at: float) -> int:
    return max(0, int((finished_at - started_at) * 1000))


def _close_connection(connection: _Connection) -> None:
    with suppress(OSError, ValueError):
        connection.close()


def _known_stopped(process: _WorkerProcess) -> bool:
    try:
        return not process.is_alive()
    except (OSError, RuntimeError, ValueError):
        return False
