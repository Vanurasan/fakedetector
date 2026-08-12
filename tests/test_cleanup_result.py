"""Contract tests for the CleanupResult domain model."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from fakedetector.domain import CleanupResult, CleanupStatus, ErrorDetail


def cleanup_data() -> dict[str, Any]:
    """Return a complete successful cleanup record."""
    return {
        "status": "completed",
        "original_file_deleted": True,
        "intermediate_files_deleted": True,
        "quarantine_used": False,
        "finished_at": datetime(2026, 7, 24, 14, 36, 17, tzinfo=UTC),
        "errors": [],
    }


@pytest.mark.parametrize("status", list(CleanupStatus))
def test_cleanup_result_accepts_every_status(status: CleanupStatus) -> None:
    result = CleanupResult.model_validate({**cleanup_data(), "status": status.value})

    assert result.status is status


def test_cleanup_result_accepts_nullable_finished_at() -> None:
    result = CleanupResult.model_validate(
        {**cleanup_data(), "status": "not_started", "finished_at": None}
    )

    assert result.finished_at is None


def test_cleanup_result_validates_nested_error_detail() -> None:
    result = CleanupResult.model_validate(
        {
            **cleanup_data(),
            "status": "failed",
            "errors": [
                {
                    "code": "cleanup_failed",
                    "category": "cleanup",
                    "message": "Не удалось удалить временный файл.",
                    "retryable": True,
                }
            ],
        }
    )

    assert isinstance(result.errors[0], ErrorDetail)


def test_cleanup_result_serializes_utc_time_with_z_suffix() -> None:
    result = CleanupResult.model_validate(cleanup_data())

    assert result.model_dump(mode="json")["finished_at"] == "2026-07-24T14:36:17Z"


@pytest.mark.parametrize(
    "finished_at",
    [
        datetime(2026, 7, 24, 14, 36, 17),
        datetime(2026, 7, 24, 17, 36, 17, tzinfo=timezone(timedelta(hours=3))),
    ],
)
def test_cleanup_result_rejects_naive_and_non_utc_time(finished_at: datetime) -> None:
    with pytest.raises(ValidationError):
        CleanupResult.model_validate({**cleanup_data(), "finished_at": finished_at})


def test_cleanup_result_json_dump_and_round_trip() -> None:
    result = CleanupResult.model_validate(cleanup_data())
    dumped = result.model_dump(mode="json")
    restored = CleanupResult.model_validate_json(result.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == result


def test_cleanup_result_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        CleanupResult.model_validate({**cleanup_data(), "workspace_path": "runtime/temp/id"})
