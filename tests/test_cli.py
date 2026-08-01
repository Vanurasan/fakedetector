"""Regression tests for the installed FakeDetector console script."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_HELP_TIMEOUT_SECONDS = 5.0


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


def test_installed_console_script_help() -> None:
    executable = shutil.which("fakedetector")
    assert executable is not None, (
        "installed 'fakedetector' console script was not found on PATH; "
        "run this test through 'uv run pytest'"
    )

    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("FAKEDETECTOR_")
    }
    runtime_state_before = _runtime_state()
    try:
        completed = subprocess.run(
            [executable, "--help"],
            cwd=_REPOSITORY_ROOT,
            env=environment,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_HELP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(
            "installed 'fakedetector --help' did not finish within 5 seconds"
        ) from None
    except OSError:
        raise AssertionError(
            "installed 'fakedetector' console script could not be executed"
        ) from None

    assert _runtime_state() == runtime_state_before, (
        "'fakedetector --help' must not create or modify runtime files"
    )
    assert completed.returncode == 0, "'fakedetector --help' must exit successfully"

    help_output = completed.stdout.casefold()
    assert "usage" in help_output
    assert "fakedetector" in help_output
    assert "--config" in help_output
