"""Contract tests for the versioned top-level AnalysisResult model."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

import fakedetector.domain as domain
from fakedetector.domain import (
    AnalysisCompleteness,
    AnalysisResult,
    AnalysisStatus,
    AnalyzerResult,
    CleanupResult,
    Finding,
    InputFileDescriptor,
    ProcessingStage,
    Recommendation,
    RiskAssessment,
    SourceContext,
    ValidatedFileDescriptor,
)
from fakedetector.domain.models import AnalysisProcessing
from fakedetector.domain.models import AnalysisResult as ModelsAnalysisResult

EXPECTED_DOMAIN_EXPORTS = [
    "AnalysisCompleteness",
    "AnalysisResult",
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


def error_data(code: str = "internal_error", category: str = "internal") -> dict[str, Any]:
    """Return a safe top-level error."""
    return {
        "code": code,
        "category": category,
        "message": "Безопасно отражённая причина результата.",
        "retryable": False,
        "field": None,
        "analyzer_id": None,
        "safe_details": {},
    }


def input_file_data() -> dict[str, Any]:
    """Return the file descriptor available before successful validation."""
    return {
        "original_name": "message.jpg",
        "declared_content_type": "image/jpeg",
        "size_bytes": 2048,
        "received_at": datetime(2026, 7, 24, 14, 35, 21, tzinfo=UTC),
    }


def validated_file_data() -> dict[str, Any]:
    """Return a validated image descriptor used by completed analysis."""
    return {
        "original_name": "message.jpg",
        "extension": "jpg",
        "declared_mime_type": "image/jpeg",
        "detected_mime_type": "image/jpeg",
        "media_type": "image",
        "size_bytes": 2048,
        "sha256": "canonical-test-digest",
        "signature_match": True,
        "safe_read": True,
        "technical_parameters": {
            "width": 1280,
            "height": 720,
            "format": "JPEG",
            "color_mode": "RGB",
            "frame_count": None,
            "has_metadata": False,
        },
    }


def processing_data() -> dict[str, Any]:
    """Return complete processing timing and version context."""
    return {
        "queued_at": datetime(2026, 7, 24, 14, 35, 22, tzinfo=UTC),
        "started_at": datetime(2026, 7, 24, 14, 35, 23, tzinfo=UTC),
        "finished_at": datetime(2026, 7, 24, 14, 36, 18, tzinfo=UTC),
        "duration_ms": 55_000,
        "config_snapshot_id": "config_sha256_prefix",
        "application_version": "0.1.0",
    }


def analyzer_data() -> dict[str, Any]:
    """Return a successful analyzer result embedded as a nested dictionary."""
    return {
        "analyzer_id": "metadata_analyzer",
        "analyzer_version": "1.0.0",
        "media_type": "image",
        "group": "metadata",
        "status": "completed",
        "applicable": True,
        "started_at": datetime(2026, 7, 24, 14, 35, 25, tzinfo=UTC),
        "finished_at": datetime(2026, 7, 24, 14, 35, 26, tzinfo=UTC),
        "duration_ms": 1000,
        "score": 4.2,
        "score_name": "model_logit",
        "summary": "Проверка завершена.",
        "raw_metrics": {},
        "candidate_findings": [],
        "warnings": [],
        "errors": [],
    }


def finding_data() -> dict[str, Any]:
    """Return one normalized finding."""
    return {
        "finding_id": "finding_0001",
        "group": "metadata",
        "type": "metadata_anomaly",
        "severity": "significant",
        "source_analyzer_id": "metadata_analyzer",
        "source_analyzer_version": "1.0.0",
        "description": "Выявлена аномалия метаданных.",
        "localization": {"type": "file"},
        "source_score": 4.2,
        "score_impact": 25.0,
        "critical_override_eligible": False,
        "correlation_group": None,
        "evidence_refs": [],
    }


def completeness_data(status: str = "complete") -> dict[str, Any]:
    """Return declared completeness without calculating it in the result model."""
    return {
        "status": status,
        "planned_analyzers": 1,
        "applicable_analyzers": 1,
        "completed_analyzers": 1,
        "failed_analyzers": 0,
        "timed_out_analyzers": 0,
        "skipped_analyzers": 0,
        "not_applicable_analyzers": 0,
        "coverage_ratio": 1.0,
        "missing_capabilities": [],
        "explanation": "Все обязательные применимые проверки выполнены.",
    }


def risk_data(final_level: str | None = "medium") -> dict[str, Any]:
    """Return a declared assessment without invoking a risk algorithm."""
    return {
        "model_id": "score_model_v1",
        "model_version": "0.1.0",
        "score": 25.0,
        "score_based_level": "medium" if final_level is not None else None,
        "critical_override_applied": False,
        "critical_finding_ids": [],
        "final_level": final_level,
        "probability": None,
        "probability_method": None,
        "summary": "Объявленная риск-оценка.",
        "explanation": "Результат внешнего алгоритма агрегации.",
        "limitations": [],
    }


def recommendation_data() -> dict[str, Any]:
    """Return a canonical recommendation."""
    return {
        "primary_action": "manual_review",
        "additional_actions": ["verify_source"],
        "text": "Рекомендуется ручная проверка.",
        "requires_manual_review": True,
    }


def cleanup_data() -> dict[str, Any]:
    """Return the factual cleanup block."""
    return {
        "status": "completed",
        "original_file_deleted": True,
        "intermediate_files_deleted": True,
        "quarantine_used": False,
        "finished_at": datetime(2026, 7, 24, 14, 36, 17, tzinfo=UTC),
        "errors": [],
    }


def completed_result_data() -> dict[str, Any]:
    """Return a complete valid AnalysisResult as nested dictionaries."""
    return {
        "schema_version": "1.0",
        "analysis_id": "analysis-opaque-001",
        "created_at": datetime(2026, 7, 24, 14, 35, 22, tzinfo=UTC),
        "updated_at": datetime(2026, 7, 24, 14, 36, 18, tzinfo=UTC),
        "status": "completed",
        "stage": "finished",
        "source": {"channel": "api"},
        "file": validated_file_data(),
        "processing": processing_data(),
        "analyzers": [analyzer_data()],
        "findings": [finding_data()],
        "completeness": completeness_data(),
        "risk_assessment": risk_data(),
        "recommendation": recommendation_data(),
        "cleanup": cleanup_data(),
        "warnings": [],
        "errors": [],
    }


def rejected_result_data() -> dict[str, Any]:
    """Return a structurally valid rejected terminal result."""
    data = completed_result_data()
    data.update(
        {
            "status": "rejected",
            "stage": "finished",
            "file": input_file_data(),
            "analyzers": [],
            "findings": [],
            "completeness": completeness_data("not_assessed"),
            "risk_assessment": risk_data(None),
            "errors": [error_data("file_signature_mismatch", "validation")],
        }
    )
    return data


def failed_result_data() -> dict[str, Any]:
    """Return a structurally valid failed terminal result."""
    data = completed_result_data()
    data.update(
        {
            "status": "failed",
            "completeness": completeness_data("not_assessed"),
            "risk_assessment": risk_data(None),
            "errors": [error_data()],
        }
    )
    return data


def test_analysis_result_accepts_full_completed_result() -> None:
    result = AnalysisResult.model_validate(completed_result_data())

    assert result.status is AnalysisStatus.COMPLETED
    assert result.stage is ProcessingStage.FINISHED
    assert isinstance(result.file, ValidatedFileDescriptor)
    assert result.analyzers[0].score == 4.2
    assert result.risk_assessment.probability is None
    assert result.risk_assessment.final_level is not None


def test_analysis_result_accepts_partial_result_with_partial_completeness() -> None:
    data = completed_result_data()
    data.update(
        {
            "status": "partial",
            "completeness": completeness_data("partial"),
            "warnings": ["Анализ выполнен частично."],
        }
    )

    result = AnalysisResult.model_validate(data)

    assert result.status is AnalysisStatus.PARTIAL
    assert result.completeness.status.value == "partial"


def test_analysis_result_accepts_rejected_result_with_input_descriptor() -> None:
    result = AnalysisResult.model_validate(rejected_result_data())

    assert result.status is AnalysisStatus.REJECTED
    assert isinstance(result.file, InputFileDescriptor)
    assert result.analyzers == []
    assert result.findings == []


def test_analysis_result_accepts_failed_result() -> None:
    result = AnalysisResult.model_validate(failed_result_data())

    assert result.status is AnalysisStatus.FAILED
    assert result.risk_assessment.final_level is None


def test_schema_version_defaults_to_and_serializes_as_1_0() -> None:
    data = completed_result_data()
    del data["schema_version"]

    result = AnalysisResult.model_validate(data)

    assert result.schema_version == "1.0"
    assert result.model_dump(mode="json")["schema_version"] == "1.0"


def test_analysis_result_rejects_other_schema_version() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**completed_result_data(), "schema_version": "1.1"})


def test_analysis_result_converts_string_status_and_stage_to_enums() -> None:
    result = AnalysisResult.model_validate(completed_result_data())

    assert result.status is AnalysisStatus.COMPLETED
    assert result.stage is ProcessingStage.FINISHED


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
@pytest.mark.parametrize(
    "invalid_time",
    [
        datetime(2026, 7, 24, 14, 35, 22),
        datetime(2026, 7, 24, 17, 35, 22, tzinfo=timezone(timedelta(hours=3))),
    ],
)
def test_analysis_result_rejects_naive_and_non_utc_top_level_times(
    field: str,
    invalid_time: datetime,
) -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**completed_result_data(), field: invalid_time})


@pytest.mark.parametrize("field", ["queued_at", "started_at", "finished_at"])
@pytest.mark.parametrize(
    "invalid_time",
    [
        datetime(2026, 7, 24, 14, 35, 22),
        datetime(2026, 7, 24, 17, 35, 22, tzinfo=timezone(timedelta(hours=3))),
    ],
)
def test_analysis_result_rejects_naive_and_non_utc_processing_times(
    field: str,
    invalid_time: datetime,
) -> None:
    processing = {
        **processing_data(),
        field: invalid_time,
    }

    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**completed_result_data(), "processing": processing})


def test_analysis_result_rejects_negative_processing_duration() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {
                **completed_result_data(),
                "processing": {**processing_data(), "duration_ms": -1},
            }
        )


def test_analysis_result_requires_non_null_processing_queued_at() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {
                **completed_result_data(),
                "processing": {**processing_data(), "queued_at": None},
            }
        )


def test_analysis_result_serializes_all_utc_times_with_z() -> None:
    dumped = AnalysisResult.model_validate(completed_result_data()).model_dump(mode="json")

    assert dumped["created_at"].endswith("Z")
    assert dumped["updated_at"].endswith("Z")
    assert dumped["processing"]["queued_at"].endswith("Z")
    assert dumped["processing"]["started_at"].endswith("Z")
    assert dumped["processing"]["finished_at"].endswith("Z")
    assert dumped["cleanup"]["finished_at"].endswith("Z")


def test_analysis_result_converts_all_nested_dictionaries_to_models() -> None:
    result = AnalysisResult.model_validate(completed_result_data())

    assert isinstance(result.source, SourceContext)
    assert isinstance(result.processing, AnalysisProcessing)
    assert isinstance(result.analyzers[0], AnalyzerResult)
    assert isinstance(result.findings[0], Finding)
    assert isinstance(result.completeness, AnalysisCompleteness)
    assert isinstance(result.risk_assessment, RiskAssessment)
    assert isinstance(result.recommendation, Recommendation)
    assert isinstance(result.cleanup, CleanupResult)


def test_analysis_result_json_dump_and_full_round_trip() -> None:
    result = AnalysisResult.model_validate(completed_result_data())
    dumped = result.model_dump(mode="json")
    restored = AnalysisResult.model_validate_json(result.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == result
    assert isinstance(restored.file, ValidatedFileDescriptor)
    assert isinstance(restored.processing, AnalysisProcessing)


def test_empty_top_level_collections_remain_present_as_empty_lists() -> None:
    data = completed_result_data()
    data.update({"analyzers": [], "findings": [], "warnings": [], "errors": []})

    dumped = AnalysisResult.model_validate(data).model_dump(mode="json")

    for field in ("analyzers", "findings", "warnings", "errors"):
        assert dumped[field] == []


@pytest.mark.parametrize("field", ["analyzers", "findings", "warnings", "errors"])
def test_analysis_result_requires_every_top_level_collection(field: str) -> None:
    data = completed_result_data()
    del data[field]

    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(data)


@pytest.mark.parametrize("field", ["analyzers", "findings"])
def test_rejected_result_rejects_analysis_outputs(field: str) -> None:
    data = rejected_result_data()
    data[field] = [analyzer_data()] if field == "analyzers" else [finding_data()]

    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(data)


def test_rejected_result_rejects_final_level() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {**rejected_result_data(), "risk_assessment": risk_data("low")}
        )


def test_rejected_result_requires_errors() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**rejected_result_data(), "errors": []})


def test_rejected_result_requires_not_assessed_completeness() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {**rejected_result_data(), "completeness": completeness_data("partial")}
        )


def test_failed_result_rejects_final_level() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {**failed_result_data(), "risk_assessment": risk_data("high")}
        )


def test_failed_result_requires_errors() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**failed_result_data(), "errors": []})


def test_insufficient_completeness_rejects_final_level() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {**completed_result_data(), "completeness": completeness_data("insufficient")}
        )


def test_insufficient_completeness_accepts_absent_final_level() -> None:
    result = AnalysisResult.model_validate(
        {
            **completed_result_data(),
            "completeness": completeness_data("insufficient"),
            "risk_assessment": risk_data(None),
        }
    )

    assert result.risk_assessment.final_level is None


def test_partial_result_requires_partial_completeness() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**completed_result_data(), "status": "partial"})


@pytest.mark.parametrize(("field", "value"), [("status", "done"), ("stage", "done")])
def test_analysis_result_rejects_invalid_status_and_stage(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**completed_result_data(), field: value})


def test_analysis_result_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({**completed_result_data(), "workspace_path": "private"})


def test_internal_paths_do_not_appear_in_serialized_result() -> None:
    dumped_json = AnalysisResult.model_validate(completed_result_data()).model_dump_json()

    assert "workspace_path" not in dumped_json
    assert "source_file_ref" not in dumped_json
    assert "runtime/temp" not in dumped_json


def test_public_analysis_contracts_are_available_by_direct_import() -> None:
    assert AnalysisResult is ModelsAnalysisResult
    assert domain.AnalysisResult is ModelsAnalysisResult
    assert domain.CleanupResult is CleanupResult
    assert domain.Recommendation is Recommendation
    assert domain.RiskAssessment is RiskAssessment
    assert "AnalysisProcessing" not in domain.__all__


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
