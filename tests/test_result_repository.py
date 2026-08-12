"""Contract and safety tests for the JSON file result repository."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

import pytest

import fakedetector.repositories.result_repository as repository_module
from fakedetector.domain import AnalysisResult, AnalysisResultSummary, MediaType, RiskLevel
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
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    validated_file: bool = False,
    external_reference: str = "../external/reference",
    final_level: str | None = "low",
) -> AnalysisResult:
    """Build a compact valid completed AnalysisResult for repository tests."""
    timestamp = created_at or datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    last_updated = updated_at or timestamp
    input_file: dict[str, Any] = {
        "original_name": original_name,
        "declared_content_type": "image/jpeg",
        "size_bytes": 128,
        "received_at": timestamp,
    }
    validated_descriptor: dict[str, Any] = {
        "original_name": original_name,
        "extension": "jpg",
        "declared_mime_type": "image/jpeg",
        "detected_mime_type": "image/jpeg",
        "media_type": "image",
        "size_bytes": 128,
        "sha256": "repository-test-digest",
        "signature_match": True,
        "safe_read": True,
        "technical_parameters": {
            "width": 16,
            "height": 16,
            "format": "JPEG",
            "color_mode": "RGB",
            "frame_count": None,
            "has_metadata": False,
        },
    }
    return AnalysisResult.model_validate(
        {
            "schema_version": "1.0",
            "analysis_id": analysis_id,
            "created_at": timestamp,
            "updated_at": last_updated,
            "status": "completed",
            "stage": "finished",
            "source": {
                "channel": "api",
                "connector": None,
                "external_system": None,
                "external_reference": external_reference,
            },
            "file": validated_descriptor if validated_file else input_file,
            "processing": {
                "queued_at": timestamp,
                "started_at": timestamp,
                "finished_at": last_updated,
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
                "final_level": final_level,
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


def test_get_rejects_filename_payload_id_mismatch_without_deletion(tmp_path: Path) -> None:
    repository = JsonFileResultRepository(tmp_path)
    target = tmp_path / "requested-id.json"
    payload = make_result("payload-id").model_dump_json()
    target.write_text(payload, encoding="utf-8")

    with pytest.raises(CorruptedResultError) as error_info:
        repository.get("requested-id")

    assert str(error_info.value) == "Stored result is corrupted or invalid."
    assert "requested-id" not in str(error_info.value)
    assert "payload-id" not in str(error_info.value)
    assert str(tmp_path) not in str(error_info.value)
    assert target.read_text(encoding="utf-8") == payload


def test_list_recent_protocol_missing_directory_and_empty_directory(tmp_path: Path) -> None:
    result_directory = tmp_path / "results"
    repository = JsonFileResultRepository(result_directory)

    assert isinstance(repository, ResultRepository)
    assert repository.list_recent(10) == []
    assert not result_directory.exists()

    result_directory.mkdir()
    assert repository.list_recent(10) == []


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_list_recent_rejects_non_positive_limit_before_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: int,
) -> None:
    result_directory = tmp_path / "results"
    repository = JsonFileResultRepository(result_directory)

    def fail_if_scanned(_path: Path) -> NoReturn:
        raise AssertionError("invalid limit must not scan the result directory")

    monkeypatch.setattr(Path, "iterdir", fail_if_scanned)

    with pytest.raises(ValueError, match="^limit must be greater than zero$"):
        repository.list_recent(limit)

    assert not result_directory.exists()


def test_list_recent_returns_exact_safe_summary_for_validated_result(tmp_path: Path) -> None:
    repository = JsonFileResultRepository(tmp_path)
    result = make_result(
        "validated-id",
        original_name="PRIVATE-NAME.jpg",
        validated_file=True,
        external_reference="PRIVATE-REFERENCE",
    )
    repository.save(result)

    summaries = repository.list_recent(1)

    assert summaries == [
        AnalysisResultSummary(
            analysis_id="validated-id",
            created_at=result.created_at,
            updated_at=result.updated_at,
            status=result.status,
            media_type=MediaType.IMAGE,
            final_risk_level=RiskLevel.LOW,
            completeness_status=result.completeness.status,
        )
    ]
    serialized = summaries[0].model_dump_json()
    assert "PRIVATE-NAME" not in serialized
    assert "PRIVATE-REFERENCE" not in serialized


def test_list_recent_input_descriptor_does_not_guess_media_type_or_risk(tmp_path: Path) -> None:
    repository = JsonFileResultRepository(tmp_path)
    result = make_result(
        "unvalidated-id",
        original_name="looks-like-video.mp4",
        final_level=None,
    )
    repository.save(result)

    summary = repository.list_recent(1)[0]

    assert summary.media_type is None
    assert summary.final_risk_level is None


def test_list_recent_sorts_by_created_at_then_id_and_ignores_updated_at_and_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    base_time = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    results = [
        make_result(
            "tie-z",
            created_at=base_time,
            updated_at=base_time + timedelta(days=20),
        ),
        make_result(
            "newest",
            created_at=base_time + timedelta(minutes=1),
            updated_at=base_time - timedelta(days=20),
        ),
        make_result(
            "tie-a",
            created_at=base_time,
            updated_at=base_time + timedelta(days=30),
        ),
        make_result(
            "oldest",
            created_at=base_time - timedelta(minutes=1),
            updated_at=base_time + timedelta(days=40),
        ),
    ]
    for index, result in enumerate(results):
        repository.save(result)
        path = tmp_path / f"{result.analysis_id}.json"
        os.utime(path, (100 + index, 100 + index))

    real_iterdir = Path.iterdir

    def reverse_iterdir(path: Path) -> Any:
        return iter(reversed(list(real_iterdir(path))))

    monkeypatch.setattr(Path, "iterdir", reverse_iterdir)

    assert [summary.analysis_id for summary in repository.list_recent(10)] == [
        "newest",
        "tie-a",
        "tie-z",
        "oldest",
    ]
    assert [summary.analysis_id for summary in repository.list_recent(2)] == [
        "newest",
        "tie-a",
    ]


def test_list_recent_filters_corruption_before_applying_limit_and_is_read_only(
    tmp_path: Path,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    valid_results = [
        make_result(
            "valid-new",
            created_at=datetime(2026, 8, 12, 13, 0, tzinfo=UTC),
        ),
        make_result(
            "valid-old",
            created_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
        ),
    ]
    for result in valid_results:
        repository.save(result)

    corrupted_payloads: dict[str, bytes] = {
        "invalid-utf8.json": b"\xff\xfePRIVATE_UTF8",
        "invalid-json.json": b'{"private": "PRIVATE_JSON"',
        "schema-invalid.json": b'{"private": "PRIVATE_SCHEMA"}',
    }
    unsupported = json.loads(make_result("unsupported").model_dump_json())
    unsupported["schema_version"] = "2.0"
    corrupted_payloads["unsupported.json"] = json.dumps(unsupported).encode()
    nested_invalid = json.loads(make_result("nested-invalid").model_dump_json())
    nested_invalid["risk_assessment"]["final_level"] = "critical"
    corrupted_payloads["nested-invalid.json"] = json.dumps(nested_invalid).encode()
    mismatch_payload = make_result("payload-id").model_dump_json().encode()
    corrupted_payloads["filename-id.json"] = mismatch_payload

    for filename, payload in corrupted_payloads.items():
        (tmp_path / filename).write_bytes(payload)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    summaries = repository.list_recent(2)

    assert [summary.analysis_id for summary in summaries] == ["valid-new", "valid-old"]
    assert "filename-id" not in {summary.analysis_id for summary in summaries}
    assert "payload-id" not in {summary.analysis_id for summary in summaries}
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_list_recent_returns_empty_when_all_result_candidates_are_corrupted(
    tmp_path: Path,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    target = tmp_path / "broken.json"
    target.write_text('{"private": "DO_NOT_LEAK"', encoding="utf-8")

    assert repository.list_recent(5) == []
    assert target.exists()


def test_list_recent_ignores_non_candidates_and_does_not_recurse(tmp_path: Path) -> None:
    repository = JsonFileResultRepository(tmp_path)
    valid = make_result("direct-valid")
    repository.save(valid)
    payload = valid.model_dump_json()
    (tmp_path / ".result-random.tmp").write_text(payload, encoding="utf-8")
    (tmp_path / "upper.JSON").write_text(payload, encoding="utf-8")
    (tmp_path / "double.json.tmp").write_text(payload, encoding="utf-8")
    (tmp_path / "directory.json").mkdir()
    (tmp_path / "..json").write_text(payload, encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested-valid.json").write_text(
        make_result("nested-valid").model_dump_json(), encoding="utf-8"
    )

    assert [summary.analysis_id for summary in repository.list_recent(20)] == [
        "direct-valid"
    ]


def test_list_recent_ignores_symlink_without_reading_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    target = tmp_path / "outside-target.txt"
    target.write_text(make_result("linked").model_dump_json(), encoding="utf-8")
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not available in this environment")

    real_read_text = Path.read_text

    def guard_target_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path in (link, target):
            raise AssertionError("listing followed or read a symlink")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guard_target_read)

    assert repository.list_recent(5) == []


def test_list_recent_directory_enumeration_error_is_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_directory = tmp_path / "PRIVATE-DIRECTORY"
    result_directory.mkdir()
    repository = JsonFileResultRepository(result_directory)

    def fail_iterdir(_path: Path) -> NoReturn:
        raise OSError("PRIVATE OS ENUMERATION ERROR")

    monkeypatch.setattr(Path, "iterdir", fail_iterdir)

    with pytest.raises(ResultRepositoryError) as error_info:
        repository.list_recent(1)

    assert str(error_info.value) == "Stored results could not be listed."
    assert "PRIVATE" not in str(error_info.value)
    assert str(tmp_path) not in str(error_info.value)


def test_list_recent_candidate_read_error_is_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = JsonFileResultRepository(tmp_path)
    target = tmp_path / "private-entry.json"
    payload = make_result("private-entry").model_dump_json()
    target.write_text(payload, encoding="utf-8")
    real_read_text = Path.read_text

    def fail_candidate_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == target:
            raise OSError("PRIVATE OS READ ERROR")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_candidate_read)

    with pytest.raises(ResultRepositoryError) as error_info:
        repository.list_recent(1)

    assert str(error_info.value) == "Stored results could not be listed."
    assert "private-entry" not in str(error_info.value)
    assert "PRIVATE OS" not in str(error_info.value)
    assert payload not in str(error_info.value)
    assert str(tmp_path) not in str(error_info.value)
