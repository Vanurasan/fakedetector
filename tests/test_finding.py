"""Contract tests for Finding and canonical localization models."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

import fakedetector.domain as domain
from fakedetector.domain import (
    BoundingBoxLocalization,
    FileLocalization,
    Finding,
    FindingSeverity,
    FrameIntervalLocalization,
    Localization,
    TimeIntervalLocalization,
)
from fakedetector.domain.models import (
    BoundingBoxLocalization as ModelsBoundingBoxLocalization,
)
from fakedetector.domain.models import FileLocalization as ModelsFileLocalization
from fakedetector.domain.models import Finding as ModelsFinding
from fakedetector.domain.models import (
    FrameIntervalLocalization as ModelsFrameIntervalLocalization,
)
from fakedetector.domain.models import Localization as ModelsLocalization
from fakedetector.domain.models import (
    TimeIntervalLocalization as ModelsTimeIntervalLocalization,
)

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

LOCALIZATION_CASES: list[tuple[dict[str, Any], type[Any]]] = [
    ({"type": "file"}, FileLocalization),
    (
        {
            "type": "bounding_box",
            "x": 0.21,
            "y": 0.15,
            "width": 0.34,
            "height": 0.42,
            "coordinate_space": "normalized",
        },
        BoundingBoxLocalization,
    ),
    (
        {"type": "time_interval", "start_seconds": 12.1, "end_seconds": 19.5},
        TimeIntervalLocalization,
    ),
    (
        {"type": "frame_interval", "start_frame": 302, "end_frame": 487},
        FrameIntervalLocalization,
    ),
]


def finding_data(localization: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a complete canonical finding."""
    return {
        "finding_id": "finding_0004",
        "group": "multimodal",
        "type": "audio_video_desynchronization",
        "severity": "critical",
        "source_analyzer_id": "audio_video_sync_analyzer",
        "source_analyzer_version": "1.0.0",
        "description": "Выявлено устойчивое несоответствие.",
        "localization": localization,
        "source_score": 0.94,
        "score_impact": None,
        "critical_override_eligible": False,
        "correlation_group": "face_sync_segment_1",
        "evidence_refs": [],
    }


@pytest.mark.parametrize(("data", "expected_type"), LOCALIZATION_CASES)
def test_all_canonical_localizations_validate(
    data: dict[str, Any],
    expected_type: type[Any],
) -> None:
    localization = TypeAdapter(Localization).validate_python(data)

    assert isinstance(localization, expected_type)


@pytest.mark.parametrize(("data", "expected_type"), LOCALIZATION_CASES)
def test_finding_discriminated_union_selects_variant_by_type(
    data: dict[str, Any],
    expected_type: type[Any],
) -> None:
    finding = Finding.model_validate(finding_data(data.copy()))

    assert isinstance(finding.localization, expected_type)


def test_localization_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(finding_data({"type": "polygon", "points": []}))


@pytest.mark.parametrize(("data", "_expected_type"), LOCALIZATION_CASES)
def test_localization_variants_reject_extra_fields(
    data: dict[str, Any],
    _expected_type: type[Any],
) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Localization).validate_python({**data, "unknown": True})


def test_bounding_box_accepts_zero_and_one_boundaries() -> None:
    localization = BoundingBoxLocalization(
        type="bounding_box",
        x=0,
        y=1,
        width=1,
        height=0,
        coordinate_space="normalized",
    )

    assert localization.x == 0
    assert localization.y == 1


def test_bounding_box_does_not_add_extent_sum_constraint() -> None:
    localization = BoundingBoxLocalization(
        type="bounding_box",
        x=0.8,
        y=0.9,
        width=0.7,
        height=0.6,
        coordinate_space="normalized",
    )

    assert localization.x + localization.width > 1
    assert localization.y + localization.height > 1


@pytest.mark.parametrize("field_name", ["x", "y", "width", "height"])
@pytest.mark.parametrize("invalid_value", [-0.001, 1.001])
def test_bounding_box_rejects_values_outside_normalized_range(
    field_name: str,
    invalid_value: float,
) -> None:
    data = LOCALIZATION_CASES[1][0].copy()
    data[field_name] = invalid_value

    with pytest.raises(ValidationError):
        BoundingBoxLocalization.model_validate(data)


def test_bounding_box_rejects_non_normalized_coordinate_space() -> None:
    data = {**LOCALIZATION_CASES[1][0], "coordinate_space": "pixels"}

    with pytest.raises(ValidationError):
        BoundingBoxLocalization.model_validate(data)


@pytest.mark.parametrize(
    ("model_type", "data"),
    [
        (
            TimeIntervalLocalization,
            {"type": "time_interval", "start_seconds": 0, "end_seconds": 0},
        ),
        (
            FrameIntervalLocalization,
            {"type": "frame_interval", "start_frame": 0, "end_frame": 0},
        ),
    ],
)
def test_interval_localizations_accept_equal_nonnegative_boundaries(
    model_type: type[Any],
    data: dict[str, Any],
) -> None:
    assert model_type.model_validate(data)


@pytest.mark.parametrize(
    ("model_type", "data"),
    [
        (
            TimeIntervalLocalization,
            {"type": "time_interval", "start_seconds": 2.0, "end_seconds": 1.0},
        ),
        (
            FrameIntervalLocalization,
            {"type": "frame_interval", "start_frame": 2, "end_frame": 1},
        ),
    ],
)
def test_interval_localizations_reject_start_after_end(
    model_type: type[Any],
    data: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(data)


@pytest.mark.parametrize(
    ("model_type", "data"),
    [
        (
            TimeIntervalLocalization,
            {"type": "time_interval", "start_seconds": -1.0, "end_seconds": 1.0},
        ),
        (
            TimeIntervalLocalization,
            {"type": "time_interval", "start_seconds": 0.0, "end_seconds": -1.0},
        ),
        (
            FrameIntervalLocalization,
            {"type": "frame_interval", "start_frame": -1, "end_frame": 1},
        ),
        (
            FrameIntervalLocalization,
            {"type": "frame_interval", "start_frame": 0, "end_frame": -1},
        ),
    ],
)
def test_interval_localizations_reject_negative_start_and_end(
    model_type: type[Any],
    data: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(data)


@pytest.mark.parametrize(
    ("localization", "expected_type"),
    [*LOCALIZATION_CASES, (None, type(None))],
)
def test_finding_accepts_every_localization_and_null(
    localization: dict[str, Any] | None,
    expected_type: type[Any],
) -> None:
    finding = Finding.model_validate(finding_data(localization))

    assert isinstance(finding.localization, expected_type)


@pytest.mark.parametrize("missing_field", finding_data())
def test_finding_requires_every_field_including_nullable(missing_field: str) -> None:
    data = finding_data()
    del data[missing_field]

    with pytest.raises(ValidationError):
        Finding.model_validate(data)


def test_finding_accepts_explicit_null_contract_fields() -> None:
    finding = Finding.model_validate(
        {
            **finding_data(),
            "localization": None,
            "source_score": None,
            "score_impact": None,
            "correlation_group": None,
        }
    )

    assert finding.localization is None
    assert finding.source_score is None
    assert finding.score_impact is None
    assert finding.correlation_group is None


def test_finding_converts_string_severity_to_enum() -> None:
    finding = Finding.model_validate(finding_data())

    assert finding.severity is FindingSeverity.CRITICAL


def test_finding_rejects_unknown_severity() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate({**finding_data(), "severity": "high"})


def test_high_source_score_does_not_create_critical_finding_automatically() -> None:
    finding = Finding.model_validate(
        {
            **finding_data(),
            "severity": "weak",
            "source_score": 1_000_000.0,
            "critical_override_eligible": False,
        }
    )

    assert finding.severity is FindingSeverity.WEAK
    assert finding.critical_override_eligible is False


def test_finding_json_dump_and_round_trip() -> None:
    finding = Finding.model_validate(finding_data(LOCALIZATION_CASES[2][0].copy()))

    dumped = finding.model_dump(mode="json")
    restored = Finding.model_validate_json(finding.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == finding
    assert isinstance(restored.localization, TimeIntervalLocalization)


def test_finding_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate({**finding_data(), "final_risk": "high"})


def test_finding_models_are_available_by_direct_domain_import() -> None:
    assert BoundingBoxLocalization is ModelsBoundingBoxLocalization
    assert FileLocalization is ModelsFileLocalization
    assert Finding is ModelsFinding
    assert FrameIntervalLocalization is ModelsFrameIntervalLocalization
    assert Localization is ModelsLocalization
    assert TimeIntervalLocalization is ModelsTimeIntervalLocalization
    assert domain.BoundingBoxLocalization is ModelsBoundingBoxLocalization
    assert domain.FileLocalization is ModelsFileLocalization
    assert domain.Finding is ModelsFinding
    assert domain.FrameIntervalLocalization is ModelsFrameIntervalLocalization
    assert domain.Localization is ModelsLocalization
    assert domain.TimeIntervalLocalization is ModelsTimeIntervalLocalization


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
