"""Tests for the pure deterministic Stage 7 assessment policy."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from fakedetector.config.models import CompletenessConfig, RiskAssessmentConfig
from fakedetector.domain import (
    AnalysisCompleteness,
    AnalyzerResult,
    AnalyzerStatus,
    CompletenessStatus,
    ErrorDetail,
    Finding,
    FindingSeverity,
    MediaType,
    RiskAssessment,
    RiskLevel,
)
from fakedetector.lifecycle._stage7 import (
    CompletenessAssessmentService,
    RecommendationService,
    RiskAssessmentService,
    Stage7AssessmentError,
    _TrustedCriticalRule,
)


def _error(analyzer_id: str, status: AnalyzerStatus) -> ErrorDetail:
    return ErrorDetail(
        code="analyzer_timeout" if status is AnalyzerStatus.TIMEOUT else "analyzer_error",
        category="analyzer",
        message="Анализатор не завершил проверку.",
        retryable=True,
        analyzer_id=analyzer_id,
    )


def _result(
    analyzer_id: str,
    status: AnalyzerStatus = AnalyzerStatus.COMPLETED,
    *,
    version: str = "1.0.0",
    group: str = "test_group",
    applicable: bool | None = None,
) -> AnalyzerResult:
    if applicable is None:
        applicable = status is not AnalyzerStatus.NOT_APPLICABLE
    errors = (
        [_error(analyzer_id, status)]
        if status
        in {
            AnalyzerStatus.ERROR,
            AnalyzerStatus.TIMEOUT,
        }
        else []
    )
    return AnalyzerResult(
        analyzer_id=analyzer_id,
        analyzer_version=version,
        media_type=MediaType.IMAGE,
        group=group,
        status=status,
        applicable=applicable,
        started_at=None,
        finished_at=None,
        duration_ms=None,
        score=None,
        score_name=None,
        summary=(
            "Анализатор пропущен политикой."
            if status is AnalyzerStatus.SKIPPED
            else "Проверка завершена."
        ),
        raw_metrics={},
        candidate_findings=[],
        warnings=[],
        errors=errors,
    )


def _finding(
    finding_id: str,
    *,
    severity: FindingSeverity = FindingSeverity.WEAK,
    finding_type: str = "test_signal",
    source_analyzer_id: str = "analyzer_a",
    source_analyzer_version: str = "1.0.0",
    group: str = "test_group",
    correlation_group: str | None = None,
    eligible: bool = False,
    source_score: float | None = None,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        group=group,
        type=finding_type,
        severity=severity,
        source_analyzer_id=source_analyzer_id,
        source_analyzer_version=source_analyzer_version,
        description="Наблюдаемый технический признак.",
        localization=None,
        source_score=source_score,
        score_impact=None,
        critical_override_eligible=eligible,
        correlation_group=correlation_group,
        evidence_refs=[],
    )


def _completeness(
    results: Sequence[AnalyzerResult],
    *,
    minimum: float = 0.5,
) -> AnalysisCompleteness:
    return CompletenessAssessmentService(CompletenessConfig(minimum_for_assessment=minimum)).assess(
        [result.analyzer_id for result in results], results
    )


def _risk_config(
    *,
    override_enabled: bool = False,
    allowed_finding_types: Sequence[str] = (),
) -> RiskAssessmentConfig:
    return RiskAssessmentConfig.model_validate(
        {
            "critical_override": {
                "enabled": override_enabled,
                "allowed_finding_types": list(allowed_finding_types),
            }
        }
    )


def _risk(
    results: Sequence[AnalyzerResult],
    findings: Sequence[Finding],
    *,
    config: RiskAssessmentConfig | None = None,
    rules: Sequence[_TrustedCriticalRule] | None = None,
) -> RiskAssessment:
    completeness = _completeness(results)
    risk_config = config or _risk_config()
    service = (
        RiskAssessmentService(risk_config)
        if rules is None
        else RiskAssessmentService(
            risk_config,
            _trusted_critical_rules=rules,
        )
    )
    return service.assess(completeness, results, findings)


def test_complete_analysis_with_no_findings_is_low_without_probability() -> None:
    results = [_result("analyzer_a")]

    completeness = _completeness(results)
    risk = _risk(results, [])

    assert completeness.status is CompletenessStatus.COMPLETE
    assert completeness.coverage_ratio == 1.0
    assert risk.score == 0
    assert risk.score_based_level is RiskLevel.LOW
    assert risk.final_level is RiskLevel.LOW
    assert risk.probability is None
    assert risk.probability_method is None
    assert any("не является доказательством подлинности" in item for item in risk.limitations)


@pytest.mark.parametrize(
    ("findings", "expected_score", "expected_level"),
    [
        ([_finding("finding_1")], 5, RiskLevel.LOW),
        ([_finding("finding_1"), _finding("finding_2")], 10, RiskLevel.MEDIUM),
        (
            [_finding("finding_1", severity=FindingSeverity.SIGNIFICANT)],
            25,
            RiskLevel.MEDIUM,
        ),
        (
            [
                _finding("finding_1", severity=FindingSeverity.SIGNIFICANT),
                _finding("finding_2"),
            ],
            30,
            RiskLevel.HIGH,
        ),
    ],
)
def test_score_model_v1_thresholds(
    findings: list[Finding],
    expected_score: int,
    expected_level: RiskLevel,
) -> None:
    risk = _risk([_result("analyzer_a")], findings)

    assert risk.score == expected_score
    assert risk.score_based_level is expected_level
    assert risk.final_level is expected_level


def test_source_score_is_not_used_by_score_model_v1() -> None:
    results = [_result("analyzer_a")]
    low_source_score = _finding("finding_1", source_score=0.01)
    high_source_score = _finding("finding_1", source_score=0.99)

    first = _risk(results, [low_source_score])
    second = _risk(results, [high_source_score])

    assert first.score == second.score == 5
    assert first.final_level is second.final_level is RiskLevel.LOW


def test_correlation_bucket_uses_maximum_and_deterministic_representative() -> None:
    results = [_result("analyzer_a")]
    findings = [
        _finding(
            "finding_b",
            severity=FindingSeverity.SIGNIFICANT,
            correlation_group="shared_signal",
        ),
        _finding(
            "finding_a",
            severity=FindingSeverity.SIGNIFICANT,
            correlation_group="shared_signal",
        ),
        _finding("finding_c"),
    ]

    first = _risk(results, findings)
    second = _risk(results, list(reversed(findings)))

    assert first == second
    assert first.score == 30
    assert "representative=finding_a" in first.explanation
    assert "подавленные повторные вклады=[finding_b]" in first.explanation
    assert all(finding.score_impact is None for finding in findings)


def test_completeness_preserves_exact_ratio_and_missing_plan_order() -> None:
    results = [
        _result("completed", AnalyzerStatus.COMPLETED),
        _result("errored", AnalyzerStatus.ERROR),
        _result("timed_out", AnalyzerStatus.TIMEOUT),
        _result("skipped", AnalyzerStatus.SKIPPED),
        _result("not_applicable", AnalyzerStatus.NOT_APPLICABLE),
    ]

    completeness = _completeness(results)

    assert completeness.status is CompletenessStatus.INSUFFICIENT
    assert completeness.planned_analyzers == 5
    assert completeness.applicable_analyzers == 4
    assert completeness.completed_analyzers == 1
    assert completeness.failed_analyzers == 1
    assert completeness.timed_out_analyzers == 1
    assert completeness.skipped_analyzers == 1
    assert completeness.not_applicable_analyzers == 1
    assert completeness.coverage_ratio == 1 / 4
    assert completeness.missing_capabilities == [
        "errored",
        "timed_out",
        "skipped",
        "not_applicable",
    ]
    assert "error=[errored]" in completeness.explanation
    assert "timeout=[timed_out]" in completeness.explanation
    assert "skipped=[skipped]" in completeness.explanation
    assert "not_applicable=[not_applicable]" in completeness.explanation


def test_completeness_threshold_equality_is_partial() -> None:
    results = [
        _result("completed"),
        _result("errored", AnalyzerStatus.ERROR),
    ]

    completeness = _completeness(results)

    assert completeness.coverage_ratio == 0.5
    assert completeness.status is CompletenessStatus.PARTIAL


def test_completeness_ratio_is_not_artificially_rounded() -> None:
    results = [
        _result("completed_a"),
        _result("completed_b"),
        _result("errored", AnalyzerStatus.ERROR),
    ]

    completeness = _completeness(results)

    assert completeness.coverage_ratio == 2 / 3
    assert completeness.coverage_ratio != 0.67


def test_not_applicable_does_not_prevent_complete_for_remaining_plan() -> None:
    results = [
        _result("completed"),
        _result("not_applicable", AnalyzerStatus.NOT_APPLICABLE),
    ]

    completeness = _completeness(results)

    assert completeness.status is CompletenessStatus.COMPLETE
    assert completeness.applicable_analyzers == 1
    assert completeness.coverage_ratio == 1.0
    assert completeness.missing_capabilities == ["not_applicable"]


@pytest.mark.parametrize(
    ("results", "minimum"),
    [
        ([], 0.5),
        ([_result("na", AnalyzerStatus.NOT_APPLICABLE)], 0.5),
        ([_result("error", AnalyzerStatus.ERROR)], 0.5),
        (
            [
                _result("completed"),
                _result("error_1", AnalyzerStatus.ERROR),
                _result("error_2", AnalyzerStatus.ERROR),
            ],
            0.5,
        ),
    ],
)
def test_insufficient_completeness_never_produces_risk(
    results: list[AnalyzerResult],
    minimum: float,
) -> None:
    completeness = _completeness(results, minimum=minimum)
    risk = RiskAssessmentService(_risk_config()).assess(completeness, results, [])

    assert completeness.status is CompletenessStatus.INSUFFICIENT
    assert risk.score is None
    assert risk.score_based_level is None
    assert risk.final_level is None
    assert not risk.critical_override_applied
    assert risk.critical_finding_ids == []


def test_completeness_rejects_results_not_matching_active_plan_order() -> None:
    service = CompletenessAssessmentService(CompletenessConfig())
    results = [_result("analyzer_b"), _result("analyzer_a")]

    with pytest.raises(
        Stage7AssessmentError,
        match="Stage 7 assessment failed",
    ) as exc_info:
        service.assess(["analyzer_a", "analyzer_b"], results)

    assert exc_info.value.reason_code == "invalid_completeness_input"


def test_critical_override_is_disabled_by_default_even_with_trusted_rule() -> None:
    finding = _finding(
        "finding_critical",
        severity=FindingSeverity.CRITICAL,
        finding_type="trusted_test_signal",
        eligible=True,
    )
    rule = _TrustedCriticalRule(
        "trusted_test_signal",
        "analyzer_a",
        "1.0.0",
    )

    risk = _risk(
        [_result("analyzer_a")],
        [finding],
        config=_risk_config(allowed_finding_types=["trusted_test_signal"]),
        rules=[rule],
    )

    assert risk.score == 25
    assert risk.final_level is RiskLevel.MEDIUM
    assert not risk.critical_override_applied
    assert risk.critical_finding_ids == []


def test_production_trusted_critical_catalog_is_empty() -> None:
    finding = _finding(
        "finding_critical",
        severity=FindingSeverity.CRITICAL,
        finding_type="trusted_test_signal",
        eligible=True,
    )

    risk = _risk(
        [_result("analyzer_a")],
        [finding],
        config=_risk_config(
            override_enabled=True,
            allowed_finding_types=["trusted_test_signal"],
        ),
    )

    assert not risk.critical_override_applied
    assert risk.final_level is RiskLevel.MEDIUM


def test_exact_test_only_trusted_rule_applies_override() -> None:
    rule = _TrustedCriticalRule(
        "trusted_test_signal",
        "analyzer_a",
        "1.0.0",
    )
    findings = [
        _finding(
            "finding_b",
            severity=FindingSeverity.CRITICAL,
            finding_type="trusted_test_signal",
            eligible=True,
            correlation_group="shared",
        ),
        _finding(
            "finding_a",
            severity=FindingSeverity.CRITICAL,
            finding_type="trusted_test_signal",
            eligible=True,
            correlation_group="shared",
        ),
    ]

    risk = _risk(
        [_result("analyzer_a")],
        findings,
        config=_risk_config(
            override_enabled=True,
            allowed_finding_types=["trusted_test_signal"],
        ),
        rules=[rule],
    )

    assert risk.score == 25
    assert risk.score_based_level is RiskLevel.MEDIUM
    assert risk.critical_override_applied
    assert risk.critical_finding_ids == ["finding_a", "finding_b"]
    assert risk.final_level is RiskLevel.HIGH


@pytest.mark.parametrize(
    "finding_changes",
    [
        {"severity": FindingSeverity.SIGNIFICANT},
        {"eligible": False},
        {"finding_type": "not_allowed"},
    ],
)
def test_critical_override_rejects_nonqualifying_finding(
    finding_changes: dict[str, Any],
) -> None:
    finding_parameters: dict[str, Any] = {
        "severity": FindingSeverity.CRITICAL,
        "finding_type": "trusted_test_signal",
        "eligible": True,
    }
    finding_parameters.update(finding_changes)
    finding = _finding("finding_critical", **finding_parameters)
    rule = _TrustedCriticalRule(
        "trusted_test_signal",
        "analyzer_a",
        "1.0.0",
    )

    risk = _risk(
        [_result("analyzer_a")],
        [finding],
        config=_risk_config(
            override_enabled=True,
            allowed_finding_types=["trusted_test_signal"],
        ),
        rules=[rule],
    )

    assert not risk.critical_override_applied
    assert risk.critical_finding_ids == []


def test_critical_override_rejects_trusted_rule_version_mismatch() -> None:
    finding = _finding(
        "finding_critical",
        severity=FindingSeverity.CRITICAL,
        finding_type="trusted_test_signal",
        source_analyzer_version="2.0.0",
        eligible=True,
    )
    rule = _TrustedCriticalRule(
        "trusted_test_signal",
        "analyzer_a",
        "1.0.0",
    )

    risk = _risk(
        [_result("analyzer_a", version="2.0.0")],
        [finding],
        config=_risk_config(
            override_enabled=True,
            allowed_finding_types=["trusted_test_signal"],
        ),
        rules=[rule],
    )

    assert risk.score == 25
    assert not risk.critical_override_applied


@pytest.mark.parametrize(
    ("results", "finding"),
    [
        (
            [_result("analyzer_a")],
            _finding("finding_1", source_analyzer_id="missing_analyzer"),
        ),
        (
            [
                _result("analyzer_a"),
                _result("analyzer_b", AnalyzerStatus.ERROR),
            ],
            _finding("finding_1", source_analyzer_id="analyzer_b"),
        ),
        (
            [_result("analyzer_a", applicable=False)],
            _finding("finding_1"),
        ),
        (
            [_result("analyzer_a")],
            _finding("finding_1", source_analyzer_version="2.0.0"),
        ),
        (
            [_result("analyzer_a")],
            _finding("finding_1", group="other_group"),
        ),
    ],
    ids=[
        "missing_source",
        "source_error",
        "source_applicable_false",
        "version_mismatch",
        "group_mismatch",
    ],
)
def test_risk_rejects_invalid_finding_provenance(
    results: list[AnalyzerResult],
    finding: Finding,
) -> None:
    completeness = _completeness(results)

    with pytest.raises(Stage7AssessmentError) as exc_info:
        RiskAssessmentService(_risk_config()).assess(completeness, results, [finding])

    assert exc_info.value.reason_code == "invalid_risk_input"


def test_risk_scores_finding_with_matching_completed_applicable_source() -> None:
    risk = _risk([_result("analyzer_a")], [_finding("finding_1")])

    assert risk.score == 5
    assert risk.score_based_level is RiskLevel.LOW
    assert risk.final_level is RiskLevel.LOW


def test_critical_override_is_never_applied_when_completeness_is_insufficient() -> None:
    results = [
        _result("analyzer_a"),
        _result("analyzer_b", AnalyzerStatus.ERROR),
        _result("analyzer_c", AnalyzerStatus.ERROR),
    ]
    finding = _finding(
        "finding_critical",
        severity=FindingSeverity.CRITICAL,
        finding_type="trusted_test_signal",
        eligible=True,
    )
    rule = _TrustedCriticalRule(
        "trusted_test_signal",
        "analyzer_a",
        "1.0.0",
    )

    risk = _risk(
        results,
        [finding],
        config=_risk_config(
            override_enabled=True,
            allowed_finding_types=["trusted_test_signal"],
        ),
        rules=[rule],
    )

    assert _completeness(results).status is CompletenessStatus.INSUFFICIENT
    assert risk.score is None
    assert not risk.critical_override_applied
    assert risk.final_level is None


def _declared_completeness(status: CompletenessStatus) -> AnalysisCompleteness:
    if status is CompletenessStatus.COMPLETE:
        values = (1, 1, 1, 0, 1.0, [])
    elif status is CompletenessStatus.PARTIAL:
        values = (2, 2, 1, 1, 0.5, ["analyzer_b"])
    else:
        values = (1, 1, 0, 1, 0.0, ["analyzer_a"])
    planned, applicable, completed, failed, coverage, missing = values
    return AnalysisCompleteness(
        status=status,
        planned_analyzers=planned,
        applicable_analyzers=applicable,
        completed_analyzers=completed,
        failed_analyzers=failed,
        timed_out_analyzers=0,
        skipped_analyzers=0,
        not_applicable_analyzers=0,
        coverage_ratio=coverage,
        missing_capabilities=missing,
        explanation="Ограничение полноты зафиксировано.",
    )


def _declared_risk(level: RiskLevel | None) -> RiskAssessment:
    return RiskAssessment(
        model_id="score_model_v1",
        model_version="0.1.0",
        score=None if level is None else 0,
        score_based_level=level,
        critical_override_applied=False,
        critical_finding_ids=[],
        final_level=level,
        probability=None,
        probability_method=None,
        summary="Риск объявлен.",
        explanation="Основания перечислены.",
        limitations=[],
    )


@pytest.mark.parametrize(
    ("status", "level", "primary", "additional", "manual"),
    [
        (CompletenessStatus.COMPLETE, RiskLevel.LOW, "no_additional_action", [], False),
        (
            CompletenessStatus.COMPLETE,
            RiskLevel.MEDIUM,
            "manual_review",
            ["verify_source_via_independent_channel"],
            True,
        ),
        (
            CompletenessStatus.COMPLETE,
            RiskLevel.HIGH,
            "escalate_to_security",
            [
                "manual_review",
                "verify_source_via_independent_channel",
                "send_to_incident_response",
            ],
            True,
        ),
        (
            CompletenessStatus.PARTIAL,
            RiskLevel.LOW,
            "manual_review",
            ["retry_analysis"],
            True,
        ),
        (
            CompletenessStatus.PARTIAL,
            RiskLevel.MEDIUM,
            "manual_review",
            ["verify_source_via_independent_channel", "retry_analysis"],
            True,
        ),
        (
            CompletenessStatus.PARTIAL,
            RiskLevel.HIGH,
            "escalate_to_security",
            [
                "manual_review",
                "verify_source_via_independent_channel",
                "retry_analysis",
            ],
            True,
        ),
        (
            CompletenessStatus.INSUFFICIENT,
            None,
            "manual_review",
            ["retry_analysis"],
            True,
        ),
    ],
)
def test_recommendation_matrix(
    status: CompletenessStatus,
    level: RiskLevel | None,
    primary: str,
    additional: list[str],
    manual: bool,
) -> None:
    recommendation = RecommendationService().recommend(
        _declared_completeness(status),
        _declared_risk(level),
    )

    assert recommendation.primary_action == primary
    assert recommendation.additional_actions == additional
    assert recommendation.requires_manual_review is manual
    assert recommendation.text


def test_explanations_are_deterministic_and_avoid_forensic_verdicts() -> None:
    results = [_result("analyzer_a")]
    completeness = _completeness(results)
    risk = _risk(results, [])
    recommendation = RecommendationService().recommend(completeness, risk)
    text = " ".join(
        [
            completeness.explanation,
            risk.summary,
            risk.explanation,
            *risk.limitations,
            recommendation.text,
        ]
    ).lower()

    assert "score=0" in text
    assert "thresholds: low=0..5, medium=6..29, high>=30" in text
    assert "critical override: applied=false" in text
    assert "файл поддельный" not in text
    assert "файл настоящий" not in text
    assert "вероятность подделки" not in text
