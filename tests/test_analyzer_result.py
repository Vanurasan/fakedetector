"""Contract tests for the AnalyzerResult domain model."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

import fakedetector.domain as domain
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, ErrorDetail, MediaType
from fakedetector.domain.models import AnalyzerResult as ModelsAnalyzerResult

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

ERROR_DATA: dict[str, Any] = {
    "code": "analyzer_execution_failed",
    "category": "analyzer",
    "message": "Анализатор завершился безопасно обработанной ошибкой.",
    "retryable": True,
    "field": None,
    "analyzer_id": "audio_video_sync_analyzer",
    "safe_details": {"attempt": 1},
}


def analyzer_result_data() -> dict[str, Any]:
    """Return a complete successful analyzer result."""
    return {
        "analyzer_id": "audio_video_sync_analyzer",
        "analyzer_version": "1.0.0",
        "media_type": "video",
        "group": "multimodal",
        "status": "completed",
        "applicable": True,
        "started_at": datetime(2026, 7, 24, 14, 35, 25, tzinfo=UTC),
        "finished_at": datetime(2026, 7, 24, 14, 35, 42, 314_000, tzinfo=UTC),
        "duration_ms": 17_314,
        "score": 4.2,
        "score_name": "model_logit",
        "summary": "Выявлено устойчивое несоответствие.",
        "raw_metrics": {
            "segments_checked": 8,
            "quality": {"usable": True, "notes": None},
        },
        "candidate_findings": [
            {
                "type": "audio_video_desynchronization",
                "interval": [12.1, 19.5],
            }
        ],
        "warnings": [],
        "errors": [],
    }


def test_analyzer_result_accepts_completed_result() -> None:
    result = AnalyzerResult.model_validate(analyzer_result_data())

    assert result.status is AnalyzerStatus.COMPLETED
    assert result.media_type is MediaType.VIDEO
    assert result.score == 4.2
    assert result.score_name == "model_logit"


@pytest.mark.parametrize("status", list(AnalyzerStatus))
def test_analyzer_result_accepts_every_status(status: AnalyzerStatus) -> None:
    data = analyzer_result_data()
    data["status"] = status.value
    if status is AnalyzerStatus.NOT_APPLICABLE:
        data["applicable"] = False
    if status in {AnalyzerStatus.ERROR, AnalyzerStatus.TIMEOUT}:
        data["errors"] = [ERROR_DATA.copy()]
    if status is AnalyzerStatus.SKIPPED:
        data["summary"] = "Пропущено безопасной политикой запуска."

    result = AnalyzerResult.model_validate(data)

    assert result.status is status


def test_analyzer_result_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate({**analyzer_result_data(), "status": "running"})


def test_analyzer_result_converts_string_enums_to_typed_enums() -> None:
    result = AnalyzerResult.model_validate(analyzer_result_data())

    assert result.media_type is MediaType.VIDEO
    assert result.status is AnalyzerStatus.COMPLETED


@pytest.mark.parametrize("missing_field", analyzer_result_data())
def test_analyzer_result_requires_every_field(missing_field: str) -> None:
    data = analyzer_result_data()
    del data[missing_field]

    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate(data)


def test_analyzer_result_accepts_explicit_nullable_values() -> None:
    result = AnalyzerResult.model_validate(
        {
            **analyzer_result_data(),
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "score": None,
            "score_name": None,
        }
    )

    assert result.started_at is None
    assert result.finished_at is None
    assert result.duration_ms is None
    assert result.score is None
    assert result.score_name is None
    assert {"started_at", "finished_at", "duration_ms", "score", "score_name"} <= (
        result.model_fields_set
    )


def test_analyzer_result_serializes_utc_datetimes_with_z_suffix() -> None:
    result = AnalyzerResult.model_validate(analyzer_result_data())

    dumped = result.model_dump(mode="json")

    assert dumped["started_at"] == "2026-07-24T14:35:25Z"
    assert dumped["finished_at"] == "2026-07-24T14:35:42.314000Z"


@pytest.mark.parametrize("field_name", ["started_at", "finished_at"])
@pytest.mark.parametrize(
    "invalid_datetime",
    [
        datetime(2026, 7, 24, 14, 35, 25),
        datetime(
            2026,
            7,
            24,
            17,
            35,
            25,
            tzinfo=timezone(timedelta(hours=3)),
        ),
    ],
)
def test_analyzer_result_rejects_naive_and_non_utc_datetimes(
    field_name: str,
    invalid_datetime: datetime,
) -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate(
            {**analyzer_result_data(), field_name: invalid_datetime}
        )


def test_analyzer_result_rejects_negative_duration() -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate({**analyzer_result_data(), "duration_ms": -1})


def test_analyzer_result_accepts_zero_duration() -> None:
    result = AnalyzerResult.model_validate({**analyzer_result_data(), "duration_ms": 0})

    assert result.duration_ms == 0


def test_analyzer_result_rejects_score_without_score_name() -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate({**analyzer_result_data(), "score_name": None})


def test_analyzer_result_does_not_limit_analyzer_score_as_probability() -> None:
    result = AnalyzerResult.model_validate({**analyzer_result_data(), "score": -12.5})

    assert result.score == -12.5


def test_not_applicable_result_rejects_applicable_true() -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate(
            {**analyzer_result_data(), "status": "not_applicable", "applicable": True}
        )


@pytest.mark.parametrize("status", [AnalyzerStatus.ERROR, AnalyzerStatus.TIMEOUT])
def test_error_and_timeout_require_errors(status: AnalyzerStatus) -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate(
            {**analyzer_result_data(), "status": status, "errors": []}
        )


def test_skipped_result_requires_nonempty_safe_reason() -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate(
            {
                **analyzer_result_data(),
                "status": "skipped",
                "summary": "   ",
                "warnings": ["  "],
            }
        )


def test_skipped_result_accepts_meaningful_warning_as_reason() -> None:
    result = AnalyzerResult.model_validate(
        {
            **analyzer_result_data(),
            "status": "skipped",
            "summary": "",
            "warnings": ["Анализатор отключён активным профилем."],
        }
    )

    assert result.status is AnalyzerStatus.SKIPPED


def test_analyzer_result_validates_nested_error_details() -> None:
    result = AnalyzerResult.model_validate(
        {**analyzer_result_data(), "status": "error", "errors": [ERROR_DATA.copy()]}
    )

    assert isinstance(result.errors[0], ErrorDetail)
    assert result.errors[0].analyzer_id == "audio_video_sync_analyzer"


def test_analyzer_result_accepts_json_safe_structured_results() -> None:
    result = AnalyzerResult.model_validate(analyzer_result_data())
    dumped = result.model_dump(mode="json")

    assert json.loads(json.dumps(dumped["raw_metrics"])) == dumped["raw_metrics"]
    assert json.loads(json.dumps(dumped["candidate_findings"])) == dumped[
        "candidate_findings"
    ]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [("raw_metrics", {"unsafe": object()}), ("candidate_findings", [object()])],
)
def test_analyzer_result_rejects_non_json_structured_results(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate(
            {**analyzer_result_data(), field_name: invalid_value}
        )


def test_analyzer_result_json_dump_and_round_trip() -> None:
    result = AnalyzerResult.model_validate(analyzer_result_data())

    dumped = result.model_dump(mode="json")
    restored = AnalyzerResult.model_validate_json(result.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == result
    assert restored.status is AnalyzerStatus.COMPLETED
    assert restored.media_type is MediaType.VIDEO


def test_analyzer_result_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        AnalyzerResult.model_validate(
            {**analyzer_result_data(), "probability_of_forgery": 0.99}
        )


def test_analyzer_result_is_available_by_direct_domain_import() -> None:
    assert AnalyzerResult is ModelsAnalyzerResult
    assert domain.AnalyzerResult is ModelsAnalyzerResult


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
