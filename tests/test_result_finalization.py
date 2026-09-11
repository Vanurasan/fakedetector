"""Tests for factual AnalysisResult assembly and the persistence boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.core import AuthoritativeLifecycleClock
from fakedetector.domain import (
    AnalysisCompleteness,
    AnalysisResult,
    AnalysisStatus,
    AnalyzerResult,
    AnalyzerStatus,
    CleanupResult,
    CleanupStatus,
    CompletenessStatus,
    ErrorDetail,
    Finding,
    FindingSeverity,
    ImageTechnicalParameters,
    InputFileDescriptor,
    MediaType,
    Recommendation,
    RiskAssessment,
    RiskLevel,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.intake import Stage3Terminal
from fakedetector.lifecycle.models import TerminalTaskFacts
from fakedetector.repositories import JsonFileResultRepository, ResultRepositoryError
from fakedetector.result_finalization import (
    AnalysisResultAssembler,
    ResultFinalizationError,
    ResultFinalizationService,
)

_CREATED = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
_FINISHED = _CREATED + timedelta(seconds=3)


class _FixedClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


class _RecordingRepository:
    def __init__(self, events: list[str] | None = None) -> None:
        self.saved: list[AnalysisResult] = []
        self.events = events

    def save(self, result: AnalysisResult) -> None:
        if self.events is not None:
            self.events.append("save")
        self.saved.append(result.model_copy(deep=True))

    def get(self, analysis_id: str) -> AnalysisResult | None:
        return next((result for result in self.saved if result.analysis_id == analysis_id), None)

    def exists(self, analysis_id: str) -> bool:
        return self.get(analysis_id) is not None

    def list_recent(self, limit: int):
        del limit
        return []


class _FailingRepository(_RecordingRepository):
    def save(self, result: AnalysisResult) -> None:
        del result
        raise ResultRepositoryError("PRIVATE C:\\runtime\\results\\secret.json")


def _config(
    tmp_path: Path,
    *,
    include_raw_metrics: bool = False,
) -> AppConfig:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(tmp_path / "temp")
    raw["result"]["directory"] = str(tmp_path / "results")
    raw["result"]["include_raw_metrics"] = include_raw_metrics
    return AppConfig.model_validate(raw)


def _validated_file() -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name="проверка.png",
        extension="png",
        declared_mime_type="image/png",
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=128,
        sha256="a" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=ImageTechnicalParameters(
            width=16,
            height=8,
            format="PNG",
            color_mode="RGB",
            has_metadata=False,
        ),
    )


def _analyzer_result(*, failed: bool = False) -> AnalyzerResult:
    error = ErrorDetail(
        code="analyzer_error",
        category="analyzer",
        message="Анализатор завершился ошибкой.",
        retryable=False,
        analyzer_id="image_test",
    )
    return AnalyzerResult(
        analyzer_id="image_test",
        analyzer_version="1.0.0",
        media_type=MediaType.IMAGE,
        group="image",
        status=AnalyzerStatus.ERROR if failed else AnalyzerStatus.COMPLETED,
        applicable=True,
        started_at=_CREATED + timedelta(seconds=1),
        finished_at=_CREATED + timedelta(seconds=2),
        duration_ms=1000,
        score=None if failed else 5.0,
        score_name=None if failed else "test_score",
        summary="Тестовый результат анализатора.",
        raw_metrics={"private_metric": {"value": 0.25}},
        candidate_findings=[],
        warnings=[],
        errors=[error] if failed else [],
    )


def _completeness(status: CompletenessStatus) -> AnalysisCompleteness:
    if status is CompletenessStatus.COMPLETE:
        values = (1, 1, 1, 0, 0, 0, 0, 1.0)
    elif status is CompletenessStatus.PARTIAL:
        values = (2, 2, 1, 1, 0, 0, 0, 0.5)
    else:
        values = (1, 1, 0, 1, 0, 0, 0, 0.0)
    return AnalysisCompleteness(
        status=status,
        planned_analyzers=values[0],
        applicable_analyzers=values[1],
        completed_analyzers=values[2],
        failed_analyzers=values[3],
        timed_out_analyzers=values[4],
        skipped_analyzers=values[5],
        not_applicable_analyzers=values[6],
        coverage_ratio=values[7],
        missing_capabilities=[] if status is CompletenessStatus.COMPLETE else ["missing"],
        explanation="Полнота определена авторитетным Stage 7.",
    )


def _risk(status: CompletenessStatus) -> RiskAssessment:
    insufficient = status is CompletenessStatus.INSUFFICIENT
    return RiskAssessment(
        model_id="score_model_v1",
        model_version="0.1.0",
        score=None if insufficient else 5.0,
        score_based_level=None if insufficient else RiskLevel.LOW,
        critical_override_applied=False,
        critical_finding_ids=[],
        final_level=None if insufficient else RiskLevel.LOW,
        probability=None,
        probability_method=None,
        summary="Риск сформирован Stage 7.",
        explanation="Тестовая авторитетная оценка.",
        limitations=["Покрытие недостаточно."] if insufficient else [],
    )


def _recommendation() -> Recommendation:
    return Recommendation(
        primary_action="manual_review",
        additional_actions=[],
        text="Рекомендуется ручная проверка.",
        requires_manual_review=True,
    )


def _terminal_facts(
    config: AppConfig,
    *,
    status: AnalysisStatus,
    completeness_status: CompletenessStatus | None,
) -> TerminalTaskFacts:
    analyzer = _analyzer_result()
    finding = Finding(
        finding_id="finding-accepted-failure",
        group="image",
        type="test_finding",
        severity=FindingSeverity.WEAK,
        source_analyzer_id=analyzer.analyzer_id,
        source_analyzer_version=analyzer.analyzer_version,
        description="Фактически опубликованный признак.",
        localization={"type": "file"},
        source_score=analyzer.score,
        score_impact=None,
        critical_override_eligible=False,
        correlation_group=None,
        evidence_refs=[],
    )
    cleanup = CleanupResult(
        status=CleanupStatus.COMPLETED,
        original_file_deleted=True,
        intermediate_files_deleted=True,
        quarantine_used=False,
        finished_at=None,
        errors=[],
    )
    primary_errors = (
        [
            ErrorDetail(
                code="internal_error",
                category="internal",
                message="Обработка завершилась системной ошибкой.",
                retryable=True,
            )
        ]
        if status is AnalysisStatus.FAILED
        else []
    )
    completeness = (
        None if completeness_status is None else _completeness(completeness_status)
    )
    risk = None if completeness_status is None else _risk(completeness_status)
    recommendation = None if completeness_status is None else _recommendation()
    return TerminalTaskFacts(
        analysis_id=f"accepted-{status.value}",
        created_at=_CREATED,
        status=status,
        config_snapshot_id=_ConfigSnapshot.capture(config).snapshot_id,
        queued_at=_CREATED,
        started_at=_CREATED + timedelta(seconds=1),
        source_json=SourceContext(channel=SourceChannel.API).model_dump_json().encode(),
        file_json=_validated_file().model_dump_json().encode(),
        analyzer_results_json=(analyzer.model_dump_json().encode(),),
        findings_json=(finding.model_dump_json().encode(),)
        if status is AnalysisStatus.FAILED
        else (),
        completeness_json=(
            None if completeness is None else completeness.model_dump_json().encode()
        ),
        risk_assessment_json=None if risk is None else risk.model_dump_json().encode(),
        recommendation_json=(
            None if recommendation is None else recommendation.model_dump_json().encode()
        ),
        cleanup_json=cleanup.model_dump_json().encode(),
        errors_json=tuple(error.model_dump_json().encode() for error in primary_errors),
    )


@pytest.mark.parametrize(
    ("status", "completeness_status", "expected_risk"),
    [
        (AnalysisStatus.COMPLETED, CompletenessStatus.COMPLETE, RiskLevel.LOW),
        (AnalysisStatus.PARTIAL, CompletenessStatus.PARTIAL, RiskLevel.LOW),
        (AnalysisStatus.PARTIAL, CompletenessStatus.INSUFFICIENT, None),
        (AnalysisStatus.FAILED, None, None),
    ],
)
def test_assembler_maps_every_accepted_terminal_shape(
    tmp_path: Path,
    status: AnalysisStatus,
    completeness_status: CompletenessStatus | None,
    expected_risk: RiskLevel | None,
) -> None:
    config = _config(tmp_path)
    assembler = AnalysisResultAssembler(
        config_snapshot_id=_ConfigSnapshot.capture(config).snapshot_id,
        application_version=config.server.application_version,
    )

    result = assembler.assemble_accepted(
        _terminal_facts(
            config,
            status=status,
            completeness_status=completeness_status,
        ),
        finished_at=_FINISHED,
    )

    assert result.schema_version == "1.0"
    assert result.status is status
    assert result.processing.finished_at == _FINISHED
    assert result.processing.duration_ms == 2_000
    assert result.cleanup is not None
    assert result.cleanup.finished_at == _FINISHED
    assert result.risk_assessment is None or result.risk_assessment.final_level is expected_risk
    if completeness_status is None:
        assert result.completeness.status is CompletenessStatus.NOT_ASSESSED
        assert result.completeness.planned_analyzers is None
        assert result.recommendation is None
        assert result.errors
        assert len(result.analyzers) == 1
        assert result.analyzers[0].analyzer_id == "image_test"
        assert result.findings[0].finding_id == "finding-accepted-failure"
    else:
        assert result.completeness.status is completeness_status
        assert result.recommendation is not None


@pytest.mark.parametrize("include_raw_metrics", [True, False])
def test_finalizer_applies_raw_metrics_policy_without_mutating_terminal_facts(
    tmp_path: Path,
    include_raw_metrics: bool,
) -> None:
    config = _config(tmp_path, include_raw_metrics=include_raw_metrics)
    events: list[str] = []
    repository = _RecordingRepository(events)
    service = ResultFinalizationService(
        config=config,
        clock=AuthoritativeLifecycleClock(_FixedClock(_FINISHED)),
        repository=repository,
    )
    facts = _terminal_facts(
        config,
        status=AnalysisStatus.COMPLETED,
        completeness_status=CompletenessStatus.COMPLETE,
    )
    authoritative_payload = facts.analyzer_results_json[0]

    result = service.finalize_accepted(
        facts,
        finished_at=_FINISHED,
        before_save=lambda: events.append("persistence"),
    )

    assert events == ["persistence", "save"]
    assert result.analyzers[0].raw_metrics == (
        {"private_metric": {"value": 0.25}} if include_raw_metrics else {}
    )
    assert AnalyzerResult.model_validate_json(authoritative_payload).raw_metrics == {
        "private_metric": {"value": 0.25}
    }
    assert facts.analyzer_results_json[0] == authoritative_payload
    assert repository.saved == [result]
    assert repository.saved[0] is not result


def _stage3_terminal(
    status: AnalysisStatus,
    *,
    file_state: str,
    include_cleanup: bool = True,
) -> Stage3Terminal:
    input_file = (
        InputFileDescriptor(
            original_name="stage3.png",
            declared_content_type="image/png",
            size_bytes=128,
            received_at=_CREATED + timedelta(seconds=1),
        )
        if file_state == "input"
        else None
    )
    validated_file = _validated_file() if file_state == "validated" else None
    validation = None
    if validated_file is not None:
        validation = ValidationResult(
            accepted=True,
            checks=[],
            errors=[],
            validated_file=validated_file,
        )
    cleanup = (
        None
        if file_state == "none" or not include_cleanup
        else CleanupResult(
            status=CleanupStatus.COMPLETED,
            original_file_deleted=True,
            intermediate_files_deleted=True,
            quarantine_used=False,
            finished_at=_CREATED + timedelta(seconds=2),
            errors=[],
        )
    )
    return Stage3Terminal(
        analysis_id=f"stage3-{status.value}-{file_state}",
        registered_at=_CREATED,
        source=SourceContext(channel=SourceChannel.API),
        input_file=input_file,
        validation=validation,
        validated_file=validated_file,
        status=status,
        cleanup=cleanup,
        errors=[
            ErrorDetail(
                code="invalid_input" if status is AnalysisStatus.REJECTED else "internal_error",
                category="validation" if status is AnalysisStatus.REJECTED else "internal",
                message="Безопасная причина Stage 3.",
                retryable=False,
            )
        ],
    )


@pytest.mark.parametrize(
    ("status", "file_state", "expected_file_type"),
    [
        (AnalysisStatus.REJECTED, "input", InputFileDescriptor),
        (AnalysisStatus.FAILED, "none", type(None)),
        (AnalysisStatus.FAILED, "validated", ValidatedFileDescriptor),
    ],
)
def test_stage3_terminal_finalization_persists_only_factual_state(
    tmp_path: Path,
    status: AnalysisStatus,
    file_state: str,
    expected_file_type: type[object],
) -> None:
    config = _config(tmp_path)
    repository = JsonFileResultRepository(config.result.directory)
    service = ResultFinalizationService(
        config=config,
        clock=AuthoritativeLifecycleClock(_FixedClock(_FINISHED)),
        repository=repository,
    )
    terminal = _stage3_terminal(status, file_state=file_state)

    result = service.finalize_stage3(terminal)

    assert isinstance(result.file, expected_file_type)
    assert result.processing.queued_at is None
    assert result.processing.started_at is None
    assert result.processing.finished_at == _FINISHED
    assert result.processing.duration_ms is None
    assert result.risk_assessment is None
    assert result.recommendation is None
    assert result.completeness.status is CompletenessStatus.NOT_ASSESSED
    assert result.completeness.coverage_ratio is None
    assert result.cleanup == terminal.cleanup
    assert repository.get(terminal.analysis_id) == result


def test_stage3_assembler_does_not_fabricate_cleanup_for_file_facts(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    assembler = AnalysisResultAssembler(
        config_snapshot_id=_ConfigSnapshot.capture(config).snapshot_id,
        application_version=config.server.application_version,
    )
    terminal = _stage3_terminal(
        AnalysisStatus.REJECTED,
        file_state="input",
        include_cleanup=False,
    )

    with pytest.raises(ValidationError, match="file facts requires cleanup facts"):
        assembler.assemble_stage3(terminal, finished_at=_FINISHED)


def test_stage3_persistence_failure_is_safe_typed_and_creates_no_fake_result(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    service = ResultFinalizationService(
        config=config,
        clock=AuthoritativeLifecycleClock(_FixedClock(_FINISHED)),
        repository=_FailingRepository(),
    )
    terminal = _stage3_terminal(AnalysisStatus.REJECTED, file_state="input")

    with pytest.raises(ResultFinalizationError) as error_info:
        service.finalize_stage3(terminal)

    error = error_info.value
    assert error.analysis_id == terminal.analysis_id
    assert error.error_detail.code == "result_write_failed"
    assert "PRIVATE" not in str(error)
    assert str(tmp_path) not in str(error)
