"""Contract tests for the RiskAssessment domain model."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from fakedetector.domain import RiskAssessment, RiskLevel


def risk_data() -> dict[str, Any]:
    """Return a complete declared risk assessment."""
    return {
        "model_id": "score_model_v1",
        "model_version": "0.1.0",
        "score": 125.5,
        "score_based_level": "medium",
        "critical_override_applied": False,
        "critical_finding_ids": [],
        "final_level": "medium",
        "probability": None,
        "probability_method": None,
        "summary": "Выявлены значимые признаки.",
        "explanation": "Оценка объявлена внешним алгоритмом.",
        "limitations": [],
    }


@pytest.mark.parametrize("score", [125.5, -4.0, None])
def test_risk_assessment_accepts_score_without_probability_range(score: float | None) -> None:
    assessment = RiskAssessment.model_validate({**risk_data(), "score": score})

    assert assessment.score == score


def test_risk_assessment_converts_string_levels_to_enums() -> None:
    assessment = RiskAssessment.model_validate(risk_data())

    assert assessment.score_based_level is RiskLevel.MEDIUM
    assert assessment.final_level is RiskLevel.MEDIUM


@pytest.mark.parametrize("field", ["score_based_level", "final_level"])
def test_risk_assessment_rejects_unknown_level(field: str) -> None:
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate({**risk_data(), field: "critical"})


def test_probability_none_is_allowed_and_not_derived_from_score() -> None:
    assessment = RiskAssessment.model_validate({**risk_data(), "score": 0.99})

    assert assessment.probability is None
    assert assessment.probability_method is None


@pytest.mark.parametrize("method", [None, "", "   "])
def test_probability_requires_nonempty_method(method: str | None) -> None:
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate(
            {**risk_data(), "probability": 0.75, "probability_method": method}
        )


def test_probability_with_method_is_allowed() -> None:
    assessment = RiskAssessment.model_validate(
        {**risk_data(), "probability": 0.75, "probability_method": "calibration_v1"}
    )

    assert assessment.probability == 0.75
    assert assessment.probability_method == "calibration_v1"


def test_disabled_critical_override_accepts_empty_finding_ids() -> None:
    assessment = RiskAssessment.model_validate(risk_data())

    assert assessment.critical_override_applied is False
    assert assessment.critical_finding_ids == []


def test_applied_critical_override_requires_finding_ids() -> None:
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate({**risk_data(), "critical_override_applied": True})


def test_applied_critical_override_accepts_finding_ids_without_calculating_level() -> None:
    assessment = RiskAssessment.model_validate(
        {
            **risk_data(),
            "critical_override_applied": True,
            "critical_finding_ids": ["finding_0001"],
            "final_level": None,
        }
    )

    assert assessment.critical_finding_ids == ["finding_0001"]
    assert assessment.final_level is None


def test_risk_assessment_does_not_create_final_level() -> None:
    assessment = RiskAssessment.model_validate(
        {**risk_data(), "score": 1_000_000, "score_based_level": "high", "final_level": None}
    )

    assert assessment.final_level is None


def test_risk_assessment_requires_every_field() -> None:
    for field in risk_data():
        data = risk_data()
        del data[field]
        with pytest.raises(ValidationError):
            RiskAssessment.model_validate(data)


def test_risk_assessment_json_dump_and_round_trip() -> None:
    assessment = RiskAssessment.model_validate(risk_data())
    dumped = assessment.model_dump(mode="json")
    restored = RiskAssessment.model_validate_json(assessment.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == assessment


def test_risk_assessment_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate({**risk_data(), "thresholds": {"high": 61}})
