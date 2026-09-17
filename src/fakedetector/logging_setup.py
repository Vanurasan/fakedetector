"""Safe JSONL logging setup for the application logger."""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fakedetector._filesystem import (
    ensure_private_directory,
    require_file_descriptor_identity,
    require_regular_file,
    require_safe_directory,
)
from fakedetector.config.models import LoggingConfig

_LOGGER_NAME = "fakedetector"
_HANDLER_MARKER = "_fakedetector_logging_handler"
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_REQUEST_ID = re.compile(r"^req_[0-9a-f]{32}$")
_SCHEMA_VERSION = re.compile(r"^[0-9]+\.[0-9]+$")

_EVENT_MESSAGES = {
    "analysis_completed": "Analysis completed.",
    "analysis_failed": "Analysis failed.",
    "analysis_partial": "Analysis completed partially.",
    "analysis_registered": "Analysis registered.",
    "analyzer_failed": "Analyzer failed.",
    "analyzer_finished": "Analyzer finished.",
    "analyzer_started": "Analyzer started.",
    "api_error": "API request failed.",
    "application_starting": "Application is starting.",
    "cleanup_completed": "Cleanup completed.",
    "cleanup_failed": "Cleanup did not complete.",
    "cleanup_started": "Cleanup started.",
    "configuration_loaded": "Configuration loaded.",
    "log": "Diagnostic event.",
    "ownership_handoff_completed": "Stage 4 ownership handoff completed.",
    "preprocessing_completed": "Preprocessing completed.",
    "preprocessing_started": "Preprocessing started.",
    "result_persistence_failed": "Result persistence failed.",
    "result_saved": "Result saved.",
    "risk_assessment_completed": "Risk assessment completed.",
    "validation_completed": "Validation completed.",
    "validation_failed": "Validation failed internally.",
    "validation_rejected": "Validation rejected the input.",
    "validation_started": "Validation started.",
}


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
        raw_event = getattr(record, "event", "log")
        event = raw_event if raw_event in _EVENT_MESSAGES else "log"
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": _safe_identifier(record.name, fallback=_LOGGER_NAME),
            "module": _safe_identifier(record.module, fallback="unknown"),
            "event": event,
            "message": _EVENT_MESSAGES[event],
        }

        _copy_identifier(payload, record, "analysis_id")
        _copy_request_id(payload, record)
        for field in ("phase", "code", "error_type", "status", "stage"):
            _copy_code(payload, record, field)
        _copy_identifier(payload, record, "analyzer_id")
        _copy_nonnegative_integer(payload, record, "duration_ms")
        _copy_schema_version(payload, record)
        _copy_host(payload, record)
        _copy_port(payload, record)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def emit_diagnostic(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    analysis_id: str | None = None,
    request_id: str | None = None,
    phase: str | None = None,
    code: str | None = None,
    error_type: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    analyzer_id: str | None = None,
    duration_ms: int | None = None,
    schema_version: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Emit one allowlisted diagnostic without changing the primary outcome."""
    safe_event = event if event in _EVENT_MESSAGES else "log"
    extra = {
        key: value
        for key, value in {
            "event": safe_event,
            "analysis_id": analysis_id,
            "request_id": request_id,
            "phase": phase,
            "code": code,
            "error_type": error_type,
            "status": status,
            "stage": stage,
            "analyzer_id": analyzer_id,
            "duration_ms": duration_ms,
            "schema_version": schema_version,
            "host": host,
            "port": port,
        }.items()
        if value is not None
    }
    try:
        logger.log(level, _EVENT_MESSAGES[safe_event], extra=extra, stacklevel=2)
    except Exception:
        return


def _safe_identifier(value: object, *, fallback: str) -> str:
    if isinstance(value, str) and _SAFE_IDENTIFIER.fullmatch(value) is not None:
        return value
    return fallback


def _copy_identifier(
    payload: dict[str, Any],
    record: logging.LogRecord,
    field: str,
) -> None:
    value = getattr(record, field, None)
    if isinstance(value, str) and _SAFE_IDENTIFIER.fullmatch(value) is not None:
        payload[field] = value


def _copy_request_id(payload: dict[str, Any], record: logging.LogRecord) -> None:
    value = getattr(record, "request_id", None)
    if isinstance(value, str) and _REQUEST_ID.fullmatch(value) is not None:
        payload["request_id"] = value


def _copy_code(
    payload: dict[str, Any],
    record: logging.LogRecord,
    field: str,
) -> None:
    value = getattr(record, field, None)
    if isinstance(value, str) and _SAFE_CODE.fullmatch(value) is not None:
        payload[field] = value


def _copy_nonnegative_integer(
    payload: dict[str, Any],
    record: logging.LogRecord,
    field: str,
) -> None:
    value = getattr(record, field, None)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        payload[field] = value


def _copy_schema_version(payload: dict[str, Any], record: logging.LogRecord) -> None:
    value = getattr(record, "schema_version", None)
    if isinstance(value, str) and _SCHEMA_VERSION.fullmatch(value) is not None:
        payload["schema_version"] = value


def _copy_host(payload: dict[str, Any], record: logging.LogRecord) -> None:
    value = getattr(record, "host", None)
    if (
        isinstance(value, str)
        and 0 < len(value) <= 255
        and not any(character.isspace() or character in "/\\" for character in value)
    ):
        payload["host"] = value


def _copy_port(payload: dict[str, Any], record: logging.LogRecord) -> None:
    value = getattr(record, "port", None)
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 65_535:
        payload["port"] = value


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
        ensure_private_directory(log_path.parent)
        require_regular_file(log_path, missing_ok=True)
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
            handler = new_handler
        else:
            handler.setLevel(logging.NOTSET)
            handler.setFormatter(_JsonlFormatter())
        require_safe_directory(log_path.parent)
        require_regular_file(log_path)
        if handler.stream is None:
            raise OSError
        require_file_descriptor_identity(log_path, handler.stream.fileno())
    except (OSError, ValueError):
        setup_failed = True

    if setup_failed:
        for configured_handler in list(logger.handlers):
            if not getattr(configured_handler, _HANDLER_MARKER, False):
                continue
            logger.removeHandler(configured_handler)
            with suppress(OSError):
                configured_handler.close()
            if configured_handler is new_handler:
                new_handler = None
        if new_handler is not None:
            with suppress(OSError):
                new_handler.close()
        raise LoggingSetupError() from None

    logger.propagate = False
    return logger
