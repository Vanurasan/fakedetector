"""Initialization of directories required by the current application runtime."""

from pathlib import Path

from fakedetector.config.models import AppConfig


class RuntimeSetupError(Exception):
    """Raised when required runtime directories cannot be initialized."""


def ensure_runtime_directories(config: AppConfig) -> None:
    """Create directories required by modules active during application startup."""
    setup_error: RuntimeSetupError | None = None
    try:
        Path(config.logging.jsonl_path).parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        setup_error = RuntimeSetupError("Runtime initialization failed.")

    if setup_error is not None:
        raise setup_error from None
