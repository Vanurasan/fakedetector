"""Regression tests for finite JSON numbers in Stage 2 domain contracts."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.domain import (
    AnalysisCompleteness,
    AnalyzerResult,
    AudioTechnicalParameters,
    BoundingBoxLocalization,
    ErrorDetail,
    Finding,
    RiskAssessment,
    TimeIntervalLocalization,
    VideoTechnicalParameters,
)

NON_FINITE_VALUES = [float("nan"), float("inf"), float("-inf")]


def analyzer_data() -> dict[str, Any]:
    return {
        "analyzer_id": "finite_test",
        "analyzer_version": "1.0",
        "media_type": "image",
        "group": "test",
        "status": "completed",
        "applicable": True,
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "score": 0.5,
        "score_name": "finite_score",
        "summary": "Finite values.",
        "raw_metrics": {},
        "candidate_findings": [],
        "warnings": [],
        "errors": [],
    }


def finding_data() -> dict[str, Any]:
    return {
        "finding_id": "finite_001",
        "group": "test",
        "type": "finite_test",
        "severity": "weak",
        "source_analyzer_id": "finite_test",
        "source_analyzer_version": "1.0",
        "description": "Finite values.",
        "localization": None,
        "source_score": 0.5,
        "score_impact": 1.0,
        "critical_override_eligible": False,
        "correlation_group": None,
        "evidence_refs": [],
    }


def completeness_data() -> dict[str, Any]:
    return {
        "status": "complete",
        "planned_analyzers": 1,
        "applicable_analyzers": 1,
        "completed_analyzers": 1,
        "failed_analyzers": 0,
        "timed_out_analyzers": 0,
        "skipped_analyzers": 0,
        "not_applicable_analyzers": 0,
        "coverage_ratio": 1.0,
        "missing_capabilities": [],
        "explanation": "Complete.",
    }


def risk_data() -> dict[str, Any]:
    return {
        "model_id": "finite_test",
        "model_version": "1.0",
        "score": 1.0,
        "score_based_level": "low",
        "critical_override_applied": False,
        "critical_finding_ids": [],
        "final_level": "low",
        "probability": 0.25,
        "probability_method": "finite_calibration",
        "summary": "Finite values.",
        "explanation": "Finite values.",
        "limitations": [],
    }


DIRECT_FLOAT_CASES: list[tuple[str, Callable[[float], BaseModel]]] = [
    (
        "audio.duration_seconds",
        lambda value: AudioTechnicalParameters(
            duration_seconds=value,
            sample_rate_hz=48_000,
            channels=2,
            codec="aac",
        ),
    ),
    (
        "video.duration_seconds",
        lambda value: VideoTechnicalParameters(
            duration_seconds=value,
            container="mp4",
            video_codec="h264",
            width=1280,
            height=720,
            fps=25.0,
            has_audio=False,
        ),
    ),
    (
        "video.fps",
        lambda value: VideoTechnicalParameters(
            duration_seconds=1.0,
            container="mp4",
            video_codec="h264",
            width=1280,
            height=720,
            fps=value,
            has_audio=False,
        ),
    ),
    (
        "bounding_box.x",
        lambda value: BoundingBoxLocalization(
            type="bounding_box",
            x=value,
            y=0.0,
            width=1.0,
            height=1.0,
            coordinate_space="normalized",
        ),
    ),
    (
        "time_interval.start_seconds",
        lambda value: TimeIntervalLocalization(
            type="time_interval", start_seconds=value, end_seconds=1.0
        ),
    ),
    (
        "analyzer.score",
        lambda value: AnalyzerResult.model_validate({**analyzer_data(), "score": value}),
    ),
    (
        "finding.source_score",
        lambda value: Finding.model_validate({**finding_data(), "source_score": value}),
    ),
    (
        "finding.score_impact",
        lambda value: Finding.model_validate({**finding_data(), "score_impact": value}),
    ),
    (
        "completeness.coverage_ratio",
        lambda value: AnalysisCompleteness.model_validate(
            {**completeness_data(), "coverage_ratio": value}
        ),
    ),
    (
        "risk.score",
        lambda value: RiskAssessment.model_validate({**risk_data(), "score": value}),
    ),
    (
        "risk.probability",
        lambda value: RiskAssessment.model_validate({**risk_data(), "probability": value}),
    ),
]


@pytest.mark.parametrize("non_finite", NON_FINITE_VALUES)
@pytest.mark.parametrize(
    ("case_name", "factory"),
    DIRECT_FLOAT_CASES,
    ids=[case[0] for case in DIRECT_FLOAT_CASES],
)
def test_all_direct_stage2_float_fields_reject_non_finite_values(
    case_name: str,
    factory: Callable[[float], BaseModel],
    non_finite: float,
) -> None:
    del case_name
    with pytest.raises(ValidationError):
        factory(non_finite)


NESTED_NON_FINITE_FACTORIES: list[tuple[str, Callable[[Any], BaseModel]]] = [
    (
        "safe_details",
        lambda value: ErrorDetail(
            code="finite_test",
            category="internal",
            message="Safe.",
            retryable=False,
            safe_details=value,
        ),
    ),
    (
        "raw_metrics",
        lambda value: AnalyzerResult.model_validate({**analyzer_data(), "raw_metrics": value}),
    ),
    (
        "candidate_findings",
        lambda value: AnalyzerResult.model_validate(
            {**analyzer_data(), "candidate_findings": value}
        ),
    ),
]


def nested_value(field_name: str, non_finite: float, shape: str) -> Any:
    leaf: Any
    if shape == "direct":
        leaf = non_finite
    elif shape == "dict":
        leaf = {"value": non_finite}
    elif shape == "nested_dict":
        leaf = {"outer": {"inner": non_finite}}
    elif shape == "list":
        leaf = [None, True, 1, "safe", non_finite]
    else:
        leaf = {"mixed": [None, {"value": non_finite}, 1.5]}

    if field_name in {"safe_details", "raw_metrics"} and not isinstance(leaf, dict):
        return {"value": leaf}
    if field_name == "candidate_findings" and not isinstance(leaf, list):
        return [leaf]
    return leaf


@pytest.mark.parametrize("non_finite", NON_FINITE_VALUES)
@pytest.mark.parametrize("shape", ["direct", "dict", "nested_dict", "list", "mixed"])
@pytest.mark.parametrize(
    ("field_name", "factory"),
    NESTED_NON_FINITE_FACTORIES,
    ids=[case[0] for case in NESTED_NON_FINITE_FACTORIES],
)
def test_json_value_fields_recursively_reject_non_finite_numbers(
    field_name: str,
    factory: Callable[[Any], BaseModel],
    shape: str,
    non_finite: float,
) -> None:
    with pytest.raises(ValidationError):
        factory(nested_value(field_name, non_finite, shape))


def test_finite_json_numbers_and_standard_json_values_round_trip_exactly() -> None:
    structured_value = {
        "none": None,
        "bool": True,
        "int": 7,
        "float": 0.125,
        "str": "safe",
        "list": [None, False, 2, 3.5, "nested"],
        "dict": {"finite": -42.25},
    }
    error = ErrorDetail(
        code="finite_test",
        category="internal",
        message="Safe.",
        retryable=False,
        safe_details=structured_value,
    )
    analyzer = AnalyzerResult.model_validate(
        {
            **analyzer_data(),
            "score": -12.5,
            "raw_metrics": structured_value,
            "candidate_findings": [structured_value],
        }
    )

    restored_error = ErrorDetail.model_validate_json(error.model_dump_json())
    restored_analyzer = AnalyzerResult.model_validate_json(analyzer.model_dump_json())

    assert restored_error == error
    assert restored_analyzer == analyzer
    assert json.loads(error.model_dump_json())["safe_details"] == structured_value


@pytest.mark.parametrize("non_finite", NON_FINITE_VALUES)
@pytest.mark.parametrize(
    ("field_name", "model_factory"),
    [
        (
            "duration_seconds",
            lambda: AudioTechnicalParameters(
                duration_seconds=1.0,
                sample_rate_hz=48_000,
                channels=2,
                codec="aac",
            ),
        ),
        ("score", lambda: RiskAssessment.model_validate(risk_data())),
    ],
    ids=["non_nullable_audio_duration", "nullable_risk_score"],
)
def test_model_dump_json_rejects_non_finite_direct_mutation(
    field_name: str,
    model_factory: Callable[[], BaseModel],
    non_finite: float,
) -> None:
    model = model_factory()
    setattr(model, field_name, non_finite)

    with pytest.raises(PydanticSerializationError, match="JSON numbers must be finite"):
        model.model_dump_json()


@pytest.mark.parametrize("non_finite", NON_FINITE_VALUES)
@pytest.mark.parametrize(
    "mutation",
    [
        lambda error, _analyzer, value: error.safe_details.__setitem__("x", value),
        lambda error, _analyzer, value: error.safe_details.__setitem__(
            "deep", {"a": [{"b": value}]}
        ),
        lambda _error, analyzer, value: analyzer.raw_metrics.__setitem__("x", value),
        lambda _error, analyzer, value: analyzer.raw_metrics.__setitem__(
            "deep", {"a": [{"b": value}]}
        ),
        lambda _error, analyzer, value: analyzer.candidate_findings.append({"x": value}),
        lambda _error, analyzer, value: analyzer.candidate_findings.append(
            {"a": [{"b": value}]}
        ),
    ],
    ids=[
        "safe_details_direct",
        "safe_details_deep",
        "raw_metrics_direct",
        "raw_metrics_deep",
        "candidate_findings_direct",
        "candidate_findings_deep",
    ],
)
def test_model_dump_json_rejects_non_finite_in_place_nested_mutation(
    mutation: Callable[[ErrorDetail, AnalyzerResult, float], object],
    non_finite: float,
) -> None:
    error = ErrorDetail(
        code="finite_test",
        category="internal",
        message="Safe.",
        retryable=False,
    )
    analyzer = AnalyzerResult.model_validate(analyzer_data())
    mutation(error, analyzer, non_finite)
    mutated_model = error if error.safe_details else analyzer

    with pytest.raises(PydanticSerializationError, match="JSON numbers must be finite"):
        mutated_model.model_dump_json()


@pytest.mark.parametrize("non_finite", NON_FINITE_VALUES)
def test_model_dump_json_checks_nested_domain_models_after_mutation(non_finite: float) -> None:
    analyzer = AnalyzerResult.model_validate(analyzer_data())
    error = ErrorDetail(
        code="finite_test",
        category="internal",
        message="Safe.",
        retryable=False,
        safe_details={"finite": 1.0},
    )
    analyzer.errors.append(error)
    error.safe_details["deep"] = {"a": [{"b": non_finite}]}

    with pytest.raises(PydanticSerializationError, match="JSON numbers must be finite"):
        analyzer.model_dump_json()


def test_model_dump_json_preserves_signature_options_and_finite_round_trip() -> None:
    assessment = RiskAssessment.model_validate(risk_data())

    dumped = assessment.model_dump_json(indent=2, ensure_ascii=True, exclude_none=True)
    restored = RiskAssessment.model_validate_json(dumped)

    assert restored == assessment
    assert json.loads(dumped)["probability"] == 0.25
