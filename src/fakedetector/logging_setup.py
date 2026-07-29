"""Safe JSONL logging setup for the application logger."""

from __future__ import annotations

import json
import logging
import logging.handlers
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fakedetector.config.models import LoggingConfig

_LOGGER_NAME = "fakedetector"
_HANDLER_MARKER = "_fakedetector_logging_handler"


class LoggingSetupError(Exception):
    """Raised when the application log handler cannot be initialized safely."""

    def __init__(self) -> None:
        super().__init__("Logging initialization failed.")


class _JsonlFormatter(logging.Formatter):
    """Serialize only the approved fields of a log record."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(
            record.created,
            tz=UTC,
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }

        for field in ("schema_version", "host", "port"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _remove_configured_handlers(
    logger: logging.Logger,
    jsonl_path: str,
    rotation_max_bytes: int,
    rotation_backup_count: int,
) -> logging.handlers.RotatingFileHandler | None:
    """Return a matching rotating handler and remove stale application handlers."""
    existing_handler: logging.handlers.RotatingFileHandler | None = None
    expected_path = Path(jsonl_path).absolute()
    for handler in list(logger.handlers):
        if not getattr(handler, _HANDLER_MARKER, False):
            continue
        if (
            isinstance(handler, logging.handlers.RotatingFileHandler)
            and Path(handler.baseFilename) == expected_path
            and handler.maxBytes == rotation_max_bytes
            and handler.backupCount == rotation_backup_count
        ):
            existing_handler = handler
            continue
        logger.removeHandler(handler)
        handler.close()
    return existing_handler


def configure_logging(config: LoggingConfig) -> logging.Logger:
    """Configure and return the named application logger."""
    logger = logging.getLogger(_LOGGER_NAME)
    new_handler: logging.handlers.RotatingFileHandler | None = None
    setup_failed = False

    try:
        logger.setLevel(config.level)
        log_path = Path(config.jsonl_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = _remove_configured_handlers(
            logger,
            str(log_path),
            config.rotation_max_bytes,
            config.rotation_backup_count,
        )
        if handler is None:
            new_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=config.rotation_max_bytes,
                backupCount=config.rotation_backup_count,
                encoding="utf-8",
            )
            new_handler.setLevel(logging.NOTSET)
            new_handler.setFormatter(_JsonlFormatter())
            setattr(new_handler, _HANDLER_MARKER, True)
            logger.addHandler(new_handler)
        else:
            handler.setLevel(logging.NOTSET)
            handler.setFormatter(_JsonlFormatter())
    except (OSError, ValueError):
        setup_failed = True

    if setup_failed:
        if new_handler is not None:
            logger.removeHandler(new_handler)
            with suppress(OSError):
                new_handler.close()
        raise LoggingSetupError() from None

    logger.propagate = False
    return logger
