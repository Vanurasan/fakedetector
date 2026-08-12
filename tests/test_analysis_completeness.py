"""Contract tests for the AnalysisCompleteness domain model."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

import fakedetector.domain as domain
from fakedetector.domain import AnalysisCompleteness, CompletenessStatus
from fakedetector.domain.models import AnalysisCompleteness as ModelsAnalysisCompleteness

EXPECTED_DOMAIN_EXPORTS = [
    "AnalysisCompleteness",
    "AnalysisStatus",
    "AnalyzerResult",
    "AnalyzerStatus",
    "AudioTechnicalParameters",
    "BoundingBoxLocalization",
    "CleanupStatus",
    "CompletenessStatus",
    "ErrorDetail",
    "FileLocalization",
    "Finding",
    "FindingSeverity",
    "FrameIntervalLocalization",
    "ImageTechnicalParameters",
    "InputFileDescriptor",
    "Localization",
    "MediaType",
    "ProcessingStage",
    "RiskLevel",
    "SourceChannel",
    "SourceContext",
    "TimeIntervalLocalization",
    "ValidatedFileDescriptor",
    "ValidationCheck",
    "ValidationResult",
    "VideoTechnicalParameters",
]

COUNTER_FIELDS = [
    "planned_analyzers",
    "applicable_analyzers",
    "completed_analyzers",
    "failed_analyzers",
    "timed_out_analyzers",
    "skipped_analyzers",
    "not_applicable_analyzers",
]


def completeness_data() -> dict[str, Any]:
    """Return a complete declared partial-analysis coverage result."""
    return {
        "status": "partial",
        "planned_analyzers": 5,
        "applicable_analyzers": 4,
        "completed_analyzers": 3,
        "failed_analyzers": 1,
        "timed_out_analyzers": 0,
        "skipped_analyzers": 1,
        "not_applicable_analyzers": 0,
        "coverage_ratio": 0.75,
        "missing_capabilities": ["synthetic_speech_detection"],
        "explanation": "Один применимый анализатор завершился ошибкой.",
    }


@pytest.mark.parametrize("status", list(CompletenessStatus))
def test_analysis_completeness_accepts_every_status(status: CompletenessStatus) -> None:
    completeness = AnalysisCompleteness.model_validate(
        {**completeness_data(), "status": status.value}
    )

    assert completeness.status is status


def test_analysis_completeness_converts_string_status_to_enum() -> None:
    completeness = AnalysisCompleteness.model_validate(completeness_data())

    assert completeness.status is CompletenessStatus.PARTIAL


def test_analysis_completeness_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        AnalysisCompleteness.model_validate({**completeness_data(), "status": "failed"})


@pytest.mark.parametrize("missing_field", completeness_data())
def test_analysis_completeness_requires_every_field(missing_field: str) -> None:
    data = completeness_data()
    del data[missing_field]

    with pytest.raises(ValidationError):
        AnalysisCompleteness.model_validate(data)


@pytest.mark.parametrize("counter_field", COUNTER_FIELDS)
def test_analysis_completeness_rejects_negative_counters(counter_field: str) -> None:
    with pytest.raises(ValidationError):
        AnalysisCompleteness.model_validate(
            {**completeness_data(), counter_field: -1}
        )


@pytest.mark.parametrize("coverage_ratio", [-0.001, 1.001])
def test_analysis_completeness_rejects_ratio_outside_unit_interval(
    coverage_ratio: float,
) -> None:
    with pytest.raises(ValidationError):
        AnalysisCompleteness.model_validate(
            {**completeness_data(), "coverage_ratio": coverage_ratio}
        )


@pytest.mark.parametrize("coverage_ratio", [0.0, 1.0])
def test_analysis_completeness_accepts_ratio_boundaries(coverage_ratio: float) -> None:
    completeness = AnalysisCompleteness.model_validate(
        {**completeness_data(), "coverage_ratio": coverage_ratio}
    )

    assert completeness.coverage_ratio == coverage_ratio


def test_analysis_completeness_does_not_calculate_or_change_ratio() -> None:
    completeness = AnalysisCompleteness.model_validate(
        {
            **completeness_data(),
            "applicable_analyzers": 4,
            "completed_analyzers": 4,
            "coverage_ratio": 0.125,
        }
    )

    assert completeness.coverage_ratio == 0.125


def test_analysis_completeness_does_not_derive_status_from_counters() -> None:
    completeness = AnalysisCompleteness.model_validate(
        {
            **completeness_data(),
            "status": "insufficient",
            "applicable_analyzers": 4,
            "completed_analyzers": 4,
            "coverage_ratio": 1.0,
        }
    )

    assert completeness.status is CompletenessStatus.INSUFFICIENT


def test_analysis_completeness_json_dump_and_round_trip() -> None:
    completeness = AnalysisCompleteness.model_validate(completeness_data())

    dumped = completeness.model_dump(mode="json")
    restored = AnalysisCompleteness.model_validate_json(completeness.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == completeness
    assert restored.status is CompletenessStatus.PARTIAL


def test_analysis_completeness_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        AnalysisCompleteness.model_validate(
            {**completeness_data(), "algorithm_version": "not-contracted"}
        )


def test_analysis_completeness_is_available_by_direct_domain_import() -> None:
    assert AnalysisCompleteness is ModelsAnalysisCompleteness
    assert domain.AnalysisCompleteness is ModelsAnalysisCompleteness


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
