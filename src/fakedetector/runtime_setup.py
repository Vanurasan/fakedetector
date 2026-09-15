"""Initialization of directories and dependencies required by the runtime."""

import subprocess
from pathlib import Path

from fakedetector._filesystem import (
    ensure_private_directory,
    require_regular_file,
    require_safe_directory,
)
from fakedetector.config.models import AppConfig


class RuntimeSetupError(Exception):
    """Raised when required runtime directories cannot be initialized."""


def ensure_runtime_directories(config: AppConfig) -> None:
    """Create active directories and verify mandatory media executables."""
    temporary_storage_path = Path(config.temporary_storage.root_path).absolute()
    quarantine_path = temporary_storage_path.parent / "quarantine"
    result_directory = Path(config.result.directory).absolute()
    log_path = Path(config.logging.jsonl_path).absolute()
    setup_error: RuntimeSetupError | None = None
    try:
        ensure_private_directory(temporary_storage_path)
        require_safe_directory(quarantine_path, missing_ok=True)
        require_safe_directory(result_directory, missing_ok=True)
        ensure_private_directory(log_path.parent)
        require_regular_file(log_path, missing_ok=True)
    except OSError:
        setup_error = RuntimeSetupError("Runtime initialization failed.")

    if setup_error is not None:
        raise setup_error from None

    dependency_error: RuntimeSetupError | None = None
    for executable in ("ffmpeg", "ffprobe"):
        try:
            result = subprocess.run(
                [executable, "-version"],
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=temporary_storage_path,
                timeout=5.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            dependency_error = RuntimeSetupError("Runtime initialization failed.")
            break
        if result.returncode != 0:
            dependency_error = RuntimeSetupError("Runtime initialization failed.")
            break

    if dependency_error is not None:
        raise dependency_error from None
