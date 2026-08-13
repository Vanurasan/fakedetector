"""Initialization of directories and dependencies required by the runtime."""

import subprocess
from pathlib import Path

from fakedetector.config.models import AppConfig


class RuntimeSetupError(Exception):
    """Raised when required runtime directories cannot be initialized."""


def ensure_runtime_directories(config: AppConfig) -> None:
    """Create active directories and verify mandatory media executables."""
    setup_error: RuntimeSetupError | None = None
    try:
        Path(config.temporary_storage.root_path).mkdir(
            mode=0o700,
            parents=True,
            exist_ok=True,
        )
        Path(config.logging.jsonl_path).parent.mkdir(parents=True, exist_ok=True)
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
