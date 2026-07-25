"""Tests for safe application logging setup."""

from __future__ import annotations

import json
import logging
from io import StringIO
from pathlib import Path

import pytest

from fakedetector.config.models import LoggingConfig
from fakedetector.logging_setup import configure_logging


@pytest.fixture
def logging_config(tmp_path: Path):
    """Provide an isolated logging configuration and clean all test handlers."""
    logger = logging.getLogger("fakedetector")
    initial_handlers = list(logger.handlers)
    config = LoggingConfig(jsonl_path=str(tmp_path / "application.jsonl"))
    configure_logging(config)
    try:
        yield logger, config
    finally:
        for handler in list(logger.handlers):
            if handler in initial_handlers:
                continue
            logger.removeHandler(handler)
            handler.close()


def _add_stream_handler(logger: logging.Logger) -> StringIO:
    stream = StringIO()
    stream_handler = logging.StreamHandler(stream)
    file_handler = next(
        handler for handler in logger.handlers if isinstance(handler, logging.FileHandler)
    )
    stream_handler.setFormatter(file_handler.formatter)
    logger.addHandler(stream_handler)
    return stream


def test_configure_logging_returns_named_logger(logging_config) -> None:
    logger, _ = logging_config

    assert logger.name == "fakedetector"


def test_configure_logging_applies_level(logging_config) -> None:
    _, config = logging_config
    config.level = "DEBUG"

    logger = configure_logging(config)

    assert logger.level == logging.DEBUG


def test_log_record_is_safe_jsonl_with_utc_timestamp(logging_config) -> None:
    logger, _ = logging_config
    stream = _add_stream_handler(logger)

    logger.info(
        "Application is starting.",
        extra={
            "event": "application_starting",
            "schema_version": "1.0",
            "host": "127.0.0.1",
            "port": 8080,
        },
    )

    line = stream.getvalue().strip()
    record = json.loads(line)
    assert record["event"] == "application_starting"
    assert record["level"] == "INFO"
    assert record["logger"] == "fakedetector"
    assert record["message"] == "Application is starting."
    assert record["schema_version"] == "1.0"
    assert record["host"] == "127.0.0.1"
    assert record["port"] == 8080
    assert record["timestamp"].endswith("Z")


def test_unknown_extra_fields_are_not_serialized(logging_config) -> None:
    logger, _ = logging_config
    stream = _add_stream_handler(logger)
    sentinel = "secret-like-sentinel"

    logger.info(
        "Safe startup message.",
        extra={"event": "application_starting", "token": sentinel, "arbitrary": sentinel},
    )

    line = stream.getvalue().strip()
    record = json.loads(line)
    assert sentinel not in line
    assert set(record) <= {
        "timestamp",
        "level",
        "logger",
        "event",
        "message",
        "schema_version",
        "host",
        "port",
    }


def test_one_log_operation_creates_one_jsonl_line(logging_config) -> None:
    logger, _ = logging_config
    stream = _add_stream_handler(logger)

    logger.info("One operation.", extra={"event": "application_starting"})

    assert len(stream.getvalue().splitlines()) == 1


def test_logging_creates_missing_parent_and_writes_jsonl(tmp_path: Path) -> None:
    """A clean nested log path works without a pre-created runtime directory."""
    logger = logging.getLogger("fakedetector")
    initial_handlers = list(logger.handlers)
    log_path = tmp_path / "missing" / "nested" / "application.jsonl"
    config = LoggingConfig(jsonl_path=str(log_path))

    assert not log_path.parent.exists()

    try:
        configure_logging(config)
        assert log_path.parent.is_dir()

        logger.info("Application is starting.", extra={"event": "application_starting"})
        for handler in logger.handlers:
            handler.flush()

        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event"] == "application_starting"
        assert record["logger"] == "fakedetector"
    finally:
        for handler in list(logger.handlers):
            if handler in initial_handlers:
                continue
            logger.removeHandler(handler)
            handler.close()


def test_repeated_configuration_does_not_duplicate_handlers(logging_config) -> None:
    logger, config = logging_config
    initial_handlers = list(logger.handlers)

    configure_logging(config)

    assert logger.handlers == initial_handlers
    assert sum(isinstance(handler, logging.FileHandler) for handler in logger.handlers) == 1


def test_repeated_configuration_preserves_foreign_handler_and_one_record(
    logging_config,
) -> None:
    logger, config = logging_config
    foreign_stream = StringIO()
    foreign_handler = logging.StreamHandler(foreign_stream)
    logger.addHandler(foreign_handler)

    configure_logging(config)
    logger.info("One operation.", extra={"event": "application_starting"})
    for handler in logger.handlers:
        handler.flush()

    assert foreign_handler in logger.handlers
    assert len(foreign_stream.getvalue().splitlines()) == 1
    log_lines = Path(config.jsonl_path).read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 1
