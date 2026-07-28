"""Regression tests for safe logging handler initialization failures."""

from __future__ import annotations

import logging
import traceback
from io import StringIO
from pathlib import Path

import pytest

from fakedetector.config.models import LoggingConfig
from fakedetector.logging_setup import LoggingSetupError, configure_logging


@pytest.fixture
def application_logger():
    logger = logging.getLogger("fakedetector")
    initial_handlers = list(logger.handlers)
    try:
        yield logger
    finally:
        for handler in list(logger.handlers):
            if handler in initial_handlers:
                continue
            logger.removeHandler(handler)
            handler.close()


def test_file_handler_oserror_is_converted_without_leaking_details(
    tmp_path: Path,
    monkeypatch,
    application_logger: logging.Logger,
) -> None:
    unsafe_detail = "unsafe-system-detail"
    log_path = tmp_path / "private" / "application.jsonl"
    initial_handlers = list(application_logger.handlers)

    def fail_file_handler(*args: object, **kwargs: object) -> logging.FileHandler:
        raise OSError(f"cannot open {log_path}: {unsafe_detail}")

    monkeypatch.setattr(logging, "FileHandler", fail_file_handler)

    with pytest.raises(LoggingSetupError) as exc_info:
        configure_logging(LoggingConfig(jsonl_path=str(log_path)))

    error = exc_info.value
    traceback_text = "".join(traceback.format_exception(error))
    assert str(error) == "Logging initialization failed."
    assert str(log_path) not in str(error)
    assert unsafe_detail not in str(error)
    assert str(log_path) not in traceback_text
    assert unsafe_detail not in traceback_text
    assert error.__cause__ is None
    assert error.__context__ is None
    assert application_logger.handlers == initial_handlers


def test_mkdir_oserror_preserves_foreign_handlers(
    tmp_path: Path,
    monkeypatch,
    application_logger: logging.Logger,
) -> None:
    initial_handlers = list(application_logger.handlers)
    foreign_handler = logging.StreamHandler(StringIO())
    application_logger.addHandler(foreign_handler)
    log_path = tmp_path / "private" / "application.jsonl"

    def fail_mkdir(self: Path, *, parents: bool, exist_ok: bool) -> None:
        raise OSError("unsafe directory detail")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(LoggingSetupError) as exc_info:
        configure_logging(LoggingConfig(jsonl_path=str(log_path)))

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert application_logger.handlers == [*initial_handlers, foreign_handler]


def test_partially_configured_handler_is_closed_and_not_registered(
    tmp_path: Path,
    monkeypatch,
    application_logger: logging.Logger,
) -> None:
    created_handlers: list[logging.FileHandler] = []
    original_file_handler = logging.FileHandler

    def tracking_file_handler(
        *args: object,
        **kwargs: object,
    ) -> logging.FileHandler:
        handler = original_file_handler(*args, **kwargs)
        created_handlers.append(handler)
        return handler

    def fail_set_formatter(
        self: logging.FileHandler,
        fmt: logging.Formatter | None,
    ) -> None:
        raise ValueError("unsafe formatter detail")

    monkeypatch.setattr(logging, "FileHandler", tracking_file_handler)
    monkeypatch.setattr(original_file_handler, "setFormatter", fail_set_formatter)

    with pytest.raises(LoggingSetupError):
        configure_logging(
            LoggingConfig(jsonl_path=str(tmp_path / "application.jsonl"))
        )

    assert len(created_handlers) == 1
    assert created_handlers[0] not in application_logger.handlers
    assert created_handlers[0].stream is None
