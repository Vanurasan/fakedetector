"""Tests for initialization of application runtime directories."""

from __future__ import annotations

import subprocess
import traceback
from pathlib import Path

import pytest

import fakedetector.runtime_setup as runtime_setup_module
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

    assert (runtime_path / "temp").is_dir()
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

    assert (tmp_path / "runtime" / "temp").is_dir()
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


def test_creates_active_temp_but_not_inactive_result_directory(tmp_path: Path) -> None:
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
    assert temporary_storage_path.is_dir()
    assert not result_directory.exists()


def test_mkdir_error_is_safe_and_has_no_unsafe_exception_chain(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sentinel = "secret-like-sentinel"
    unsafe_path = tmp_path / sentinel / "logs" / "application.jsonl"
    unsafe_temp_path = tmp_path / sentinel / "temp"
    config = make_config(
        temporary_storage_path=unsafe_temp_path,
        result_directory=tmp_path / "results",
        log_path=unsafe_path,
    )

    def fail_mkdir(
        self: Path,
        mode: int = 0o777,
        *,
        parents: bool,
        exist_ok: bool,
    ) -> None:
        raise OSError(f"cannot create {self}: {sentinel}")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(RuntimeSetupError) as exc_info:
        ensure_runtime_directories(config)

    error = exc_info.value
    rendered_traceback = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    assert str(unsafe_path) not in str(error)
    assert str(unsafe_temp_path) not in str(error)
    assert sentinel not in str(error)
    assert str(unsafe_path) not in rendered_traceback
    assert str(unsafe_temp_path) not in rendered_traceback
    assert sentinel not in rendered_traceback
    assert error.__cause__ is None
    assert error.__context__ is None


def test_verifies_ffmpeg_and_ffprobe_with_safe_bounded_calls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append((arguments, kwargs))
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(runtime_setup_module.subprocess, "run", fake_run)
    config = make_config(
        temporary_storage_path=tmp_path / "temp",
        result_directory=tmp_path / "results",
        log_path=tmp_path / "logs" / "application.jsonl",
    )

    ensure_runtime_directories(config)

    assert [arguments for arguments, _kwargs in calls] == [
        ["ffmpeg", "-version"],
        ["ffprobe", "-version"],
    ]
    for _arguments, kwargs in calls:
        assert kwargs == {
            "shell": False,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": (tmp_path / "temp").absolute(),
            "timeout": 5.0,
            "check": False,
        }


@pytest.mark.parametrize("failure", ["missing", "timeout", "nonzero"])
def test_media_dependency_failure_is_safe_runtime_failure(
    tmp_path: Path,
    monkeypatch,
    failure: str,
) -> None:
    sentinel = "PRIVATE INSTALLATION PATH"

    def fake_run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if failure == "missing":
            raise FileNotFoundError(sentinel)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(sentinel, 5.0)
        return subprocess.CompletedProcess(arguments, 1, stderr=sentinel.encode())

    monkeypatch.setattr(runtime_setup_module.subprocess, "run", fake_run)
    config = make_config(
        temporary_storage_path=tmp_path / "temp",
        result_directory=tmp_path / "results",
        log_path=tmp_path / "logs" / "application.jsonl",
    )

    with pytest.raises(RuntimeSetupError) as error_info:
        ensure_runtime_directories(config)

    assert str(error_info.value) == "Runtime initialization failed."
    assert sentinel not in str(error_info.value)
    assert error_info.value.__cause__ is None
    assert error_info.value.__context__ is None
