"""Contract tests for the minimal safe AnalysisResultSummary projection."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

import fakedetector.domain as domain
from fakedetector.domain import (
    AnalysisResult,
    AnalysisResultSummary,
    AnalysisStatus,
    CompletenessStatus,
    MediaType,
    RiskLevel,
)
from fakedetector.domain.models import AnalysisResultSummary as ModelsAnalysisResultSummary

SUMMARY_FIELDS = [
    "analysis_id",
    "created_at",
    "updated_at",
    "status",
    "media_type",
    "final_risk_level",
    "completeness_status",
]


def summary_data() -> dict[str, Any]:
    """Return all fields of one canonical summary."""
    return {
        "analysis_id": "summary-001",
        "created_at": datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 12, 10, 5, tzinfo=UTC),
        "status": "partial",
        "media_type": "video",
        "final_risk_level": "medium",
        "completeness_status": "partial",
    }


def result_data(*, validated_file: bool) -> dict[str, Any]:
    """Return a complete result suitable for testing summary projection."""
    created_at = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    updated_at = datetime(2026, 8, 12, 9, 3, tzinfo=UTC)
    input_file: dict[str, Any] = {
        "original_name": "misleading-audio.mp3",
        "declared_content_type": "audio/mpeg",
        "size_bytes": 1234,
        "received_at": created_at,
    }
    validated_descriptor: dict[str, Any] = {
        "original_name": "misleading-audio.mp3",
        "extension": "jpg",
        "declared_mime_type": "audio/mpeg",
        "detected_mime_type": "image/jpeg",
        "media_type": "image",
        "size_bytes": 1234,
        "sha256": "summary-test-digest",
        "signature_match": True,
        "safe_read": True,
        "technical_parameters": {
            "width": 100,
            "height": 100,
            "format": "JPEG",
            "color_mode": "RGB",
            "frame_count": None,
            "has_metadata": False,
        },
    }
    return {
        "schema_version": "1.0",
        "analysis_id": "projection-001",
        "created_at": created_at,
        "updated_at": updated_at,
        "status": "completed",
        "stage": "finished",
        "source": {
            "channel": "api",
            "connector": "mail_connector",
            "external_system": "private-system",
            "external_reference": "private-reference",
        },
        "file": validated_descriptor if validated_file else input_file,
        "processing": {
            "queued_at": created_at,
            "started_at": created_at,
            "finished_at": updated_at,
            "duration_ms": 180_000,
            "config_snapshot_id": "config-test",
            "application_version": "0.1.0",
        },
        "analyzers": [],
        "findings": [],
        "completeness": {
            "status": "complete",
            "planned_analyzers": 99,
            "applicable_analyzers": 98,
            "completed_analyzers": 1,
            "failed_analyzers": 97,
            "timed_out_analyzers": 0,
            "skipped_analyzers": 1,
            "not_applicable_analyzers": 1,
            "coverage_ratio": 0.01,
            "missing_capabilities": ["private-capability"],
            "explanation": "This value must not enter the summary.",
        },
        "risk_assessment": {
            "model_id": "score-model",
            "model_version": "1.0",
            "score": 999,
            "score_based_level": "high",
            "critical_override_applied": False,
            "critical_finding_ids": [],
            "final_level": "medium",
            "probability": None,
            "probability_method": None,
            "summary": "Private risk text.",
            "explanation": "Private explanation.",
            "limitations": ["private limitation"],
        },
        "recommendation": {
            "primary_action": "manual_review",
            "additional_actions": [],
            "text": "Private recommendation.",
            "requires_manual_review": True,
        },
        "cleanup": {
            "status": "completed",
            "original_file_deleted": True,
            "intermediate_files_deleted": True,
            "quarantine_used": False,
            "finished_at": updated_at,
            "errors": [],
        },
        "warnings": ["Private warning."],
        "errors": [],
    }


def test_summary_has_exact_required_fields_without_defaults() -> None:
    assert list(AnalysisResultSummary.model_fields) == SUMMARY_FIELDS
    assert all(field.is_required() for field in AnalysisResultSummary.model_fields.values())


@pytest.mark.parametrize("missing_field", SUMMARY_FIELDS)
def test_summary_requires_every_field_including_nullable(missing_field: str) -> None:
    data = summary_data()
    del data[missing_field]

    with pytest.raises(ValidationError):
        AnalysisResultSummary.model_validate(data)


def test_summary_accepts_explicit_nullable_values() -> None:
    summary = AnalysisResultSummary.model_validate(
        {**summary_data(), "media_type": None, "final_risk_level": None}
    )

    assert summary.media_type is None
    assert summary.final_risk_level is None


def test_summary_converts_strings_to_canonical_enums() -> None:
    summary = AnalysisResultSummary.model_validate(summary_data())

    assert summary.status is AnalysisStatus.PARTIAL
    assert summary.media_type is MediaType.VIDEO
    assert summary.final_risk_level is RiskLevel.MEDIUM
    assert summary.completeness_status is CompletenessStatus.PARTIAL


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "done"),
        ("media_type", "document"),
        ("final_risk_level", "critical"),
        ("completeness_status", "failed"),
    ],
)
def test_summary_rejects_unknown_enum_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        AnalysisResultSummary.model_validate({**summary_data(), field: value})


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
@pytest.mark.parametrize(
    "invalid_time",
    [
        datetime(2026, 8, 12, 10, 0),
        datetime(2026, 8, 12, 13, 0, tzinfo=timezone(timedelta(hours=3))),
    ],
)
def test_summary_rejects_naive_and_non_utc_times(field: str, invalid_time: datetime) -> None:
    with pytest.raises(ValidationError):
        AnalysisResultSummary.model_validate({**summary_data(), field: invalid_time})


def test_summary_serializes_utc_timestamps_with_z_and_round_trips() -> None:
    summary = AnalysisResultSummary.model_validate(summary_data())
    dumped = summary.model_dump(mode="json")
    restored = AnalysisResultSummary.model_validate_json(summary.model_dump_json())

    assert dumped["created_at"].endswith("Z")
    assert dumped["updated_at"].endswith("Z")
    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == summary


def test_summary_rejects_extra_fields_and_omits_full_result_fields() -> None:
    with pytest.raises(ValidationError):
        AnalysisResultSummary.model_validate({**summary_data(), "schema_version": "1.0"})
    with pytest.raises(ValidationError):
        AnalysisResultSummary.model_validate({**summary_data(), "stage": "finished"})

    assert set(AnalysisResultSummary.model_validate(summary_data()).model_dump()) == set(
        SUMMARY_FIELDS
    )


@pytest.mark.parametrize(
    ("validated_file", "expected_media_type"),
    [(True, MediaType.IMAGE), (False, None)],
)
def test_summary_projection_copies_only_contracted_sources(
    validated_file: bool,
    expected_media_type: MediaType | None,
) -> None:
    result = AnalysisResult.model_validate(result_data(validated_file=validated_file))

    summary = AnalysisResultSummary.from_result(result)

    assert summary == AnalysisResultSummary(
        analysis_id=result.analysis_id,
        created_at=result.created_at,
        updated_at=result.updated_at,
        status=result.status,
        media_type=expected_media_type,
        final_risk_level=RiskLevel.MEDIUM,
        completeness_status=CompletenessStatus.COMPLETE,
    )
    assert summary.final_risk_level is not result.risk_assessment.score_based_level
    serialized = summary.model_dump_json()
    for sensitive_value in (
        "misleading-audio.mp3",
        "audio/mpeg",
        "private-system",
        "private-reference",
        "private-capability",
        "Private risk text",
        "Private recommendation",
        "Private warning",
    ):
        assert sensitive_value not in serialized


def test_summary_projection_preserves_absent_final_risk_without_deriving_low() -> None:
    data = result_data(validated_file=False)
    data["status"] = "failed"
    data["risk_assessment"]["final_level"] = None
    data["completeness"]["status"] = "not_assessed"
    data["errors"] = [
        {
            "code": "internal_error",
            "category": "internal",
            "message": "Safe failure.",
            "retryable": False,
        }
    ]
    result = AnalysisResult.model_validate(data)

    summary = AnalysisResultSummary.from_result(result)

    assert summary.final_risk_level is None
    assert summary.completeness_status is CompletenessStatus.NOT_ASSESSED


def test_summary_is_available_by_direct_domain_import_and_exact_all() -> None:
    assert AnalysisResultSummary is ModelsAnalysisResultSummary
    assert domain.AnalysisResultSummary is ModelsAnalysisResultSummary
    assert domain.__all__ == [
        "AnalysisCompleteness",
        "AnalysisResult",
        "AnalysisResultSummary",
        "AnalysisStatus",
        "AnalyzerResult",
        "AnalyzerStatus",
        "AudioTechnicalParameters",
        "BoundingBoxLocalization",
        "CleanupResult",
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
        "Recommendation",
        "RiskAssessment",
        "RiskLevel",
        "SourceChannel",
        "SourceContext",
        "TimeIntervalLocalization",
        "ValidatedFileDescriptor",
        "ValidationCheck",
        "ValidationResult",
        "VideoTechnicalParameters",
    ]
