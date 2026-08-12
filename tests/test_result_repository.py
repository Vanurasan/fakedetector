"""Contract and safety tests for the JSON file result repository."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import pytest

import fakedetector.repositories.result_repository as repository_module
from fakedetector.domain import AnalysisResult
from fakedetector.repositories import (
    CorruptedResultError,
    InvalidAnalysisIdError,
    JsonFileResultRepository,
    ResultRepository,
    ResultRepositoryError,
)

UNSAFE_ANALYSIS_IDS = [
    "../escape",
    "..\\escape",
    "subdir/name",
    "subdir\\name",
    "/absolute",
    "\\absolute",
    ".",
    "..",
]


def make_result(
    analysis_id: str = "analysis-safe-001",
    *,
    original_name: str = "проверка.jpg",
    warning: str | None = None,
) -> AnalysisResult:
    """Build a compact valid completed AnalysisResult for repository tests."""
    timestamp = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    return AnalysisResult.model_validate(
        {
            "schema_version": "1.0",
            "analysis_id": analysis_id,
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "completed",
            "stage": "finished",
            "source": {
                "channel": "api",
                "connector": None,
                "external_system": None,
                "external_reference": "../external/reference",
            },
            "file": {
                "original_name": original_name,
                "declared_content_type": "image/jpeg",
                "size_bytes": 128,
                "received_at": timestamp,
            },
            "processing": {
                "queued_at": timestamp,
                "started_at": timestamp,
                "finished_at": timestamp,
                "duration_ms": 0,
                "config_snapshot_id": "config-test",
                "application_version": "0.1.0",
            },
            "analyzers": [],
            "findings": [],
            "completeness": {
                "status": "complete",
                "planned_analyzers": 0,
                "applicable_analyzers": 0,
                "completed_analyzers": 0,
                "failed_analyzers": 0,
                "timed_out_analyzers": 0,
                "skipped_analyzers": 0,
                "not_applicable_analyzers": 0,
                "coverage_ratio": 1.0,
                "missing_capabilities": [],
                "explanation": "Тестовый анализ завершён.",
            },
            "risk_assessment": {
                "model_id": "score_model_v1",
                "model_version": "0.1.0",
                "score": 0,
                "score_based_level": "low",
                "critical_override_applied": False,
                "critical_finding_ids": [],
                "final_level": "low",
                "probability": None,
                "probability_method": None,
                "summary": "Значимые признаки не выявлены.",
                "explanation": "Тестовая объявленная оценка.",
                "limitations": [],
            },
            "recommendation": {
                "primary_action": "no_additional_action",
                "additional_actions": [],
                "text": "Дополнительные действия не требуются.",
                "requires_manual_review": False,
            },
            "cleanup": {
                "status": "completed",
                "original_file_deleted": True,
                "intermediate_files_deleted": True,
                "quarantine_used": False,
                "finished_at": timestamp,
                "errors": [],
            },
            "warnings": [] if warning is None else [warning],
            "errors": [],
        }
    )


def test_concrete_repository_satisfies_available_structural_protocol(tmp_path: Path) -> None:
    repository = JsonFileResultRepository(tmp_path / "results")

    assert isinstance(repository, ResultRepository)


def test_save_get_exists_and_utf8_json_round_trip(tmp_path: Path) -> None:
    result_directory = tmp_path / "nested" / "results"
    repository = JsonFileResultRepository(result_directory)
    result = make_result()

    assert repository.exists(result.analysis_id) is False
    assert repository.get(result.analysis_id) is None

    repository.save(result)

    target = result_directory / f"{result.analysis_id}.json"
    assert repository.exists(result.analysis_id) is True
    assert [path.name for path in result_directory.iterdir()] == [target.name]
    payload = target.read_bytes()
    assert "проверка.jpg" in payload.decode("utf-8")
    assert json.loads(payload) == result.model_dump(mode="json")
    assert repository.get(result.analysis_id) == result


def test_repeated_save_atomically_replaces_result_for_same_id(tmp_path: Path) -> None:
    repository = JsonFileResultRepository(tmp_path)
    initial = make_result(warning="Первая версия.")
    replacement = make_result(warning="Заменённая версия.")

    repository.save(initial)
    repository.save(replacement)

    assert repository.get(initial.analysis_id) == replacement
    assert list(tmp_path.glob("*.json")) == [tmp_path / f"{initial.analysis_id}.json"]
    assert not list(tmp_path.glob("*.tmp"))


def test_successful_save_uses_same_directory_temp_file_and_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_directory = tmp_path / "results"
    repository = JsonFileResultRepository(result_directory)
    result = make_result()
    observed: dict[str, Path] = {}
    real_replace = os.replace

    def observe_replace(source: os.PathLike[str], target: os.PathLike[str]) -> None:
        source_path = Path(source)
        target_path = Path(target)
        assert source_path.exists()
        assert source_path.parent == result_directory
        assert source_path.name.startswith(".result-")
        assert result.analysis_id not in source_path.name
        assert target_path == result_directory / f"{result.analysis_id}.json"
        observed.update(source=source_path, target=target_path)
        real_replace(source, target)

    monkeypatch.setattr(repository_module.os, "replace", observe_replace)

    repository.save(result)

    assert observed["target"].is_file()
    assert not observed["source"].exists()
    assert [path.name for path in result_directory.iterdir()] == [f"{result.analysis_id}.json"]


def test_failure_before_replace_preserves_existing_target_and_removes_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    initial = make_result(warning="Сохранённый результат.")
    replacement = make_result(warning="Не должен быть сохранён.")
    repository.save(initial)
    target = tmp_path / f"{initial.analysis_id}.json"
    original_payload = target.read_bytes()

    def fail_replace(_source: object, _target: object) -> NoReturn:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(repository_module.os, "replace", fail_replace)

    with pytest.raises(ResultRepositoryError, match="^Result could not be saved\\.$"):
        repository.save(replacement)

    assert target.read_bytes() == original_payload
    assert repository.get(initial.analysis_id) == initial
    assert [path.name for path in tmp_path.iterdir()] == [target.name]


def test_write_failure_before_replace_preserves_target_and_never_calls_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    initial = make_result(warning="Сохранённый результат.")
    replacement = make_result(warning="Не должен быть сохранён.")
    repository.save(initial)
    target = tmp_path / f"{initial.analysis_id}.json"
    original_payload = target.read_bytes()
    replace_called = False

    def fail_fsync(_file_descriptor: int) -> NoReturn:
        raise OSError("simulated write failure")

    def observe_replace(_source: object, _target: object) -> None:
        nonlocal replace_called
        replace_called = True

    monkeypatch.setattr(repository_module.os, "fsync", fail_fsync)
    monkeypatch.setattr(repository_module.os, "replace", observe_replace)

    with pytest.raises(ResultRepositoryError, match="^Result could not be saved\\.$"):
        repository.save(replacement)

    assert replace_called is False
    assert target.read_bytes() == original_payload
    assert repository.get(initial.analysis_id) == initial
    assert [path.name for path in tmp_path.iterdir()] == [target.name]


def test_failed_first_save_leaves_no_partial_target_or_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    result = make_result()

    def fail_replace(_source: object, _target: object) -> NoReturn:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(repository_module.os, "replace", fail_replace)

    with pytest.raises(ResultRepositoryError):
        repository.save(result)

    assert list(tmp_path.iterdir()) == []
    assert repository.exists(result.analysis_id) is False


@pytest.mark.parametrize("analysis_id", UNSAFE_ANALYSIS_IDS)
@pytest.mark.parametrize("operation", ["save", "get", "exists"])
def test_all_operations_reject_unsafe_analysis_ids_without_writing(
    tmp_path: Path,
    analysis_id: str,
    operation: str,
) -> None:
    result_directory = tmp_path / "results"
    repository = JsonFileResultRepository(result_directory)

    with pytest.raises(
        InvalidAnalysisIdError,
        match="^Analysis ID is not a safe path component\\.$",
    ):
        if operation == "save":
            repository.save(make_result(analysis_id))
        elif operation == "get":
            repository.get(analysis_id)
        else:
            repository.exists(analysis_id)

    assert not result_directory.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("analysis_id", ["", "C:drive-relative", "safe:name", "nul\0id"])
def test_cross_platform_unsafe_path_components_are_rejected(
    tmp_path: Path,
    analysis_id: str,
) -> None:
    repository = JsonFileResultRepository(tmp_path / "results")

    with pytest.raises(InvalidAnalysisIdError):
        repository.exists(analysis_id)


def test_target_path_depends_only_on_opaque_analysis_id(tmp_path: Path) -> None:
    result_directory = tmp_path / "results"
    repository = JsonFileResultRepository(result_directory)
    analysis_id = "opaque-id"
    first = make_result(analysis_id, original_name="../../outside/first.jpg")
    second = make_result(analysis_id, original_name="C:\\private\\second.jpg")

    repository.save(first)
    repository.save(second)

    assert [path.name for path in result_directory.iterdir()] == ["opaque-id.json"]
    restored = repository.get(analysis_id)
    assert restored == second
    assert restored is not None
    assert restored.file.original_name == "C:\\private\\second.jpg"
    assert not (tmp_path / "outside").exists()


def test_exists_ignores_non_result_entries(tmp_path: Path) -> None:
    repository = JsonFileResultRepository(tmp_path)
    (tmp_path / "analysis-safe-001.json").mkdir()
    (tmp_path / "analysis-safe-001.tmp").write_text("not a result", encoding="utf-8")

    assert repository.exists("analysis-safe-001") is False
    assert repository.get("analysis-safe-001") is None


@pytest.mark.parametrize(
    "payload",
    [
        '{"secret_payload": "DO_NOT_LEAK"',
        '{"analysis_id": "safe", "secret_payload": "DO_NOT_LEAK"}',
    ],
)
def test_corrupted_and_schema_invalid_json_raise_safe_error_without_deletion(
    tmp_path: Path,
    payload: str,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    target = tmp_path / "stored-result.json"
    target.write_text(payload, encoding="utf-8")

    with pytest.raises(CorruptedResultError) as error_info:
        repository.get("stored-result")

    assert str(error_info.value) == "Stored result is corrupted or invalid."
    assert "DO_NOT_LEAK" not in str(error_info.value)
    assert str(tmp_path) not in str(error_info.value)
    assert target.read_text(encoding="utf-8") == payload
