"""Tests for initialization of application runtime directories."""

from __future__ import annotations

import traceback
from pathlib import Path

import pytest

from fakedetector.config.models import AppConfig
from fakedetector.runtime_setup import RuntimeSetupError, ensure_runtime_directories


def make_config(
    *,
    temporary_storage_path: Path,
    result_directory: Path,
    log_path: Path,
) -> AppConfig:
    """Create a valid configuration with isolated filesystem paths."""
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {},
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {"root_path": str(temporary_storage_path)},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {"directory": str(result_directory)},
            "error_handling": {},
            "logging": {"jsonl_path": str(log_path)},
            "external_systems": {},
        }
    )


def test_creates_required_nested_directory_when_runtime_is_absent(tmp_path: Path) -> None:
    runtime_path = tmp_path / "missing" / "runtime"
    log_path = runtime_path / "logs" / "nested" / "application.jsonl"
    config = make_config(
        temporary_storage_path=runtime_path / "temp",
        result_directory=runtime_path / "results",
        log_path=log_path,
    )

    assert not runtime_path.exists()

    ensure_runtime_directories(config)

    assert log_path.parent.is_dir()
    assert not log_path.exists()


def test_supports_relative_path_and_repeated_calls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = make_config(
        temporary_storage_path=Path("runtime/temp"),
        result_directory=Path("runtime/results"),
        log_path=Path("runtime/logs/application.jsonl"),
    )

    ensure_runtime_directories(config)
    ensure_runtime_directories(config)

    assert (tmp_path / "runtime" / "logs").is_dir()


def test_existing_directory_and_file_are_preserved(tmp_path: Path) -> None:
    log_directory = tmp_path / "runtime" / "logs"
    log_directory.mkdir(parents=True)
    marker = log_directory / "keep.txt"
    marker.write_text("preserve-me", encoding="utf-8")
    config = make_config(
        temporary_storage_path=tmp_path / "runtime" / "temp",
        result_directory=tmp_path / "runtime" / "results",
        log_path=log_directory / "application.jsonl",
    )

    ensure_runtime_directories(config)

    assert marker.read_text(encoding="utf-8") == "preserve-me"


def test_config_is_not_modified(tmp_path: Path) -> None:
    config = make_config(
        temporary_storage_path=tmp_path / "runtime" / "temp",
        result_directory=tmp_path / "runtime" / "results",
        log_path=tmp_path / "runtime" / "logs" / "application.jsonl",
    )
    original = config.model_dump(mode="json")

    ensure_runtime_directories(config)

    assert config.model_dump(mode="json") == original


def test_does_not_create_directories_for_inactive_future_modules(tmp_path: Path) -> None:
    temporary_storage_path = tmp_path / "future" / "temp"
    result_directory = tmp_path / "future" / "results"
    log_path = tmp_path / "active" / "logs" / "application.jsonl"
    config = make_config(
        temporary_storage_path=temporary_storage_path,
        result_directory=result_directory,
        log_path=log_path,
    )

    ensure_runtime_directories(config)

    assert log_path.parent.is_dir()
    assert not temporary_storage_path.exists()
    assert not result_directory.exists()


def test_mkdir_error_is_safe_and_has_no_unsafe_exception_chain(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sentinel = "secret-like-sentinel"
    unsafe_path = tmp_path / sentinel / "logs" / "application.jsonl"
    config = make_config(
        temporary_storage_path=tmp_path / "temp",
        result_directory=tmp_path / "results",
        log_path=unsafe_path,
    )

    def fail_mkdir(self: Path, *, parents: bool, exist_ok: bool) -> None:
        raise OSError(f"cannot create {self}: {sentinel}")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(RuntimeSetupError) as exc_info:
        ensure_runtime_directories(config)

    error = exc_info.value
    rendered_traceback = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    assert str(unsafe_path) not in str(error)
    assert sentinel not in str(error)
    assert str(unsafe_path) not in rendered_traceback
    assert sentinel not in rendered_traceback
    assert error.__cause__ is None
    assert error.__context__ is None
