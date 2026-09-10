"""Pure deterministic completeness, risk, and recommendation policy for Stage 7."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.config.models import CompletenessConfig, RiskAssessmentConfig
from fakedetector.domain import (
    AnalysisCompleteness,
    AnalyzerResult,
    AnalyzerStatus,
    CompletenessStatus,
    Finding,
    FindingSeverity,
    Recommendation,
    RiskAssessment,
    RiskLevel,
)


class Stage7AssessmentError(RuntimeError):
    """Safe failure raised when authoritative Stage 7 inputs are inconsistent."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Stage 7 assessment failed.")


@dataclass(frozen=True, slots=True, order=True)
class _TrustedCriticalRule:
    finding_type: str
    source_analyzer_id: str
    source_analyzer_version: str


@dataclass(frozen=True, slots=True)
class _ScoringBucket:
    key: str
    correlation_group: str | None
    findings: tuple[Finding, ...]
    representative: Finding
    contribution: int


_PRODUCTION_TRUSTED_CRITICAL_RULES: tuple[_TrustedCriticalRule, ...] = ()


class CompletenessAssessmentService:
    """Calculate completeness for one exact active analyzer plan."""

    def __init__(self, config: CompletenessConfig) -> None:
        try:
            if not isinstance(config, CompletenessConfig):
                raise TypeError("CompletenessConfig is required")
            self._config = CompletenessConfig.model_validate(
                config.model_dump(mode="python", warnings="error")
            )
        except (PydanticSerializationError, TypeError, ValidationError, ValueError):
            raise Stage7AssessmentError("invalid_configuration") from None

    def assess(
        self,
        planned_analyzer_ids: Sequence[str],
        analyzer_results: Sequence[AnalyzerResult],
    ) -> AnalysisCompleteness:
        try:
            plan = tuple(planned_analyzer_ids)
            results = _validated_results(analyzer_results, expected_ids=plan)
            return _build_completeness(
                plan,
                results,
                minimum_for_assessment=self._config.minimum_for_assessment,
            )
        except (
            AttributeError,
            PydanticSerializationError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise Stage7AssessmentError("invalid_completeness_input") from None


class RiskAssessmentService:
    """Apply score_model_v1 to authoritative findings without media I/O."""

    def __init__(
        self,
        config: RiskAssessmentConfig,
        *,
        _trusted_critical_rules: Sequence[_TrustedCriticalRule] = (
            _PRODUCTION_TRUSTED_CRITICAL_RULES
        ),
    ) -> None:
        try:
            if not isinstance(config, RiskAssessmentConfig):
                raise TypeError("RiskAssessmentConfig is required")
            self._config = RiskAssessmentConfig.model_validate(
                config.model_dump(mode="python", warnings="error")
            )
            rules = tuple(_trusted_critical_rules)
            if any(
                not isinstance(rule, _TrustedCriticalRule)
                or not rule.finding_type.strip()
                or not rule.source_analyzer_id.strip()
                or not rule.source_analyzer_version.strip()
                for rule in rules
            ):
                raise ValueError("invalid trusted critical rule")
            self._trusted_critical_rules = frozenset(rules)
        except (
            AttributeError,
            PydanticSerializationError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise Stage7AssessmentError("invalid_configuration") from None

    def assess(
        self,
        completeness: AnalysisCompleteness,
        analyzer_results: Sequence[AnalyzerResult],
        findings: Sequence[Finding],
    ) -> RiskAssessment:
        try:
            validated_completeness = _validated_completeness(completeness)
            results = _validated_results(analyzer_results)
            validated_findings = _validated_findings(findings)
            expected_completeness = _build_completeness(
                tuple(result.analyzer_id for result in results),
                results,
                minimum_for_assessment=(self._config.completeness.minimum_for_assessment),
            )
            if validated_completeness.model_dump(exclude={"explanation"}) != (
                expected_completeness.model_dump(exclude={"explanation"})
            ):
                raise ValueError("completeness does not match analyzer results")
            _validate_finding_provenance(results, validated_findings)
            buckets = self._build_scoring_buckets(validated_findings)
            qualifying_ids = self._qualifying_critical_finding_ids(
                validated_completeness,
                validated_findings,
            )
            return self._assessment(
                validated_completeness,
                results,
                validated_findings,
                buckets,
                qualifying_ids,
            )
        except (
            AttributeError,
            PydanticSerializationError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise Stage7AssessmentError("invalid_risk_input") from None

    def _severity_contribution(self, finding: Finding) -> int:
        scores = self._config.severity_scores
        return {
            FindingSeverity.WEAK: scores.weak,
            FindingSeverity.SIGNIFICANT: scores.significant,
            FindingSeverity.CRITICAL: scores.critical,
        }[finding.severity]

    def _build_scoring_buckets(
        self,
        findings: tuple[Finding, ...],
    ) -> tuple[_ScoringBucket, ...]:
        grouped: dict[tuple[str, str], list[Finding]] = {}
        for finding in findings:
            if finding.correlation_group is None:
                group_key = ("finding", finding.finding_id)
            else:
                group_key = ("correlation_group", finding.correlation_group)
            grouped.setdefault(group_key, []).append(finding)

        buckets: list[_ScoringBucket] = []
        for (kind, value), members in sorted(grouped.items()):
            ordered_members = tuple(sorted(members, key=lambda item: item.finding_id))
            representative = min(
                ordered_members,
                key=lambda item: (-self._severity_contribution(item), item.finding_id),
            )
            buckets.append(
                _ScoringBucket(
                    key=f"{kind}:{value}",
                    correlation_group=(value if kind == "correlation_group" else None),
                    findings=ordered_members,
                    representative=representative,
                    contribution=self._severity_contribution(representative),
                )
            )
        return tuple(buckets)

    def _qualifying_critical_finding_ids(
        self,
        completeness: AnalysisCompleteness,
        findings: tuple[Finding, ...],
    ) -> tuple[str, ...]:
        if (
            completeness.status is CompletenessStatus.INSUFFICIENT
            or not self._config.critical_override.enabled
        ):
            return ()

        allowed_types = set(self._config.critical_override.allowed_finding_types)
        qualifying: list[str] = []
        for finding in findings:
            rule = _TrustedCriticalRule(
                finding_type=finding.type,
                source_analyzer_id=finding.source_analyzer_id,
                source_analyzer_version=finding.source_analyzer_version,
            )
            if (
                finding.type in allowed_types
                and rule in self._trusted_critical_rules
                and finding.severity is FindingSeverity.CRITICAL
                and finding.critical_override_eligible
            ):
                qualifying.append(finding.finding_id)
        return tuple(sorted(qualifying))

    def _assessment(
        self,
        completeness: AnalysisCompleteness,
        results: tuple[AnalyzerResult, ...],
        findings: tuple[Finding, ...],
        buckets: tuple[_ScoringBucket, ...],
        qualifying_ids: tuple[str, ...],
    ) -> RiskAssessment:
        assessable = completeness.status in {
            CompletenessStatus.COMPLETE,
            CompletenessStatus.PARTIAL,
        }
        if assessable:
            calculated_score = sum(bucket.contribution for bucket in buckets)
            score: int | None = calculated_score
            score_based_level = self._score_level(calculated_score)
            override_applied = bool(qualifying_ids)
            final_level = RiskLevel.HIGH if override_applied else score_based_level
        else:
            score = None
            score_based_level = None
            override_applied = False
            final_level = None
            qualifying_ids = ()

        return RiskAssessment(
            model_id=self._config.model_id,
            model_version=self._config.model_version,
            score=score,
            score_based_level=score_based_level,
            critical_override_applied=override_applied,
            critical_finding_ids=list(qualifying_ids),
            final_level=final_level,
            probability=None,
            probability_method=None,
            summary=_risk_summary(completeness.status, final_level),
            explanation=self._risk_explanation(
                completeness,
                findings,
                buckets,
                score,
                override_applied,
                qualifying_ids,
            ),
            limitations=_risk_limitations(completeness, results, findings),
        )

    def _score_level(self, score: int) -> RiskLevel:
        thresholds = self._config.thresholds
        if score <= thresholds.low_max:
            return RiskLevel.LOW
        if score <= thresholds.medium_max:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH

    def _risk_explanation(
        self,
        completeness: AnalysisCompleteness,
        findings: tuple[Finding, ...],
        buckets: tuple[_ScoringBucket, ...],
        score: int | None,
        override_applied: bool,
        qualifying_ids: tuple[str, ...],
    ) -> str:
        finding_details = (
            " | ".join(
                (
                    f"finding_id={finding.finding_id}, type={finding.type}, "
                    f"severity={finding.severity.value}, "
                    f"source={finding.source_analyzer_id}@{finding.source_analyzer_version}"
                )
                for finding in findings
            )
            or "нет"
        )
        bucket_details = (
            " | ".join(
                (
                    f"bucket={bucket.key}, correlation_group="
                    f"{bucket.correlation_group or 'null'}, "
                    f"representative={bucket.representative.finding_id}, "
                    f"contribution={bucket.contribution if score is not None else 'не применён'}, "
                    "подавленные повторные вклады="
                    f"{_format_ids(_suppressed_finding_ids(bucket))}"
                )
                for bucket in buckets
            )
            or "нет"
        )
        thresholds = self._config.thresholds
        high_min = thresholds.medium_max + 1
        return (
            f"Полнота: status={completeness.status.value}. "
            f"Findings: {finding_details}. Scoring buckets: {bucket_details}. "
            f"Score={score if score is not None else 'null'}; thresholds: "
            f"low=0..{thresholds.low_max}, "
            f"medium={thresholds.low_max + 1}..{thresholds.medium_max}, "
            f"high>={high_min}. Critical override: applied="
            f"{'true' if override_applied else 'false'}, "
            f"qualifying_finding_ids={_format_ids(qualifying_ids)}."
        )


class RecommendationService:
    """Map completeness and risk to deterministic non-automated next steps."""

    def recommend(
        self,
        completeness: AnalysisCompleteness,
        risk_assessment: RiskAssessment,
    ) -> Recommendation:
        try:
            validated_completeness = _validated_completeness(completeness)
            risk = _validated_risk(risk_assessment)
            key = (validated_completeness.status, risk.final_level)
            recommendation = _RECOMMENDATIONS[key]
            if validated_completeness.status is CompletenessStatus.INSUFFICIENT:
                if risk.score is not None or risk.score_based_level is not None:
                    raise ValueError("insufficient assessment must not have a score")
            elif risk.final_level is None:
                raise ValueError("assessable completeness requires final risk")
            return Recommendation.model_validate(
                {
                    "primary_action": recommendation[0],
                    "additional_actions": list(recommendation[1]),
                    "text": recommendation[2],
                    "requires_manual_review": recommendation[3],
                }
            )
        except (
            AttributeError,
            KeyError,
            PydanticSerializationError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise Stage7AssessmentError("invalid_recommendation_input") from None


class Stage7AssessmentService:
    """Compose the pure Stage 7 policy over one validated immutable config."""

    def __init__(self, config: RiskAssessmentConfig) -> None:
        try:
            if not isinstance(config, RiskAssessmentConfig):
                raise TypeError("RiskAssessmentConfig is required")
            self._config = RiskAssessmentConfig.model_validate(
                config.model_dump(mode="python", warnings="error")
            )
        except (
            AttributeError,
            PydanticSerializationError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise Stage7AssessmentError("invalid_configuration") from None
        self._completeness = CompletenessAssessmentService(self._config.completeness)
        self._risk = RiskAssessmentService(self._config)
        self._recommendation = RecommendationService()

    def _uses_config(self, config: RiskAssessmentConfig) -> bool:
        try:
            candidate = RiskAssessmentConfig.model_validate(
                config.model_dump(mode="python", warnings="error")
            )
        except (
            AttributeError,
            PydanticSerializationError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            return False
        return candidate == self._config

    def assess(
        self,
        planned_analyzer_ids: Sequence[str],
        analyzer_results: Sequence[AnalyzerResult],
        findings: Sequence[Finding],
    ) -> tuple[AnalysisCompleteness, RiskAssessment, Recommendation]:
        """Return one deterministic completeness, risk, and recommendation tuple."""
        completeness = self._completeness.assess(planned_analyzer_ids, analyzer_results)
        risk_assessment = self._risk.assess(completeness, analyzer_results, findings)
        recommendation = self._recommendation.recommend(completeness, risk_assessment)
        return completeness, risk_assessment, recommendation


def _validated_results(
    analyzer_results: Sequence[AnalyzerResult],
    *,
    expected_ids: tuple[str, ...] | None = None,
) -> tuple[AnalyzerResult, ...]:
    if expected_ids is not None:
        if any(not analyzer_id.strip() for analyzer_id in expected_ids):
            raise ValueError("planned analyzer IDs must be non-empty")
        if len(expected_ids) != len(set(expected_ids)):
            raise ValueError("planned analyzer IDs must be unique")

    validated: list[AnalyzerResult] = []
    for result in analyzer_results:
        if not isinstance(result, AnalyzerResult):
            raise TypeError("AnalyzerResult is required")
        detached = AnalyzerResult.model_validate(result.model_dump(mode="python", warnings="error"))
        if not detached.analyzer_id.strip() or not detached.analyzer_version.strip():
            raise ValueError("analyzer identity must be non-empty")
        validated.append(detached)
    ids = tuple(result.analyzer_id for result in validated)
    if len(ids) != len(set(ids)):
        raise ValueError("analyzer result IDs must be unique")
    if expected_ids is not None and ids != expected_ids:
        raise ValueError("analyzer results must match active plan order")
    return tuple(validated)


def _validated_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    validated: list[Finding] = []
    for finding in findings:
        if not isinstance(finding, Finding):
            raise TypeError("Finding is required")
        detached = Finding.model_validate(finding.model_dump(mode="python", warnings="error"))
        if any(
            not value.strip()
            for value in (
                detached.finding_id,
                detached.type,
                detached.source_analyzer_id,
                detached.source_analyzer_version,
            )
        ):
            raise ValueError("finding identity must be non-empty")
        if detached.correlation_group is not None and not detached.correlation_group.strip():
            raise ValueError("correlation_group must be null or non-empty")
        validated.append(detached)
    ids = tuple(finding.finding_id for finding in validated)
    if len(ids) != len(set(ids)):
        raise ValueError("finding IDs must be unique")
    return tuple(sorted(validated, key=lambda finding: finding.finding_id))


def _validate_finding_provenance(
    results: tuple[AnalyzerResult, ...],
    findings: tuple[Finding, ...],
) -> None:
    results_by_id = {result.analyzer_id: result for result in results}
    for finding in findings:
        source = results_by_id.get(finding.source_analyzer_id)
        if source is None or not (
            source.analyzer_version == finding.source_analyzer_version
            and source.group == finding.group
            and source.status is AnalyzerStatus.COMPLETED
            and source.applicable is True
        ):
            raise ValueError("finding provenance does not match a completed applicable result")


def _validated_completeness(value: AnalysisCompleteness) -> AnalysisCompleteness:
    if not isinstance(value, AnalysisCompleteness):
        raise TypeError("AnalysisCompleteness is required")
    return AnalysisCompleteness.model_validate(value.model_dump(mode="python", warnings="error"))


def _validated_risk(value: RiskAssessment) -> RiskAssessment:
    if not isinstance(value, RiskAssessment):
        raise TypeError("RiskAssessment is required")
    return RiskAssessment.model_validate(value.model_dump(mode="python", warnings="error"))


def _build_completeness(
    plan: tuple[str, ...],
    results: tuple[AnalyzerResult, ...],
    *,
    minimum_for_assessment: float,
) -> AnalysisCompleteness:
    by_status = {
        status: tuple(result.analyzer_id for result in results if result.status is status)
        for status in AnalyzerStatus
    }
    planned = len(plan)
    completed = len(by_status[AnalyzerStatus.COMPLETED])
    failed = len(by_status[AnalyzerStatus.ERROR])
    timed_out = len(by_status[AnalyzerStatus.TIMEOUT])
    skipped = len(by_status[AnalyzerStatus.SKIPPED])
    not_applicable = len(by_status[AnalyzerStatus.NOT_APPLICABLE])
    applicable = planned - not_applicable
    coverage_ratio = completed / applicable if applicable > 0 else 0.0

    insufficient_reasons: list[str] = []
    if planned == 0:
        insufficient_reasons.append("активный план пуст")
    if applicable == 0:
        insufficient_reasons.append("применимые анализаторы отсутствуют")
    if completed == 0:
        insufficient_reasons.append("нет завершённых анализаторов")
    if coverage_ratio < minimum_for_assessment:
        insufficient_reasons.append(f"coverage_ratio ниже порога {minimum_for_assessment}")

    if insufficient_reasons:
        status = CompletenessStatus.INSUFFICIENT
        reason = "; ".join(insufficient_reasons)
    elif (
        completed > 0
        and completed == applicable
        and failed == 0
        and timed_out == 0
        and skipped == 0
    ):
        status = CompletenessStatus.COMPLETE
        reason = "все применимые анализаторы завершены без error, timeout или skipped"
    else:
        status = CompletenessStatus.PARTIAL
        reason = "покрытие достаточно для ограниченной оценки, но анализ неполон"

    missing_statuses = {
        AnalyzerStatus.ERROR,
        AnalyzerStatus.TIMEOUT,
        AnalyzerStatus.SKIPPED,
        AnalyzerStatus.NOT_APPLICABLE,
    }
    missing_capabilities = [
        result.analyzer_id for result in results if result.status in missing_statuses
    ]
    explanation = (
        f"Выполнено {completed}/{applicable} применимых анализаторов при "
        f"planned={planned}; coverage_ratio={coverage_ratio}. "
        f"error={_format_ids(by_status[AnalyzerStatus.ERROR])}; "
        f"timeout={_format_ids(by_status[AnalyzerStatus.TIMEOUT])}; "
        f"skipped={_format_ids(by_status[AnalyzerStatus.SKIPPED])}; "
        "not_applicable="
        f"{_format_ids(by_status[AnalyzerStatus.NOT_APPLICABLE])}. "
        f"Статус {status.value}: {reason}."
    )
    return AnalysisCompleteness(
        status=status,
        planned_analyzers=planned,
        applicable_analyzers=applicable,
        completed_analyzers=completed,
        failed_analyzers=failed,
        timed_out_analyzers=timed_out,
        skipped_analyzers=skipped,
        not_applicable_analyzers=not_applicable,
        coverage_ratio=coverage_ratio,
        missing_capabilities=missing_capabilities,
        explanation=explanation,
    )


def _risk_summary(
    completeness_status: CompletenessStatus,
    final_level: RiskLevel | None,
) -> str:
    if completeness_status is CompletenessStatus.INSUFFICIENT:
        return "Полнота анализа недостаточна для формирования риск-оценки."
    if final_level is None:
        raise ValueError("assessable completeness requires final risk")
    return {
        RiskLevel.LOW: (
            "Проектная риск-оценка находится на уровне low с учётом перечисленных ограничений."
        ),
        RiskLevel.MEDIUM: ("Выявлены технические признаки, требующие дополнительной проверки."),
        RiskLevel.HIGH: (
            "Выявлены технические признаки повышенного риска, требующие проверки специалистом."
        ),
    }[final_level]


def _risk_limitations(
    completeness: AnalysisCompleteness,
    results: tuple[AnalyzerResult, ...],
    findings: tuple[Finding, ...],
) -> list[str]:
    limitations = [
        (
            "Модель score является внутренней детерминированной эвристикой проекта, "
            "а не статистической моделью."
        ),
        "Поле probability не рассчитывается и остаётся null.",
        "Оценка покрывает только текущий активный профиль анализаторов.",
    ]
    if completeness.missing_capabilities:
        limitations.append(
            f"Пробелы текущего активного профиля: {', '.join(completeness.missing_capabilities)}."
        )

    error_ids = tuple(
        result.analyzer_id for result in results if result.status is AnalyzerStatus.ERROR
    )
    timeout_ids = tuple(
        result.analyzer_id for result in results if result.status is AnalyzerStatus.TIMEOUT
    )
    skipped_ids = tuple(
        result.analyzer_id for result in results if result.status is AnalyzerStatus.SKIPPED
    )
    if error_ids or timeout_ids or skipped_ids:
        limitations.append(
            f"Не выполнены анализаторы: error={_format_ids(error_ids)}; "
            f"timeout={_format_ids(timeout_ids)}; "
            f"skipped={_format_ids(skipped_ids)}."
        )

    not_applicable_ids = tuple(
        result.analyzer_id for result in results if result.status is AnalyzerStatus.NOT_APPLICABLE
    )
    if completeness.status is not CompletenessStatus.COMPLETE or not_applicable_ids:
        limitations.append(
            f"Ограничение полноты: status={completeness.status.value}; "
            f"not_applicable={_format_ids(not_applicable_ids)}."
        )
    if not findings:
        limitations.append(
            "Отсутствие findings означает только отсутствие признаков, найденных "
            "доступными методами, и не является доказательством подлинности."
        )
    return limitations


def _format_ids(values: Sequence[str]) -> str:
    return "[" + ", ".join(values) + "]"


def _suppressed_finding_ids(bucket: _ScoringBucket) -> tuple[str, ...]:
    return tuple(
        item.finding_id
        for item in bucket.findings
        if item.finding_id != bucket.representative.finding_id
    )


_RECOMMENDATIONS: dict[
    tuple[CompletenessStatus, RiskLevel | None],
    tuple[str, tuple[str, ...], str, bool],
] = {
    (CompletenessStatus.COMPLETE, RiskLevel.LOW): (
        "no_additional_action",
        (),
        "Дополнительные действия не требуются; результат не является окончательной экспертизой.",
        False,
    ),
    (CompletenessStatus.COMPLETE, RiskLevel.MEDIUM): (
        "manual_review",
        ("verify_source_via_independent_channel",),
        "Рекомендуется ручная проверка и подтверждение источника по независимому каналу.",
        True,
    ),
    (CompletenessStatus.COMPLETE, RiskLevel.HIGH): (
        "escalate_to_security",
        (
            "manual_review",
            "verify_source_via_independent_channel",
            "send_to_incident_response",
        ),
        (
            "Рекомендуется передать результат специалисту ИБ, выполнить ручную "
            "проверку, подтвердить источник по независимому каналу и направить "
            "материал в процедуру реагирования на инциденты."
        ),
        True,
    ),
    (CompletenessStatus.PARTIAL, RiskLevel.LOW): (
        "manual_review",
        ("retry_analysis",),
        "Анализ выполнен частично: рекомендуется ручная проверка и повторный анализ.",
        True,
    ),
    (CompletenessStatus.PARTIAL, RiskLevel.MEDIUM): (
        "manual_review",
        ("verify_source_via_independent_channel", "retry_analysis"),
        (
            "Анализ выполнен частично: рекомендуется ручная проверка, подтверждение "
            "источника по независимому каналу и повторный анализ."
        ),
        True,
    ),
    (CompletenessStatus.PARTIAL, RiskLevel.HIGH): (
        "escalate_to_security",
        (
            "manual_review",
            "verify_source_via_independent_channel",
            "retry_analysis",
        ),
        (
            "Анализ выполнен частично: рекомендуется передать результат специалисту "
            "ИБ, выполнить ручную проверку, подтвердить источник по независимому "
            "каналу и повторить анализ."
        ),
        True,
    ),
    (CompletenessStatus.INSUFFICIENT, None): (
        "manual_review",
        ("retry_analysis",),
        ("Полнота недостаточна для риск-оценки: рекомендуется ручная проверка и повторный анализ."),
        True,
    ),
}
