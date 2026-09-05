"""Sequential analyzer orchestration over controlled Stage 5 path callbacks."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from fakedetector._stage5_resources import _MAX_STAGE5_ARTIFACTS
from fakedetector.analyzers._errors import AnalyzerInfrastructureError
from fakedetector.analyzers._models import _AnalyzerFileFacts
from fakedetector.analyzers._registry import AnalyzerRegistry, _ActiveAnalyzer
from fakedetector.analyzers._transport import (
    _MAX_RESPONSE_BYTES,
    _serialize_stage5_analyzer_result,
    _Stage5AnalyzerResultSizeError,
    _WorkerArtifact,
    _WorkerRequest,
    _WorkerResponseKind,
)
from fakedetector.analyzers._worker import (
    _SpawnedWorkerRunner,
    _WorkerRun,
    _WorkerRunKind,
)
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.domain import (
    AnalyzerResult,
    AnalyzerStatus,
    ErrorDetail,
    MediaType,
    ValidatedFileDescriptor,
)
from fakedetector.intake.temporary_input import IntakeSystemError
from fakedetector.lifecycle.artifacts import (
    ArtifactRegistrationError,
    WorkspaceArtifactRegistry,
)
from fakedetector.preprocessing._models import (
    PreparedArtifact,
    PreparedMedia,
)
from fakedetector.preprocessing._requirements import PreprocessingRequirements


class _WorkerRunner(Protocol):
    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun: ...


@dataclass(frozen=True, slots=True)
class _DecodedResponse:
    kind: _WorkerResponseKind
    result: AnalyzerResult | None = None


class AnalyzerOrchestrator:
    """Execute enabled analyzers sequentially without receiving a lifecycle task."""

    def __init__(
        self,
        registry: AnalyzerRegistry,
        *,
        runner: _WorkerRunner | None = None,
    ) -> None:
        self._registry = registry
        self._runner = runner or _SpawnedWorkerRunner()

    def _uses_config_snapshot(self, snapshot: _ConfigSnapshot) -> bool:
        return self._registry._uses_config_snapshot(snapshot)

    def execute(
        self,
        prepared_media: PreparedMedia,
        validated_file: ValidatedFileDescriptor,
        artifact_registry: WorkspaceArtifactRegistry,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
        result_callback: Callable[[AnalyzerResult], None] | None = None,
    ) -> tuple[AnalyzerResult, ...]:
        """Return only results from analyzers actually launched in config order."""
        self._validate_inputs(prepared_media, validated_file, artifact_registry)
        plan = self._registry.active_plan(prepared_media.media_type)
        if not plan:
            return ()

        results: list[AnalyzerResult] = []
        for active in plan:
            result = self._execute_active(
                active,
                prepared_media,
                validated_file,
                artifact_registry,
                remaining_timeout_seconds,
            )
            results.append(result)
            if result_callback is not None:
                result_callback(result)
            if (
                result.status in {AnalyzerStatus.ERROR, AnalyzerStatus.TIMEOUT}
                and not self._registry.continue_on_failure
            ):
                break
        return tuple(results)

    def preprocessing_requirements(self, media_type: MediaType) -> PreprocessingRequirements:
        """Return demand-driven representations for the active analyzer plan."""
        return self._registry.preprocessing_requirements(media_type)

    def _effective_timeout(
        self,
        remaining_timeout_seconds: Callable[[], float] | None,
    ) -> float:
        configured_timeout = self._registry.timeout_seconds
        if remaining_timeout_seconds is None:
            return configured_timeout
        remaining = remaining_timeout_seconds()
        if not isinstance(remaining, (int, float)) or isinstance(remaining, bool):
            raise AnalyzerInfrastructureError("execution_budget")
        remaining_value = float(remaining)
        if not math.isfinite(remaining_value) or remaining_value <= 0:
            raise AnalyzerInfrastructureError("execution_budget")
        return min(configured_timeout, remaining_value)

    @staticmethod
    def _validate_inputs(
        prepared_media: PreparedMedia,
        validated_file: ValidatedFileDescriptor,
        artifact_registry: WorkspaceArtifactRegistry,
    ) -> None:
        if not isinstance(prepared_media, PreparedMedia):
            raise TypeError("prepared_media must be PreparedMedia")
        if not isinstance(validated_file, ValidatedFileDescriptor):
            raise TypeError("validated_file must be ValidatedFileDescriptor")
        if not isinstance(artifact_registry, WorkspaceArtifactRegistry):
            raise TypeError("artifact_registry must be WorkspaceArtifactRegistry")
        if prepared_media.media_type is not validated_file.media_type:
            raise AnalyzerInfrastructureError("prepared_media_mismatch")
        if any(
            not artifact_registry._matches_registered_artifact(
                artifact.artifact_ref,
                artifact.artifact_id,
            )
            for artifact in prepared_media.artifacts
        ):
            raise AnalyzerInfrastructureError("artifact_capability")

    def _execute_active(
        self,
        active: _ActiveAnalyzer,
        prepared_media: PreparedMedia,
        validated_file: ValidatedFileDescriptor,
        artifact_registry: WorkspaceArtifactRegistry,
        remaining_timeout_seconds: Callable[[], float] | None,
    ) -> AnalyzerResult:
        if len(prepared_media.artifacts) > _MAX_STAGE5_ARTIFACTS:
            raise AnalyzerInfrastructureError("worker_request")
        try:
            return prepared_media.source_file_ref.with_local_source_path(
                lambda source_path: _with_artifact_paths(
                    artifact_registry,
                    prepared_media.artifacts,
                    lambda artifact_paths: self._run_with_paths(
                        active,
                        prepared_media,
                        validated_file,
                        source_path,
                        artifact_paths,
                        remaining_timeout_seconds,
                    ),
                )
            )
        except AnalyzerInfrastructureError:
            raise
        except (ArtifactRegistrationError, IntakeSystemError, OSError, TypeError, ValueError):
            raise AnalyzerInfrastructureError("input_capability") from None

    def _run_with_paths(
        self,
        active: _ActiveAnalyzer,
        prepared_media: PreparedMedia,
        validated_file: ValidatedFileDescriptor,
        source_path: Path,
        artifact_paths: tuple[Path, ...],
        remaining_timeout_seconds: Callable[[], float] | None,
    ) -> AnalyzerResult:
        timeout_seconds = self._effective_timeout(remaining_timeout_seconds)
        try:
            request = _WorkerRequest(
                worker_key=active.registration.worker_key,
                analysis_id=prepared_media.analysis_id,
                media_type=prepared_media.media_type.value,
                file_facts_json=_AnalyzerFileFacts.from_validated_file(
                    validated_file
                ).model_dump_json(),
                source_path=str(source_path.resolve()),
                artifacts=tuple(
                    _transport_artifact(artifact, path)
                    for artifact, path in zip(
                        prepared_media.artifacts,
                        artifact_paths,
                        strict=True,
                    )
                ),
                metadata_json=json.dumps(
                    _plain_json_value(prepared_media.metadata),
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                warnings=prepared_media.warnings,
                settings_json=active.settings_json,
                timeout_seconds=timeout_seconds,
            )
        except (OSError, TypeError, ValueError):
            raise AnalyzerInfrastructureError("worker_request") from None

        run = self._runner.run(request, timeout_seconds)
        if run.kind is _WorkerRunKind.TIMEOUT:
            return _failure_result(active, prepared_media, run.duration_ms, timeout=True)
        if run.kind is not _WorkerRunKind.RESPONSE or run.response is None:
            raise AnalyzerInfrastructureError("worker_run")

        decoded = _decode_response(run.response)
        if decoded.kind is _WorkerResponseKind.WORKER_ERROR:
            raise AnalyzerInfrastructureError("worker_internal")
        if decoded.kind in {
            _WorkerResponseKind.ANALYZER_ERROR,
            _WorkerResponseKind.SERIALIZATION_ERROR,
        }:
            return _failure_result(active, prepared_media, run.duration_ms, timeout=False)
        if decoded.result is None:
            raise AnalyzerInfrastructureError("worker_result")
        _validate_result_identity(decoded.result, active, prepared_media)
        normalized_result = _with_duration(decoded.result, run.duration_ms)
        try:
            _serialize_stage5_analyzer_result(normalized_result)
        except _Stage5AnalyzerResultSizeError:
            return _failure_result(active, prepared_media, run.duration_ms, timeout=False)
        return normalized_result


def _with_artifact_paths[ResultT](
    registry: WorkspaceArtifactRegistry,
    artifacts: Sequence[PreparedArtifact],
    operation: Callable[[tuple[Path, ...]], ResultT],
    *,
    index: int = 0,
    paths: tuple[Path, ...] = (),
) -> ResultT:
    if index == len(artifacts):
        return operation(paths)
    return registry.with_local_artifact_path(
        artifacts[index].artifact_ref,
        lambda path: _with_artifact_paths(
            registry,
            artifacts,
            operation,
            index=index + 1,
            paths=(*paths, path),
        ),
    )


def _transport_artifact(artifact: PreparedArtifact, path: Path) -> _WorkerArtifact:
    return _WorkerArtifact(
        artifact_id=artifact.artifact_id,
        artifact_type=artifact.artifact_type,
        local_path=str(path.resolve()),
        format=artifact.format,
        start_time_seconds=artifact.start_time_seconds,
        end_time_seconds=artifact.end_time_seconds,
        frame_index=artifact.frame_index,
    )


def _plain_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain_json_value(item) for item in value]
    return value


def _decode_response(response: bytes) -> _DecodedResponse:
    if len(response) > _MAX_RESPONSE_BYTES:
        raise AnalyzerInfrastructureError("malformed_response")
    try:
        raw = json.loads(response.decode("utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            raise ValueError
        kind = _WorkerResponseKind(raw["kind"])
        expected_keys = {"kind", "result"} if kind is _WorkerResponseKind.RESULT else {"kind"}
        if set(raw) != expected_keys:
            raise ValueError
        if kind is not _WorkerResponseKind.RESULT:
            return _DecodedResponse(kind)
        return _DecodedResponse(kind, AnalyzerResult.model_validate(raw["result"]))
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
        raise AnalyzerInfrastructureError("malformed_response") from None


def _validate_result_identity(
    result: AnalyzerResult,
    active: _ActiveAnalyzer,
    prepared_media: PreparedMedia,
) -> None:
    registration = active.registration
    if (
        result.analyzer_id != registration.analyzer_id
        or result.analyzer_version != registration.analyzer_version
        or result.group != registration.group
        or result.media_type is not prepared_media.media_type
        or result.status not in {AnalyzerStatus.COMPLETED, AnalyzerStatus.NOT_APPLICABLE}
        or (result.status is AnalyzerStatus.COMPLETED and not result.applicable)
    ):
        raise AnalyzerInfrastructureError("result_identity")


def _with_duration(result: AnalyzerResult, duration_ms: int) -> AnalyzerResult:
    data = result.model_dump(mode="python")
    data["duration_ms"] = duration_ms
    try:
        return AnalyzerResult.model_validate(data)
    except ValidationError:
        raise AnalyzerInfrastructureError("result_duration") from None


def _failure_result(
    active: _ActiveAnalyzer,
    prepared_media: PreparedMedia,
    duration_ms: int,
    *,
    timeout: bool,
) -> AnalyzerResult:
    registration = active.registration
    status = AnalyzerStatus.TIMEOUT if timeout else AnalyzerStatus.ERROR
    return AnalyzerResult(
        analyzer_id=registration.analyzer_id,
        analyzer_version=registration.analyzer_version,
        media_type=prepared_media.media_type,
        group=registration.group,
        status=status,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=duration_ms,
        score=None,
        score_name=None,
        summary=(
            "Analyzer exceeded its execution timeout."
            if timeout
            else "Analyzer execution failed safely."
        ),
        raw_metrics={},
        candidate_findings=[],
        warnings=[],
        errors=[
            ErrorDetail(
                code="analyzer_timeout" if timeout else "analyzer_error",
                category="analyzer",
                message=(
                    "Analyzer exceeded its execution timeout."
                    if timeout
                    else "Analyzer execution failed safely."
                ),
                retryable=timeout,
                analyzer_id=registration.analyzer_id,
            )
        ],
    )
