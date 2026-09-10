"""Integrated Stage 5 execution behind the existing Stage 4 executor port."""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from fakedetector._stage5_resources import _GeneratedArtifactBudget
from fakedetector.analyzers._errors import AnalyzerInfrastructureError
from fakedetector.analyzers._orchestrator import AnalyzerOrchestrator
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalyzerResult,
    CompletenessStatus,
    ErrorDetail,
    MediaType,
)
from fakedetector.intake.temporary_input import PreparedSourceRef
from fakedetector.lifecycle._stage6 import (
    Stage6FindingFormationError,
    Stage6FindingService,
)
from fakedetector.lifecycle._stage7 import (
    Stage7AssessmentError,
    Stage7AssessmentService,
)
from fakedetector.lifecycle.execution import TaskRegistry
from fakedetector.lifecycle.models import (
    AnalysisTask,
    TaskExecutionOutcome,
)
from fakedetector.preprocessing._errors import PreprocessingError
from fakedetector.preprocessing._service import (
    PreprocessingDispatcher,
    PreprocessingRequest,
)

_SAFE_STAGE7_REASON_CODES = frozenset(
    {
        "invalid_completeness_input",
        "invalid_recommendation_input",
        "invalid_risk_input",
        "unexpected_completeness_status",
    }
)


class _Stage5DeadlineExceededError(RuntimeError):
    """Internal control signal for one exhausted monotonic execution budget."""

    def __init__(self) -> None:
        super().__init__("Stage 5 processing deadline was exceeded.")


class Stage5ExecutionService:
    """Bridge preprocessing and analyzers without owning terminal lifecycle work."""

    def __init__(
        self,
        *,
        config: AppConfig,
        registry: TaskRegistry,
        preprocessing: PreprocessingDispatcher,
        orchestrator: AnalyzerOrchestrator,
        finding_service: Stage6FindingService,
        assessment_service: Stage7AssessmentService,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config_snapshot = _ConfigSnapshot.capture(config)
        captured_config = self._config_snapshot.materialize()
        if not preprocessing._uses_config_snapshot(
            self._config_snapshot
        ) or not orchestrator._uses_config_snapshot(self._config_snapshot):
            raise ValueError("Stage 5 components use different config snapshots")
        if not assessment_service._uses_config(captured_config.risk_assessment):
            raise ValueError("Stage 7 service uses different risk configuration")
        self._processing_timeout_seconds = float(captured_config.limits.processing_timeout_seconds)
        self._planned_analyzer_ids = {
            MediaType.IMAGE: tuple(captured_config.analyzers.image.enabled),
            MediaType.AUDIO: tuple(captured_config.analyzers.audio.enabled),
            MediaType.VIDEO: tuple(captured_config.analyzers.video.enabled),
        }
        self._registry = registry
        self._preprocessing = preprocessing
        self._orchestrator = orchestrator
        self._finding_service = finding_service
        self._assessment_service = assessment_service
        self._monotonic = monotonic

    def execute(self, task: AnalysisTask) -> TaskExecutionOutcome:
        """Execute one claimed task under a single non-resetting monotonic deadline."""
        deadline = self._new_deadline()
        remaining_timeout_seconds = self._remaining_timeout(deadline)
        phase = "preprocessing"
        try:
            self._registry.validate_stage5_execution(task)
            if task.context.config_snapshot_id != self._config_snapshot.snapshot_id:
                return TaskExecutionOutcome.failed(_stage5_failure("configuration_snapshot"))

            remaining_timeout_seconds()
            requirements = self._orchestrator.preprocessing_requirements(
                task.validated_file.media_type
            )
            request = PreprocessingRequest(
                analysis_id=task.context.analysis_id,
                validated_file=task.validated_file.model_copy(deep=True),
                source_file_ref=PreparedSourceRef(task.accepted_source),
                artifact_registry=task.artifacts,
                artifact_budget=_GeneratedArtifactBudget(
                    self._config_snapshot,
                    task.validated_file.media_type,
                ),
            )
            prepared_media = self._preprocessing.prepare(
                request,
                requirements,
                remaining_timeout_seconds=remaining_timeout_seconds,
            )
            remaining_timeout_seconds()
            self._registry.publish_stage5_prepared(task, prepared_media)
            remaining_timeout_seconds()
            self._registry.start_stage5_analysis(task)
            phase = "analysis"
            remaining_timeout_seconds()

            published_results: list[AnalyzerResult] = []

            def publish_result(result: AnalyzerResult) -> None:
                self._registry.append_stage5_analyzer_result(task, result)
                published_results.append(result)

            results = self._orchestrator.execute(
                prepared_media,
                task.validated_file.model_copy(deep=True),
                task.artifacts,
                remaining_timeout_seconds=remaining_timeout_seconds,
                result_callback=publish_result,
            )
            if not isinstance(results, tuple) or tuple(published_results) != results:
                raise AnalyzerInfrastructureError("result_publication")
            remaining_timeout_seconds()
            authoritative_results = self._registry._read_stage5_analyzer_results(task)
            if authoritative_results != results:
                raise AnalyzerInfrastructureError("result_publication")
            findings = self._finding_service.form_findings(authoritative_results)
            remaining_timeout_seconds()
            self._registry.publish_stage6_findings(task, findings)
            remaining_timeout_seconds()
            authoritative_results = self._registry._read_stage5_analyzer_results(task)
            authoritative_findings = self._registry._read_stage6_findings(task)
            self._registry.start_stage7_assessment(task)
            phase = "risk_assessment"
            remaining_timeout_seconds()
            completeness, risk_assessment, recommendation = self._assessment_service.assess(
                self._planned_analyzer_ids[task.validated_file.media_type],
                authoritative_results,
                authoritative_findings,
            )
            if completeness.status is CompletenessStatus.NOT_ASSESSED:
                raise Stage7AssessmentError("unexpected_completeness_status")
            remaining_timeout_seconds()
            self._registry.publish_stage7_assessment(
                task,
                completeness,
                risk_assessment,
                recommendation,
            )
        except _Stage5DeadlineExceededError:
            return TaskExecutionOutcome.failed(_processing_timeout(phase))
        except PreprocessingError as error:
            if error._cleanup_safety_barrier is not None:
                return TaskExecutionOutcome.failed(
                    _stage5_failure("preprocessing"),
                    _cleanup_safety_barrier=error._cleanup_safety_barrier,
                )
            try:
                remaining_timeout_seconds()
            except _Stage5DeadlineExceededError:
                return TaskExecutionOutcome.failed(_processing_timeout(phase))
            if error.kind == "resource_limit":
                return TaskExecutionOutcome.failed(_stage5_resource_limit(error.phase))
            return TaskExecutionOutcome.failed(_stage5_failure("preprocessing"))
        except AnalyzerInfrastructureError as error:
            return TaskExecutionOutcome.failed(
                _stage5_failure("analysis"),
                _cleanup_safety_barrier=error._cleanup_safety_barrier,
            )
        except Stage6FindingFormationError:
            return TaskExecutionOutcome.failed(_stage5_failure("analysis"))
        except Stage7AssessmentError as error:
            return TaskExecutionOutcome.failed(_stage7_failure(error.reason_code))
        if completeness.status is CompletenessStatus.COMPLETE:
            return TaskExecutionOutcome.completed()
        if completeness.status in {
            CompletenessStatus.PARTIAL,
            CompletenessStatus.INSUFFICIENT,
        }:
            return TaskExecutionOutcome.partial()

    def _new_deadline(self) -> float:
        started_at = self._monotonic()
        if not isinstance(started_at, (int, float)) or isinstance(started_at, bool):
            raise RuntimeError("Stage 5 monotonic clock is invalid.")
        started_value = float(started_at)
        if not math.isfinite(started_value):
            raise RuntimeError("Stage 5 monotonic clock is invalid.")
        return started_value + self._processing_timeout_seconds

    def _remaining_timeout(self, deadline: float) -> Callable[[], float]:
        def remaining_timeout_seconds() -> float:
            current = self._monotonic()
            if not isinstance(current, (int, float)) or isinstance(current, bool):
                raise RuntimeError("Stage 5 monotonic clock is invalid.")
            remaining = deadline - float(current)
            if not math.isfinite(remaining):
                raise RuntimeError("Stage 5 monotonic clock is invalid.")
            if remaining <= 0:
                raise _Stage5DeadlineExceededError()
            return remaining

        return remaining_timeout_seconds


def _stage5_failure(phase: str) -> ErrorDetail:
    return ErrorDetail(
        code="internal_error",
        category="internal",
        message="Внутренняя ошибка не позволила завершить обработку файла.",
        retryable=True,
        safe_details={"phase": phase},
    )


def _stage7_failure(reason_code: str) -> ErrorDetail:
    safe_reason_code = (
        reason_code if reason_code in _SAFE_STAGE7_REASON_CODES else "assessment_failure"
    )
    return ErrorDetail(
        code="internal_error",
        category="internal",
        message="Внутренняя ошибка не позволила сформировать риск-оценку.",
        retryable=True,
        safe_details={"phase": "risk_assessment", "reason_code": safe_reason_code},
    )


def _processing_timeout(phase: str) -> ErrorDetail:
    return ErrorDetail(
        code="processing_timeout",
        category="processing",
        message="Превышено допустимое время обработки файла.",
        retryable=True,
        safe_details={"phase": phase},
    )


def _stage5_resource_limit(limit: str) -> ErrorDetail:
    return ErrorDetail(
        code="stage5_resource_limit",
        category="resource_limit",
        message="Превышен допустимый предел ресурсов предварительной обработки.",
        retryable=False,
        safe_details={"phase": "preprocessing", "limit": limit},
    )
