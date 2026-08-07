"""Contract tests for the InputFileDescriptor domain model."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

import fakedetector.domain as domain
from fakedetector.domain import InputFileDescriptor
from fakedetector.domain.models import InputFileDescriptor as ModelsInputFileDescriptor

EXPECTED_DOMAIN_EXPORTS = [
    "AnalysisStatus",
    "AnalyzerStatus",
    "AudioTechnicalParameters",
    "CleanupStatus",
    "CompletenessStatus",
    "FindingSeverity",
    "ImageTechnicalParameters",
    "InputFileDescriptor",
    "MediaType",
    "ProcessingStage",
    "RiskLevel",
    "SourceChannel",
    "SourceContext",
    "ValidatedFileDescriptor",
    "VideoTechnicalParameters",
]

VALID_DESCRIPTOR: dict[str, Any] = {
    "original_name": "video_message.mp4",
    "declared_content_type": "video/mp4",
    "size_bytes": 48_231_520,
    "received_at": datetime(2026, 7, 24, 14, 35, 22, 314_000, tzinfo=UTC),
}


def test_input_file_descriptor_accepts_all_fields() -> None:
    descriptor = InputFileDescriptor(**VALID_DESCRIPTOR)

    assert descriptor.original_name == "video_message.mp4"
    assert descriptor.declared_content_type == "video/mp4"
    assert descriptor.size_bytes == 48_231_520
    assert descriptor.received_at == datetime(2026, 7, 24, 14, 35, 22, 314_000, tzinfo=UTC)


@pytest.mark.parametrize("missing_field", VALID_DESCRIPTOR)
def test_input_file_descriptor_requires_each_field(missing_field: str) -> None:
    data = VALID_DESCRIPTOR.copy()
    del data[missing_field]

    with pytest.raises(ValidationError):
        InputFileDescriptor.model_validate(data)


def test_input_file_descriptor_accepts_explicit_null_content_type() -> None:
    descriptor = InputFileDescriptor.model_validate(
        {**VALID_DESCRIPTOR, "declared_content_type": None}
    )

    assert descriptor.declared_content_type is None


def test_input_file_descriptor_requires_nullable_content_type_field() -> None:
    data = VALID_DESCRIPTOR.copy()
    del data["declared_content_type"]

    with pytest.raises(ValidationError):
        InputFileDescriptor.model_validate(data)


def test_input_file_descriptor_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        InputFileDescriptor.model_validate({**VALID_DESCRIPTOR, "system_path": "runtime/input"})


def test_input_file_descriptor_preserves_original_name_exactly() -> None:
    original_name = " ../folder\\..\\ Report .MP4 "

    descriptor = InputFileDescriptor.model_validate(
        {**VALID_DESCRIPTOR, "original_name": original_name}
    )

    assert descriptor.original_name == original_name


def test_input_file_descriptor_accepts_timezone_aware_utc_datetime() -> None:
    received_at = datetime(2026, 7, 24, 14, 35, 22, tzinfo=UTC)

    descriptor = InputFileDescriptor.model_validate(
        {**VALID_DESCRIPTOR, "received_at": received_at}
    )

    assert descriptor.received_at is received_at


def test_input_file_descriptor_rejects_naive_datetime() -> None:
    received_at = datetime(2026, 7, 24, 14, 35, 22)

    with pytest.raises(ValidationError):
        InputFileDescriptor.model_validate({**VALID_DESCRIPTOR, "received_at": received_at})


def test_input_file_descriptor_rejects_nonzero_utc_offset() -> None:
    received_at = datetime(
        2026,
        7,
        24,
        17,
        35,
        22,
        tzinfo=timezone(timedelta(hours=3)),
    )

    with pytest.raises(ValidationError):
        InputFileDescriptor.model_validate({**VALID_DESCRIPTOR, "received_at": received_at})


def test_input_file_descriptor_model_dump_is_json_compatible() -> None:
    descriptor = InputFileDescriptor(**VALID_DESCRIPTOR)

    dumped = descriptor.model_dump(mode="json")

    assert json.loads(json.dumps(dumped)) == dumped


def test_input_file_descriptor_serializes_utc_time_with_z_suffix() -> None:
    descriptor = InputFileDescriptor(**VALID_DESCRIPTOR)

    assert descriptor.model_dump(mode="json")["received_at"] == "2026-07-24T14:35:22.314000Z"


def test_input_file_descriptor_json_round_trip() -> None:
    descriptor = InputFileDescriptor(**VALID_DESCRIPTOR)

    restored = InputFileDescriptor.model_validate_json(descriptor.model_dump_json())

    assert restored == descriptor


def test_input_file_descriptor_is_available_by_direct_domain_import() -> None:
    assert InputFileDescriptor is ModelsInputFileDescriptor
    assert domain.InputFileDescriptor is ModelsInputFileDescriptor


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
