"""Pure result assembly and the single persistence finalization boundary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.core import AuthoritativeLifecycleClock
from fakedetector.domain import (
    AnalysisCompleteness,
    AnalysisResult,
    AnalysisStatus,
    AnalyzerResult,
    CleanupResult,
    CompletenessStatus,
    ErrorDetail,
    Finding,
    InputFileDescriptor,
    ProcessingStage,
    Recommendation,
    RiskAssessment,
    SourceContext,
    ValidatedFileDescriptor,
)
from fakedetector.domain.models import AnalysisProcessing
from fakedetector.intake.lifecycle import Stage3Terminal
from fakedetector.lifecycle.models import TerminalTaskFacts
from fakedetector.repositories import ResultRepository


class ResultFinalizationError(Exception):
    """Safe typed failure after a factual terminal identity is available."""

    def __init__(self, analysis_id: str) -> None:
        super().__init__("Analysis result could not be persisted.")
        self.analysis_id = analysis_id

    @property
    def error_detail(self) -> ErrorDetail:
        """Return a detached safe lifecycle error for the authoritative registry."""
        return ErrorDetail(
            code="result_write_failed",
            category="storage",
            message="Не удалось сохранить итоговый результат анализа.",
            retryable=True,
        )


class AcceptedResultFinalizer(Protocol):
    """Processor-facing port preserving the assembly-to-save lifecycle boundary."""

    def finalize_accepted(
        self,
        facts: TerminalTaskFacts,
        *,
        finished_at: datetime,
        before_save: Callable[[], None],
    ) -> object:
        """Assemble first, invoke the persistence transition, then save."""
        ...


class AnalysisResultAssembler:
    """Map factual terminal sources to one canonical AnalysisResult without I/O."""

    def __init__(self, *, config_snapshot_id: str, application_version: str) -> None:
        if not config_snapshot_id or not application_version:
            raise ValueError("result provenance identity is incomplete")
        self._config_snapshot_id = config_snapshot_id
        self._application_version = application_version

    def assemble_accepted(
        self,
        facts: TerminalTaskFacts,
        *,
        finished_at: datetime,
    ) -> AnalysisResult:
        """Assemble an accepted terminal task from detached authoritative facts."""
        if facts.config_snapshot_id != self._config_snapshot_id:
            raise ValueError("terminal facts use a different configuration snapshot")
        source = SourceContext.model_validate_json(facts.source_json)
        file = ValidatedFileDescriptor.model_validate_json(facts.file_json)
        analyzers = [
            AnalyzerResult.model_validate_json(payload)
            for payload in facts.analyzer_results_json
        ]
        findings = [Finding.model_validate_json(payload) for payload in facts.findings_json]
        cleanup_facts = CleanupResult.model_validate_json(facts.cleanup_json)
        if cleanup_facts.finished_at is not None:
            raise ValueError("terminal cleanup facts cannot contain a candidate timestamp")
        cleanup = CleanupResult.model_validate(
            {
                **cleanup_facts.model_dump(mode="python", warnings="error"),
                "finished_at": finished_at,
            }
        )
        errors = [ErrorDetail.model_validate_json(payload) for payload in facts.errors_json]
        assessment_payloads = (
            facts.completeness_json,
            facts.risk_assessment_json,
            facts.recommendation_json,
        )
        if facts.status in {AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL}:
            if any(payload is None for payload in assessment_payloads):
                raise ValueError("usable accepted result requires authoritative Stage 7 facts")
            assert facts.completeness_json is not None
            assert facts.risk_assessment_json is not None
            assert facts.recommendation_json is not None
            completeness = AnalysisCompleteness.model_validate_json(facts.completeness_json)
            risk_assessment = RiskAssessment.model_validate_json(facts.risk_assessment_json)
            recommendation = Recommendation.model_validate_json(facts.recommendation_json)
        else:
            if any(payload is not None for payload in assessment_payloads):
                raise ValueError("failed accepted result cannot contain a Stage 7 assessment")
            completeness = _not_assessed()
            risk_assessment = None
            recommendation = None
        return self._assemble(
            analysis_id=facts.analysis_id,
            created_at=facts.created_at,
            finished_at=finished_at,
            status=facts.status,
            source=source,
            file=file,
            queued_at=facts.queued_at,
            started_at=facts.started_at,
            analyzers=analyzers,
            findings=findings,
            completeness=completeness,
            risk_assessment=risk_assessment,
            recommendation=recommendation,
            cleanup=cleanup,
            errors=errors,
        )

    def assemble_stage3(
        self,
        terminal: Stage3Terminal,
        *,
        finished_at: datetime,
    ) -> AnalysisResult:
        """Assemble a registered Stage 3 terminal outcome without placeholders."""
        file: InputFileDescriptor | ValidatedFileDescriptor | None
        if terminal.validated_file is not None:
            file = terminal.validated_file.model_copy(deep=True)
        elif terminal.input_file is not None:
            file = terminal.input_file.model_copy(deep=True)
        else:
            file = None
        return self._assemble(
            analysis_id=terminal.analysis_id,
            created_at=terminal.registered_at,
            finished_at=finished_at,
            status=terminal.status,
            source=terminal.source.model_copy(deep=True),
            file=file,
            queued_at=None,
            started_at=None,
            analyzers=[],
            findings=[],
            completeness=_not_assessed(),
            risk_assessment=None,
            recommendation=None,
            cleanup=(
                None if terminal.cleanup is None else terminal.cleanup.model_copy(deep=True)
            ),
            errors=[error.model_copy(deep=True) for error in terminal.errors],
        )

    def _assemble(
        self,
        *,
        analysis_id: str,
        created_at: datetime,
        finished_at: datetime,
        status: AnalysisStatus,
        source: SourceContext,
        file: InputFileDescriptor | ValidatedFileDescriptor | None,
        queued_at: datetime | None,
        started_at: datetime | None,
        analyzers: list[AnalyzerResult],
        findings: list[Finding],
        completeness: AnalysisCompleteness,
        risk_assessment: RiskAssessment | None,
        recommendation: Recommendation | None,
        cleanup: CleanupResult | None,
        errors: list[ErrorDetail],
    ) -> AnalysisResult:
        return AnalysisResult.model_validate(
            {
                "schema_version": "1.0",
                "analysis_id": analysis_id,
                "created_at": created_at,
                "updated_at": finished_at,
                "status": status,
                "stage": ProcessingStage.FINISHED,
                "source": source,
                "file": file,
                "processing": AnalysisProcessing(
                    queued_at=queued_at,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=(
                        None
                        if started_at is None
                        else (finished_at - started_at) // timedelta(milliseconds=1)
                    ),
                    config_snapshot_id=self._config_snapshot_id,
                    application_version=self._application_version,
                ),
                "analyzers": analyzers,
                "findings": findings,
                "completeness": completeness,
                "risk_assessment": risk_assessment,
                "recommendation": recommendation,
                "cleanup": cleanup,
                "warnings": [],
                "errors": errors,
            }
        )


class ResultFinalizationService:
    """Validate, policy-project, and persist one canonical terminal result."""

    def __init__(
        self,
        *,
        config: AppConfig,
        clock: AuthoritativeLifecycleClock,
        repository: ResultRepository,
    ) -> None:
        self._config_snapshot = _ConfigSnapshot.capture(config)
        captured_config = self._config_snapshot.materialize()
        self._clock = clock
        self._repository = repository
        self._include_raw_metrics = captured_config.result.include_raw_metrics
        self._assembler = AnalysisResultAssembler(
            config_snapshot_id=self._config_snapshot.snapshot_id,
            application_version=captured_config.server.application_version,
        )

    def _uses_config_snapshot(self, snapshot: _ConfigSnapshot) -> bool:
        return self._config_snapshot == snapshot

    def finalize_accepted(
        self,
        facts: TerminalTaskFacts,
        *,
        finished_at: datetime,
        before_save: Callable[[], None],
    ) -> AnalysisResult:
        """Assemble before publishing PERSISTENCE, then persist exactly once."""
        prepared = self._prepare(
            self._assembler.assemble_accepted(facts, finished_at=finished_at)
        )
        before_save()
        return self._save(prepared)

    def finalize_stage3(self, terminal: Stage3Terminal) -> AnalysisResult:
        """Synchronously persist one registered Stage 3 terminal result."""
        lower_bound = terminal.registered_at
        if terminal.input_file is not None:
            lower_bound = max(lower_bound, terminal.input_file.received_at)
        if terminal.cleanup is not None and terminal.cleanup.finished_at is not None:
            lower_bound = max(lower_bound, terminal.cleanup.finished_at)
        finished_at = self._clock.terminal_now(not_before=lower_bound)
        prepared = self._prepare(
            self._assembler.assemble_stage3(terminal, finished_at=finished_at)
        )
        return self._save(prepared)

    def _prepare(self, result: AnalysisResult) -> AnalysisResult:
        validated = AnalysisResult.model_validate(
            result.model_dump(mode="python", round_trip=True, warnings="error")
        )
        if self._include_raw_metrics:
            return validated
        projected_analyzers = [
            AnalyzerResult.model_validate(
                {
                    **analyzer.model_dump(mode="python", warnings="error"),
                    "raw_metrics": {},
                }
            )
            for analyzer in validated.analyzers
        ]
        return AnalysisResult.model_validate(
            {
                **validated.model_dump(mode="python", round_trip=True, warnings="error"),
                "analyzers": projected_analyzers,
            }
        )

    def _save(self, result: AnalysisResult) -> AnalysisResult:
        analysis_id = result.analysis_id
        try:
            validated = AnalysisResult.model_validate(
                result.model_dump(mode="python", round_trip=True, warnings="error")
            )
            self._repository.save(validated)
            return AnalysisResult.model_validate(
                validated.model_dump(mode="python", round_trip=True, warnings="error")
            )
        except Exception:
            raise ResultFinalizationError(analysis_id) from None


def _not_assessed() -> AnalysisCompleteness:
    return AnalysisCompleteness(
        status=CompletenessStatus.NOT_ASSESSED,
        planned_analyzers=None,
        applicable_analyzers=None,
        completed_analyzers=None,
        failed_analyzers=None,
        timed_out_analyzers=None,
        skipped_analyzers=None,
        not_applicable_analyzers=None,
        coverage_ratio=None,
        missing_capabilities=[],
        explanation="Полнота анализа не оценивалась.",
    )
