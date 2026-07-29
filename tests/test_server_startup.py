"""Bounded smoke test for the installed FakeDetector server entry point."""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_STARTUP_TIMEOUT_SECONDS = 10.0
_REQUEST_TIMEOUT_SECONDS = 0.25
_POLL_INTERVAL_SECONDS = 0.05
_PROCESS_STOP_TIMEOUT_SECONDS = 3.0
_STARTUP_LOG_FIELDS = {
    "timestamp",
    "level",
    "logger",
    "event",
    "message",
    "schema_version",
    "host",
    "port",
}


def _console_scripts() -> dict[str, str]:
    distribution = importlib.metadata.distribution("fakedetector")
    return {
        entry_point.name: entry_point.value
        for entry_point in distribution.entry_points
        if entry_point.group == "console_scripts"
    }


def _reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _tracked_status() -> bytes:
    git = shutil.which("git")
    assert git is not None, "git executable is required to verify tracked files"
    result = subprocess.run(
        [git, "status", "--short", "--untracked-files=no"],
        cwd=_REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _runtime_state() -> tuple[tuple[str, bool, int, int], ...] | None:
    runtime_root = _REPOSITORY_ROOT / "runtime"
    if not runtime_root.exists():
        return None
    return tuple(
        (
            path.relative_to(runtime_root).as_posix(),
            path.is_dir(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in sorted(runtime_root.rglob("*"))
    )


def _wait_for_health(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    url = f"http://127.0.0.1:{port}/health"

    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise AssertionError(
                f"FakeDetector exited before readiness (return code {return_code})"
            )

        try:
            with urlopen(url, timeout=_REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
                status = response.status
                payload = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(_POLL_INTERVAL_SECONDS)
            continue

        assert status == 200
        assert payload == {"status": "ok"}
        assert process.poll() is None, "FakeDetector exited during the health response"
        return

    raise AssertionError("FakeDetector did not become ready within 10 seconds")


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=_PROCESS_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_PROCESS_STOP_TIMEOUT_SECONDS)


def test_console_entry_point_targets_main() -> None:
    assert _console_scripts().get("fakedetector") == "fakedetector.main:main"


def test_installed_server_starts_and_serves_health(tmp_path: Path) -> None:
    executable = shutil.which("fakedetector")
    assert executable is not None, (
        "installed 'fakedetector' console script was not found on PATH; "
        "run this test through 'uv run pytest'"
    )

    tracked_status_before = _tracked_status()
    runtime_state_before = _runtime_state()
    port = _reserve_loopback_port()
    log_path = tmp_path / "logs" / "application.jsonl"
    config_data = yaml.safe_load(
        (_REPOSITORY_ROOT / "config" / "config.example.yaml").read_text(encoding="utf-8")
    )
    config_data["server"]["host"] = "127.0.0.1"
    config_data["server"]["port"] = port
    config_data["logging"]["jsonl_path"] = str(log_path)
    temporary_yaml = yaml.safe_dump(config_data, allow_unicode=True, sort_keys=False)
    config_path = tmp_path / "server-smoke.yaml"
    config_path.write_text(temporary_yaml, encoding="utf-8")

    assert log_path.is_relative_to(tmp_path)
    assert config_path.is_relative_to(tmp_path)

    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("FAKEDETECTOR_")
    }
    process = subprocess.Popen(
        [executable, "--config", str(config_path)],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_health(process, port)
    finally:
        _stop_process(process)

    assert process.poll() is not None
    assert log_path.is_file()
    log_text = log_path.read_text(encoding="utf-8")
    records = [json.loads(line) for line in log_text.splitlines() if line.strip()]
    assert records
    assert all(set(record) <= _STARTUP_LOG_FIELDS for record in records)
    startup_records = [
        record for record in records if record.get("event") == "application_starting"
    ]
    assert len(startup_records) == 1
    startup_record = startup_records[0]
    assert set(startup_record) == _STARTUP_LOG_FIELDS
    assert startup_record["host"] == "127.0.0.1"
    assert startup_record["port"] == port
    assert temporary_yaml not in log_text

    assert _runtime_state() == runtime_state_before
    assert _tracked_status() == tracked_status_before
