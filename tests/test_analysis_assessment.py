"""Tests for the pure deterministic analysis assessment policy."""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from types import ModuleType
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
from fakedetector.lifecycle._assessment import (
    _ENSEMBLE_FAMILIES,
    AnalysisAssessmentError,
    AnalysisAssessmentService,
    CompletenessAssessmentService,
    RecommendationService,
    RiskAssessmentService,
    _effective_response,
    _ensemble_response,
    _ensemble_score,
    _family_response,
    _media_capacity,
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
        AnalysisAssessmentError,
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

    with pytest.raises(AnalysisAssessmentError) as exc_info:
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
    assert recommendation == RecommendationService().recommend(
        _declared_completeness(status), _declared_risk(level)
    )
    if status is CompletenessStatus.COMPLETE and level is RiskLevel.LOW:
        assert recommendation.text == (
            "По результатам выполненных проверок система не рекомендует дополнительных действий. "
            "Низкий уровень технического риска относится только к проверенным признакам "
            "и не подтверждает подлинность или безопасность файла."
        )


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


_ENSEMBLE_SPECS = {
    spec.analyzer_id: (family.media_type, spec)
    for family in _ENSEMBLE_FAMILIES
    for spec in family.members
}
_EXPECTED_CAPACITIES = {MediaType.IMAGE: 3.4375, MediaType.AUDIO: 2.8125, MediaType.VIDEO: 2.05}


def _ensemble_config():
    return RiskAssessmentConfig.model_validate(
        {
            "model_id": "diploma_ensemble_v1",
            "model_version": "0.1.0",
            "thresholds": {"low_max": 25, "medium_max": 55},
        }
    )


def _ensemble_metrics(analyzer_id, value):
    peak = {"count": int(value is not None), "max": value}
    metrics = {
        "audio_temporal_discontinuity": {"windows": [dict.fromkeys(("J", "E", "A"), peak)]},
        "audio_spectral_consistency": {"windows": [dict.fromkeys(("D1", "D4", "F1", "F4"), peak)]},
        "audio_repeated_segment_correspondence": {
            "pairs": [
                {
                    "state": "measured",
                    "channels": [
                        {
                            "rho": value,
                            "support_rhos": [value, value],
                            "structural_support": value is not None,
                        }
                    ],
                }
            ],
        },
        "audio_background_noise_consistency": {
            "contexts": [{"tv": value, "signed_level_change": value}],
        },
        "image_noise_residual_consistency": {"max_log2_ratio": value},
        "image_resampling_consistency": {"max_log2_ratio": value},
        "video_repeated_content_correspondence": {
            key: {
                "color_numerator": int((1 - value) * 440640),
                "delta_numerator": int((1 - value) * 660960),
            }
            if value is not None
            else None
            for key in ("minimum_color_pair", "minimum_delta_pair")
        },
        "video_visual_discontinuity": {"windows": [{"transition": peak}]},
        "video_timing_anomaly": {
            "windows": [
                {
                    "observed_pairs": int(value is not None),
                    "duplicate_pts_pairs": 0,
                    "decreasing_pts_pairs": 0,
                    "gap_deviation": peak,
                }
            ]
        },
    }.get(analyzer_id, {})
    return {"profile": _ENSEMBLE_SPECS[analyzer_id][1].profile, "state": "measured", **metrics}


def _ensemble_result(analyzer_id, value=0, status=AnalyzerStatus.COMPLETED):
    media, _ = _ENSEMBLE_SPECS[analyzer_id]
    return _result(analyzer_id, status).model_copy(
        update={"media_type": media, "raw_metrics": _ensemble_metrics(analyzer_id, value)}
    )


def _ensemble_risk(results, findings=()):
    return _risk(results, findings, config=_ensemble_config())


def test_ensemble_closed_policy_matches_catalog_maturity_and_four_families():
    from fakedetector.analyzers._catalog import (
        _resolve_runtime_analyzer_definition,
        _runtime_analyzer_registrations,
    )

    assert len(_ENSEMBLE_SPECS) == 14
    assert len(_ENSEMBLE_FAMILIES) == 12
    assert set(_ENSEMBLE_SPECS) | {"audio_aasist_l_measurement"} == {
        r.analyzer_id for r in _runtime_analyzer_registrations()
    }
    for media in MediaType:
        assert sum(family.media_type is media for family in _ENSEMBLE_FAMILIES) == 4
    weights = {"CORE": 1, "EXPERIMENTAL": 0.65, "EXPERIMENTAL_WEAK": 0.35}
    for analyzer_id, (media, spec) in _ENSEMBLE_SPECS.items():
        definition = _resolve_runtime_analyzer_definition(analyzer_id)
        assert definition.supported_media_types == {media}
        assert definition.analyzer_version == "1.0.0"
        assert spec.weight == weights[definition.maturity]


def _aasist_result(status=AnalyzerStatus.COMPLETED):
    return _result("audio_aasist_l_measurement", status, group="audio").model_copy(
        update={
            "media_type": MediaType.AUDIO,
            "raw_metrics": {"raw_logits": [-1e30, 1e30], "speech_presence": "unverified"},
        }
    )


@pytest.fixture(scope="module")
def historical_assessment():
    with pytest.MonkeyPatch.context() as imports:
        imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
        from scripts import diploma_demo_evaluation as demo

    source = (demo.ROOT / "src/fakedetector/lifecycle/_assessment.py").read_text("utf-8")
    frozen = source.replace(demo._AASIST_ID_GUARD, demo._HISTORICAL_ID_GUARD, 1)
    frozen = frozen.replace(demo._F01_LOW_TEXT, demo._HISTORICAL_LOW_TEXT, 1)
    # Only execute first-party source that reproduces the immutable historical hash.
    assert demo._digest(frozen.encode()) == (
        "0b022e995316fecde23b7afbbeb2f32bb836e7bc973fdd3d0ed86c6fc06a2a1b"
    )
    module = ModuleType("fakedetector.lifecycle._frozen_assessment_test")
    sys.modules[module.__name__] = module
    try:
        exec(compile(frozen, "<SHA-verified historical assessment>", "exec"), module.__dict__)
        yield module
    finally:
        sys.modules.pop(module.__name__)


def test_current_policy_structure_matches_sha_verified_historical_policy(historical_assessment):
    def normalizer_identity(normalizer):
        if isinstance(normalizer, partial):
            return normalizer.func.__name__, normalizer.args, normalizer.keywords
        return normalizer.__name__ if normalizer else None

    def structure(families):
        return [
            (
                family.key,
                family.media_type,
                [
                    (s.analyzer_id, s.weight, s.profile, normalizer_identity(s.normalizer))
                    for s in family.members
                ],
            )
            for family in families
        ]

    assert structure(_ENSEMBLE_FAMILIES) == structure(historical_assessment._ENSEMBLE_FAMILIES)
    assert len(_ENSEMBLE_FAMILIES) == 12 and len(_ENSEMBLE_SPECS) == 14
    for media in MediaType:
        assert _media_capacity(media) == historical_assessment._media_capacity(media)
    for score in (0, 25, 25.000001, 55, 55.000001, 100):
        assert RiskAssessmentService(_ensemble_config())._score_level(score) == (
            historical_assessment.RiskAssessmentService(_ensemble_config())._score_level(score)
        )


@pytest.mark.parametrize("value", [None, 0, 0.2, 0.5, 0.7, 1])
@pytest.mark.parametrize("status", list(AnalyzerStatus))
def test_original_fourteen_numerically_match_frozen_implementation(
    historical_assessment, value, status
):
    historical_specs = {
        spec.analyzer_id: spec
        for family in historical_assessment._ENSEMBLE_FAMILIES
        for spec in family.members
    }
    for media in MediaType:
        results = [
            _ensemble_result(analyzer_id, value, status)
            for analyzer_id, (kind, _) in _ENSEMBLE_SPECS.items()
            if kind is media
        ]
        findings = tuple(
            _finding(r.analyzer_id, source_analyzer_id=r.analyzer_id)
            for r in results
            if value
            and status is AnalyzerStatus.COMPLETED
            and not _ENSEMBLE_SPECS[r.analyzer_id][1].normalizer
        )
        for result in results:
            spec = _ENSEMBLE_SPECS[result.analyzer_id][1]
            assert _ensemble_response(
                spec, result, findings
            ) == historical_assessment._ensemble_response(
                historical_specs[result.analyzer_id], result, findings
            )
        completeness = _completeness(results)
        expected = historical_assessment.RiskAssessmentService(_ensemble_config()).assess(
            completeness, results, findings
        )
        assert _ensemble_risk(results, findings) == expected


@pytest.mark.parametrize("status", list(AnalyzerStatus))
def test_all_fourteen_original_results_and_aasist_preserve_numerical_risk(status):
    # A report has exactly one media type. Exercise all 14 canonical sources in
    # their three existing per-media plans; mixed-media reports remain forbidden.
    originals = [_ensemble_result(analyzer_id, 0.7) for analyzer_id in _ENSEMBLE_SPECS]
    for media in MediaType:
        results = [r for r in originals if r.media_type is media]
        findings = [
            _finding(r.analyzer_id, source_analyzer_id=r.analyzer_id)
            for r in results
            if not _ENSEMBLE_SPECS[r.analyzer_id][1].normalizer
        ]
        before = _ensemble_risk(results, findings)
        active = [*results, _aasist_result(status)] if media is MediaType.AUDIO else results
        after = _ensemble_risk(active, findings)
        assert after.score == before.score
        assert after.final_level == before.final_level
        assert (
            _media_capacity(media)
            == {MediaType.AUDIO: 2.8125, MediaType.IMAGE: 3.4375, MediaType.VIDEO: 2.05}[media]
        )
        if media is MediaType.AUDIO:
            completeness = _completeness(active)
            assert completeness.planned_analyzers == len(results) + 1


@pytest.mark.parametrize(
    "change",
    [
        {"analyzer_version": "2.0.0"},
        {"group": "other"},
        {"score": 1},
        {"score_name": "ml"},
        {"candidate_findings": [{"type": "fake"}]},
        {"analyzer_id": "audio_unknown_ml"},
    ],
)
def test_aasist_pass_through_does_not_open_scoring_or_unknown_ids(change):
    with pytest.raises(AnalysisAssessmentError):
        _ensemble_risk([_aasist_result().model_copy(update=change)])


@pytest.mark.parametrize("analyzer_id", _ENSEMBLE_SPECS)
def test_every_ensemble_analyzer_zero_strong_bounded_deterministic(analyzer_id):
    media, spec = _ENSEMBLE_SPECS[analyzer_id]
    clean = _ensemble_result(analyzer_id, 0)
    strong = _ensemble_result(analyzer_id, 1)
    findings = () if spec.normalizer else (_finding("accepted", source_analyzer_id=analyzer_id),)
    assert _ensemble_response(spec, clean, ()) == (0, "completed_no_signal")
    response, state = _ensemble_response(spec, strong, findings)
    expected = 0.5 if analyzer_id.startswith(("image_noise", "image_resampling")) else 1
    assert response == expected and state == "signal"
    risk = _ensemble_risk([strong], findings)
    assert risk == _ensemble_risk([strong], findings)
    assert risk.score == pytest.approx(100 * spec.weight * expected / _EXPECTED_CAPACITIES[media])
    assert risk.model_id == "diploma_ensemble_v1" and risk.model_version == "0.1.0"
    assert risk.probability is risk.probability_method is None
    assert math.isfinite(response) and 0 <= response <= 1
    assert math.isfinite(risk.score) and 0 <= risk.score <= 100
    assert f"{analyzer_id}: response=" in risk.explanation
    assert not strong.candidate_findings
    assert not risk.critical_override_applied and not risk.critical_finding_ids


@pytest.mark.parametrize("analyzer_id", _ENSEMBLE_SPECS)
@pytest.mark.parametrize(
    "status",
    [
        AnalyzerStatus.ERROR,
        AnalyzerStatus.TIMEOUT,
        AnalyzerStatus.SKIPPED,
        AnalyzerStatus.NOT_APPLICABLE,
    ],
)
def test_ensemble_failed_or_inapplicable_response_is_missing_not_clean(analyzer_id, status):
    _, spec = _ENSEMBLE_SPECS[analyzer_id]
    result = _ensemble_result(analyzer_id, 1, status)
    assert _ensemble_response(spec, result, ()) == (None, status.value)
    risk = _ensemble_risk([result])
    assert risk.score is risk.score_based_level is risk.final_level is None
    assert f"{analyzer_id}={status.value}" in " ".join(risk.limitations)


@pytest.mark.parametrize(
    "analyzer_id", [k for k, (_, s) in _ENSEMBLE_SPECS.items() if s.normalizer]
)
@pytest.mark.parametrize("explicit", [True, False])
def test_experimental_undefined_and_insufficient_are_not_zero(analyzer_id, explicit):
    _, spec = _ENSEMBLE_SPECS[analyzer_id]
    result = _ensemble_result(analyzer_id, None)
    if explicit:
        result.raw_metrics["state"] = "insufficient_evidence"
    assert _ensemble_response(spec, result, ()) == (None, "insufficient_evidence")
    risk = _ensemble_risk([result])
    assert risk.score == 0  # Execution complete, but no usable measurement: fixed denominator.
    assert "response=null" in risk.explanation
    assert f"{analyzer_id}=insufficient_evidence" in " ".join(risk.limitations)
    assert "Наибольшие отклики семейств: нет положительных откликов" in risk.explanation


@pytest.mark.parametrize(
    "analyzer_id", [k for k, (_, s) in _ENSEMBLE_SPECS.items() if s.normalizer]
)
@pytest.mark.parametrize(
    "bad", [{}, {"state": "unknown"}, {"profile": "wrong", "state": "measured"}]
)
def test_experimental_malformed_metrics_fail_closed(analyzer_id, bad):
    result = _ensemble_result(analyzer_id).model_copy(update={"raw_metrics": bad})
    with pytest.raises(AnalysisAssessmentError) as exc:
        _ensemble_risk([result])
    assert exc.value.reason_code == "invalid_risk_input"


@pytest.mark.parametrize(
    "bad", [True, "0.5", -0.1, 1.01, float("nan"), float("inf"), -float("inf")]
)
def test_ensemble_rejects_invalid_numeric_metrics_and_arithmetic(bad):
    result = _ensemble_result("audio_temporal_discontinuity")
    result.raw_metrics["windows"][0]["J"]["max"] = bad
    result.raw_metrics["windows"][0]["J"]["count"] = 1
    with pytest.raises(AnalysisAssessmentError):
        _ensemble_risk([result])
    with pytest.raises(ValueError):
        _effective_response(bad, 0.65)
    with pytest.raises(ValueError):
        _effective_response(0.5, bad)
    with pytest.raises(ValueError):
        _family_response([bad])
    with pytest.raises(ValueError):
        _ensemble_score([0, 0, 0, bad], MediaType.AUDIO)


@pytest.mark.parametrize("media,capacity", _EXPECTED_CAPACITIES.items())
def test_ensemble_arithmetic_oracles(media, capacity):
    assert _media_capacity(media) == pytest.approx(capacity)
    assert _effective_response(0.8, 0.65) == pytest.approx(0.52)
    assert _family_response([0.4, 0.8, 0.2, 1e-3]) == pytest.approx(0.92)
    assert _family_response([1, 1, 1, 1]) == 1
    assert _family_response([]) == 0
    assert _ensemble_score([0, 0, 0, 0], media) == 0
    assert _ensemble_score([1, 1, 1, 1], media) == 100
    assert _ensemble_score([0.5, 0.25, 0, 1], media) == pytest.approx(100 * 1.75 / capacity)
    for values in ([0.5, 0.25, 0, 1], [0.1, 0.2, 0.3, 0.4]):
        assert _family_response(values) == _family_response(values[::-1])
        assert _ensemble_score(values, media) == _ensemble_score(values[::-1], media)
        assert 0 <= _ensemble_score(values, media) <= 100
    with pytest.raises(ValueError):
        _ensemble_score([1, 1, 1], media)


@pytest.mark.parametrize(
    "positive_id,sibling_id,response,weight,capacity",
    [
        ("image_noise_residual_consistency", "image_resampling_consistency", 0.5, 0.35, 3.4375),
        ("audio_temporal_discontinuity", "audio_spectral_consistency", 1, 0.65, 2.8125),
        ("video_repeated_content_correspondence", "video_timing_anomaly", 1, 0.35, 2.05),
    ],
)
@pytest.mark.parametrize(
    "state",
    [
        "not_planned",
        "not_applicable",
        "completed_inapplicable",
        "error",
        "timeout",
        "skipped",
        "insufficient_evidence",
    ],
)
def test_unavailable_sibling_never_reduces_capacity_or_boosts_score(
    positive_id, sibling_id, response, weight, capacity, state
):
    positive = _ensemble_result(positive_id, 1)
    sibling = _ensemble_result(sibling_id, 0)
    reference = _ensemble_risk([positive, sibling])
    results = [positive]
    if state != "not_planned":
        if state == "insufficient_evidence":
            sibling.raw_metrics["state"] = state
        elif state == "completed_inapplicable":
            sibling.applicable = False
        else:
            sibling = _ensemble_result(sibling_id, 1, AnalyzerStatus(state))
        results.append(sibling)
    risk = _ensemble_risk(results)
    assert risk.score == reference.score == pytest.approx(100 * response * weight / capacity)
    assert risk.probability is risk.probability_method is None
    assert f"media_capacity={capacity:g}" in risk.explanation
    reported_state = "not_applicable" if state == "completed_inapplicable" else state
    assert f"{sibling_id}={reported_state}" in " ".join(risk.limitations)
    assert _ensemble_risk(results[::-1]) == risk


@pytest.mark.parametrize(
    "score,level",
    [
        (0, RiskLevel.LOW),
        (25, RiskLevel.LOW),
        (math.nextafter(25, math.inf), RiskLevel.MEDIUM),
        (55, RiskLevel.MEDIUM),
        (math.nextafter(55, math.inf), RiskLevel.HIGH),
        (100, RiskLevel.HIGH),
    ],
)
def test_ensemble_exact_unrounded_boundaries(score, level):
    assert RiskAssessmentService(_ensemble_config())._score_level(score) is level


def test_atd_asc_diminish_while_unrelated_families_accumulate():
    atd = _ensemble_result("audio_temporal_discontinuity", 1)
    asc = _ensemble_result("audio_spectral_consistency", 1)
    arc = _ensemble_result("audio_repeated_segment_correspondence", 1)
    assert (
        _ensemble_risk([atd]).score
        == _ensemble_risk([asc]).score
        == pytest.approx(100 * 0.65 / 2.8125)
    )
    together = _ensemble_risk([atd, asc])
    assert together.score == pytest.approx(100 * (0.65 + 0.25 * 0.65) / 2.8125)
    independent = _ensemble_risk([atd, arc])
    assert independent.score == pytest.approx(100 * (0.65 + 0.65) / 2.8125)
    assert independent.score > together.score
    assert "audio_temporal_discontinuity × 0.25" in together.explanation
    assert together == _ensemble_risk([asc, atd])
    partial = [
        _ensemble_result("audio_pcm_quality", status=AnalyzerStatus.ERROR),
        atd,
        asc,
        _ensemble_result("audio_background_noise_consistency", status=AnalyzerStatus.TIMEOUT),
    ]
    assert _ensemble_risk(partial) == _ensemble_risk(partial[::-1])


def test_ensemble_partial_and_insufficient_keep_recommendation_rules():
    results = [
        _ensemble_result("audio_temporal_discontinuity", 1),
        _ensemble_result("audio_pcm_quality", status=AnalyzerStatus.ERROR),
    ]
    service = AnalysisAssessmentService(_ensemble_config())
    complete, risk, recommendation = service.assess([r.analyzer_id for r in results], results, [])
    assert complete.status is CompletenessStatus.PARTIAL
    assert risk.score == pytest.approx(100 * 0.65 / 2.8125)
    assert "status=partial" in risk.explanation
    assert "partial" in " ".join(risk.limitations)
    assert recommendation.requires_manual_review
    results.append(_ensemble_result("audio_spectral_consistency", status=AnalyzerStatus.TIMEOUT))
    complete, risk, recommendation = service.assess([r.analyzer_id for r in results], results, [])
    assert complete.status is CompletenessStatus.INSUFFICIENT
    assert risk.score is risk.score_based_level is risk.final_level is None
    assert recommendation.requires_manual_review
    assert _ensemble_risk([]).score is None


def test_core_findings_count_once_and_dq_insufficiency_remains_visible():
    result = _ensemble_result("image_copy_move_correspondence")
    findings = [_finding(str(i), source_analyzer_id=result.analyzer_id) for i in range(8)]
    assert _ensemble_risk([result], findings).score == pytest.approx(100 / 3.4375)
    assert _ensemble_risk([result], findings) == _ensemble_risk([result], findings[::-1])
    dq = _ensemble_result("image_jpeg_double_quantization")
    dq.raw_metrics = {"decision": "insufficient_evidence"}
    risk = _ensemble_risk([dq])
    assert "image_jpeg_double_quantization=insufficient_evidence" in " ".join(risk.limitations)
    with pytest.raises(AnalysisAssessmentError):
        _ensemble_risk([dq], [_finding("invalid", source_analyzer_id=dq.analyzer_id)])


def test_ensemble_rejects_unknown_mixed_or_changed_sources_and_experimental_findings():
    atd = _ensemble_result("audio_temporal_discontinuity")
    invalid_inputs = [
        [_result("unknown")],
        [atd, _ensemble_result("video_timing_anomaly")],
        [atd.model_copy(update={"analyzer_version": "2.0.0"})],
        [atd.model_copy(update={"candidate_findings": [{"type": "injected"}]})],
        [atd.model_copy(update={"score": 1, "score_name": "injected"})],
    ]
    for results in invalid_inputs:
        with pytest.raises(AnalysisAssessmentError):
            _ensemble_risk(results)
    with pytest.raises(AnalysisAssessmentError):
        _ensemble_risk([atd], [_finding("injected", source_analyzer_id=atd.analyzer_id)])


def test_score_model_and_unknown_legacy_ids_preserve_historical_policy():
    results = [_ensemble_result("audio_temporal_discontinuity", 1), _result("analyzer_a")]
    findings = [
        _finding("b", severity=FindingSeverity.SIGNIFICANT, correlation_group="shared"),
        _finding("a", correlation_group="shared"),
        _finding("c"),
    ]
    expected = _risk(results, findings)
    assert expected.score == 30 and expected.final_level is RiskLevel.HIGH
    for model_id in ("score_model_v1", "legacy_custom_model"):
        actual = _risk(results, findings, config=RiskAssessmentConfig(model_id=model_id))
        assert actual.model_dump(exclude={"model_id"}) == expected.model_dump(exclude={"model_id"})


def test_normalizer_specific_support_and_pair_semantics():
    arc = _ensemble_result("audio_repeated_segment_correspondence", 1)
    channel = arc.raw_metrics["pairs"][0]["channels"][0]
    channel["support_rhos"] = [0.3, 0.8]
    assert _ensemble_risk([arc]).score == pytest.approx(100 * 0.65 * 0.3 / 2.8125)
    channel["support_rhos"] = [-0.8, 1]
    assert _ensemble_risk([arc]).score == 0
    channel["support_rhos"] = [None, 1]
    channel["structural_support"] = False
    assert "response=null" in _ensemble_risk([arc]).explanation
    vrc = _ensemble_result("video_repeated_content_correspondence", 0)
    vrc.raw_metrics["minimum_color_pair"]["color_numerator"] = 0
    vrc.raw_metrics["minimum_delta_pair"]["delta_numerator"] = 0
    assert _ensemble_risk([vrc]).score == 0  # Different minima must not fabricate one good pair.
    timing = _ensemble_result("video_timing_anomaly", None)
    timing.raw_metrics["windows"][0].update(observed_pairs=10, duplicate_pts_pairs=10)
    # No positive-gap reference required.
    assert _ensemble_risk([timing]).score == pytest.approx(100 * 0.35 / 2.05)
    background = _ensemble_result("audio_background_noise_consistency", 0)
    background.raw_metrics["contexts"][0]["signed_level_change"] = -1
    assert _ensemble_risk([background]).score == pytest.approx(100 * 0.35 / 2.8125)
    noise = _ensemble_result("image_noise_residual_consistency", 1)
    noise.raw_metrics["max_log2_ratio"] = 1e308
    assert _ensemble_risk([noise]).score == pytest.approx(100 * 0.35 / 3.4375)


@pytest.mark.parametrize(
    "analyzer_id,field,bad",
    [
        ("audio_temporal_discontinuity", "windows", "not rows"),
        ("audio_temporal_discontinuity", "windows", [{}] * 7),
        ("audio_spectral_consistency", "windows", [1]),
        ("audio_spectral_consistency", "windows", [{"D1": {"count": 0, "max": 1}}]),
        ("audio_spectral_consistency", "windows", [{"D1": {"count": 1, "max": None}}]),
        ("audio_repeated_segment_correspondence", "pairs", [{"state": "unknown"}]),
        (
            "audio_repeated_segment_correspondence",
            "pairs",
            [{"state": "measured", "channels": [{"support_rhos": [1]}]}],
        ),
        (
            "audio_repeated_segment_correspondence",
            "pairs",
            [
                {
                    "state": "measured",
                    "channels": [{"rho": 1, "support_rhos": [1, 1], "structural_support": False}],
                }
            ],
        ),
        ("audio_background_noise_consistency", "contexts", [{"tv": 0}]),
        (
            "audio_background_noise_consistency",
            "contexts",
            [{"tv": 0, "signed_level_change": -1.1}],
        ),
        ("image_noise_residual_consistency", "max_log2_ratio", -1),
        ("image_resampling_consistency", "max_log2_ratio", "1"),
        (
            "video_repeated_content_correspondence",
            "minimum_color_pair",
            {"color_numerator": True, "delta_numerator": 0},
        ),
        (
            "video_repeated_content_correspondence",
            "minimum_color_pair",
            {"color_numerator": 440641, "delta_numerator": 0},
        ),
        ("video_visual_discontinuity", "windows", [{"transition": {"count": 1}}]),
        (
            "video_timing_anomaly",
            "windows",
            [{"observed_pairs": 1, "duplicate_pts_pairs": 1, "decreasing_pts_pairs": 1}],
        ),
        (
            "video_timing_anomaly",
            "windows",
            [
                {
                    "observed_pairs": 0,
                    "duplicate_pts_pairs": 0,
                    "decreasing_pts_pairs": 0,
                    "gap_deviation": {"count": 1, "max": 1},
                }
            ],
        ),
    ],
)
def test_each_normalizer_rejects_corrupt_consumed_metrics(analyzer_id, field, bad):
    result = _ensemble_result(analyzer_id)
    result.raw_metrics[field] = bad
    with pytest.raises(AnalysisAssessmentError) as exc:
        _ensemble_risk([result])
    assert exc.value.reason_code == "invalid_risk_input"


def test_missing_support_subrows_do_not_hide_other_usable_measurements():
    asc = _ensemble_result("audio_spectral_consistency", 1)
    asc.raw_metrics["windows"].insert(0, {"state": "no_full_stft_frame"})
    assert _ensemble_risk([asc]).score == pytest.approx(100 * 0.65 / 2.8125)
    visual = _ensemble_result("video_visual_discontinuity", 1)
    visual.raw_metrics["windows"].insert(0, {"state": "unsupported_geometry"})
    assert _ensemble_risk([visual]).score == pytest.approx(100 * 0.35 / 2.05)
    arc = _ensemble_result("audio_repeated_segment_correspondence", 1)
    arc.raw_metrics["pairs"].insert(0, {"state": "insufficient_support"})
    assert _ensemble_risk([arc]).score == pytest.approx(100 * 0.65 / 2.8125)
    for result, key in ((asc, "windows"), (visual, "windows"), (arc, "pairs")):
        risk = _ensemble_risk([result])
        result.raw_metrics[key].reverse()
        assert _ensemble_risk([result]) == risk


def test_ensemble_ranking_excludes_zeros_and_breaks_ties_by_family_key():
    risk = _ensemble_risk(
        [
            _ensemble_result("audio_temporal_discontinuity", 1),
            _ensemble_result("audio_repeated_segment_correspondence", 1),
        ]
    )
    top = risk.explanation.split("Наибольшие отклики семейств: ")[1]
    assert top.startswith("audio_repetition=0.65, audio_transition=0.65.")
    assert "audio_quality" not in top and "audio_background" not in top


@pytest.mark.parametrize("media", MediaType)
def test_canonical_profile_maximum_is_100_and_high_for_every_media(media):
    results, findings = [], []
    for analyzer_id, (source_media, spec) in _ENSEMBLE_SPECS.items():
        if source_media is not media:
            continue
        result = _ensemble_result(analyzer_id, 1)
        if "max_log2_ratio" in result.raw_metrics:
            result.raw_metrics["max_log2_ratio"] = 1e308
        if spec.normalizer is None:
            findings.append(_finding(analyzer_id, source_analyzer_id=analyzer_id))
        results.append(result)
    risk = _ensemble_risk(results, findings)
    assert risk.score == pytest.approx(100)
    assert risk.score_based_level is risk.final_level is RiskLevel.HIGH
    assert risk.probability is risk.probability_method is None
    assert risk == _ensemble_risk(results[::-1], findings[::-1])


def test_ensemble_never_expands_override_and_does_not_claim_authenticity():
    result = _ensemble_result("audio_pcm_quality")
    finding = _finding(
        "accepted",
        finding_type="trusted_test_signal",
        source_analyzer_id=result.analyzer_id,
        severity=FindingSeverity.CRITICAL,
        eligible=True,
    )
    config = _ensemble_config().model_copy(
        update={
            "critical_override": _risk_config(
                override_enabled=True, allowed_finding_types=[finding.type]
            ).critical_override
        }
    )
    risk = _risk(
        [result],
        [finding],
        config=config,
        rules=[_TrustedCriticalRule(finding.type, result.analyzer_id, "1.0.0")],
    )
    assert not risk.critical_override_applied and risk.critical_finding_ids == []
    assert risk.score == pytest.approx(100 / 2.8125)
    assert risk.score_based_level is risk.final_level is RiskLevel.MEDIUM
    text = " ".join([risk.summary, risk.explanation, *risk.limitations]).lower()
    for unsupported in (
        "файл поддельный",
        "файл настоящий",
        "подлинность подтверждена",
        "% fake",
        "confidence of forgery",
    ):
        assert unsupported not in text


def test_completed_but_inapplicable_is_disclosed_and_provenance_is_still_checked():
    result = _ensemble_result("image_metadata_consistency").model_copy(update={"applicable": False})
    risk = _ensemble_risk([result])
    assert risk.score == 0
    assert "image_metadata_consistency=not_applicable" in " ".join(risk.limitations)
    with pytest.raises(AnalysisAssessmentError):
        _ensemble_risk([result], [_finding("bad", source_analyzer_id=result.analyzer_id)])


@pytest.mark.parametrize(
    "value,expected", [(math.nextafter(1, math.inf), 1), (math.nextafter(0, -math.inf), 0)]
)
def test_natural_measurement_roundoff_is_clamped_without_loosening_arithmetic(value, expected):
    result = _ensemble_result("audio_temporal_discontinuity")
    for peak in result.raw_metrics["windows"][0].values():
        peak["count"], peak["max"] = 1, value
    assert _ensemble_risk([result]).score == pytest.approx(100 * 0.65 * expected / 2.8125)
    with pytest.raises(ValueError):
        _effective_response(value, 1)
