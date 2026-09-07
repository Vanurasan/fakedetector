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
from threading import Lock
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
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._transport import (
    _MAX_RESPONSE_BYTES,
    _encode_stage5_result_response,
    _Stage5AnalyzerResultSizeError,
    _WorkerRequest,
    _WorkerResponseKind,
)
from fakedetector.core._cleanup_safety import _CleanupSafetyInterruption
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, MediaType

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
        except BaseException as error:
            _close_connection(receive_connection)
            _close_connection(send_connection)
            if isinstance(error, (OSError, RuntimeError, TypeError, ValueError)):
                raise AnalyzerInfrastructureError("spawn_setup") from None
            raise

        process_started = False
        try:
            try:
                try:
                    process.start()
                    process_started = True
                except BaseException as start_error:
                    # start() may be interrupted after the backend acquired a child.
                    process_started = True
                    with suppress(OSError, RuntimeError, ValueError):
                        process_started = process.is_alive() or process.exitcode is not None
                    if isinstance(start_error, (OSError, RuntimeError, TypeError, ValueError)):
                        raise AnalyzerInfrastructureError("spawn_start") from None
                    raise
                _close_connection(send_connection)
                kind, response = self._wait_for_response(
                    process,
                    receive_connection,
                    deadline=started_at + timeout_seconds,
                )
            finally:
                try:
                    _close_connection(receive_connection)
                finally:
                    _close_connection(send_connection)
        except BaseException as error:
            if process_started:
                self._stop_and_reap(process, error=error)
            raise
        finally:
            if not process_started:
                with suppress(OSError, ValueError):
                    process.close()

        self._stop_and_reap(process)
        return _WorkerRun(
            kind=kind,
            duration_ms=_duration_ms(started_at, self._monotonic()),
            response=response,
        )

    def _wait_for_response(
        self,
        process: _WorkerProcess,
        receive_connection: _Connection,
        *,
        deadline: float,
    ) -> tuple[_WorkerRunKind, bytes | None]:
        try:
            response_ready = receive_connection.poll(max(0.0, deadline - self._monotonic()))
        except (OSError, EOFError, ValueError):
            raise AnalyzerInfrastructureError("worker_ipc") from None

        if not response_ready:
            if not self._is_alive(process):
                raise AnalyzerInfrastructureError("worker_no_response")
            return _WorkerRunKind.TIMEOUT, None

        try:
            response = receive_connection.recv_bytes(_MAX_RESPONSE_BYTES)
        except (OSError, EOFError, ValueError):
            raise AnalyzerInfrastructureError("worker_response") from None

        self._bounded_join(process, max(0.0, deadline - self._monotonic()))
        if self._is_alive(process):
            return _WorkerRunKind.TIMEOUT, None
        if process.exitcode != 0:
            raise AnalyzerInfrastructureError("worker_exit")
        return _WorkerRunKind.RESPONSE, response

    def _stop_and_reap(
        self,
        process: _WorkerProcess,
        *,
        error: BaseException | None = None,
    ) -> None:
        barrier = _WorkerReapBarrier(process)
        try:
            if barrier.try_confirm_safe():
                return
        except BaseException as reap_error:
            if barrier._confirmed:
                if error is not None and not isinstance(error, Exception):
                    raise error from None
                raise
            # An interrupted escalation must retain the same unresolved process.
            if error is None or isinstance(error, Exception):
                error = reap_error
        if error is not None and not isinstance(error, Exception):
            raise _CleanupSafetyInterruption(error, barrier) from None
        raise AnalyzerInfrastructureError(
            "worker_reap",
            _cleanup_safety_barrier=barrier,
        )

    @staticmethod
    def _bounded_join(
        process: _WorkerProcess,
        timeout: float,
    ) -> None:
        try:
            process.join(max(0.0, timeout))
        except (OSError, RuntimeError, ValueError):
            raise AnalyzerInfrastructureError("worker_join") from None

    @staticmethod
    def _is_alive(process: _WorkerProcess) -> bool:
        try:
            return process.is_alive()
        except (OSError, RuntimeError, ValueError):
            raise AnalyzerInfrastructureError("worker_join") from None


class _WorkerReapBarrier:
    """Retain one unresolved worker and retry stop/reap with fixed bounds."""

    def __init__(self, process: _WorkerProcess) -> None:
        self._process: _WorkerProcess | None = process
        self._confirmed = False
        self._lock = Lock()

    def try_confirm_safe(self) -> bool:
        """Return true only after a bounded join confirms the worker stopped."""
        with self._lock:
            if self._confirmed:
                return True
            process = self._process
            if process is None:
                return False

            if self._confirm_stopped(process):
                return self._mark_confirmed(process)

            with suppress(OSError, RuntimeError, ValueError):
                process.terminate()
            self._try_join(process, _TERMINATE_JOIN_SECONDS)
            if self._confirm_stopped(process):
                return self._mark_confirmed(process)

            with suppress(OSError, RuntimeError, ValueError):
                process.kill()
            self._try_join(process, _KILL_JOIN_SECONDS)
            if self._confirm_stopped(process):
                return self._mark_confirmed(process)
            return False

    @staticmethod
    def _try_join(process: _WorkerProcess, timeout: float) -> bool:
        try:
            process.join(max(0.0, timeout))
        except (OSError, RuntimeError, ValueError):
            return False
        return True

    @classmethod
    def _confirm_stopped(cls, process: _WorkerProcess) -> bool:
        try:
            if process.is_alive():
                return False
        except (OSError, RuntimeError, ValueError):
            return False
        return cls._try_join(process, 0.0)

    def _mark_confirmed(self, process: _WorkerProcess) -> bool:
        self._confirmed = True
        self._process = None
        with suppress(OSError, ValueError):
            process.close()
        return True


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
        file_facts = _AnalyzerFileFacts.model_validate_json(request.file_facts_json)
        metadata = json.loads(request.metadata_json)
        if not isinstance(metadata, dict):
            return _encode_response(_WorkerResponseKind.WORKER_ERROR)
        analyzer_request = AnalyzerRequest(
            analysis_id=request.analysis_id,
            media_type=MediaType(request.media_type),
            file_facts=file_facts,
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
        return _encode_response(_WorkerResponseKind.RESULT, result=result)
    except _Stage5AnalyzerResultSizeError:
        return _encode_response(_WorkerResponseKind.ANALYZER_ERROR)
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
    result: AnalyzerResult | None = None,
) -> bytes:
    if kind is _WorkerResponseKind.RESULT:
        if result is None:
            raise ValueError("result response requires an AnalyzerResult")
        return _encode_stage5_result_response(result)
    if result is not None:
        raise ValueError("non-result response cannot contain a result")
    envelope: dict[str, object] = {"kind": kind.value}
    return json.dumps(
        envelope,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _duration_ms(started_at: float, finished_at: float) -> int:
    return max(0, int((finished_at - started_at) * 1000))


def _close_connection(connection: _Connection) -> None:
    with suppress(OSError, ValueError):
        connection.close()
