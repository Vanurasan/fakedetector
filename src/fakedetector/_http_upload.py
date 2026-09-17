"""Bounded multipart receive and parse boundary for HTTP upload adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress

from python_multipart.multipart import parse_options_header
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect, Request

from fakedetector.config.models import AppConfig

_BYTES_PER_MEBIBYTE = 1024 * 1024
_MULTIPART_ENVELOPE_BYTES = 1024 * 1024


class RequestBodyTooLargeError(Exception):
    """Signal an actual or unambiguously declared body above the global cap."""


class RequestBodyDeadlineError(Exception):
    """Signal that bounded request receive or multipart parsing missed its deadline."""


class _BodyStreamState:
    """Track whether the underlying ASGI request stream ended normally."""

    def __init__(self) -> None:
        self.completed = False


class _CompleteMultiPartParser(MultiPartParser):
    """Expose python-multipart's documented end callback as a completion signal."""

    message_complete = False

    def on_end(self) -> None:
        self.message_complete = True
        super().on_end()


def multipart_body_limit_bytes(config: AppConfig) -> int:
    """Return max configured media bytes plus the fixed multipart envelope."""
    limits = config.limits.max_file_size_mb
    return (
        max(limits.image, limits.audio, limits.video) * _BYTES_PER_MEBIBYTE
        + _MULTIPART_ENVELOPE_BYTES
    )


async def parse_bounded_multipart(
    request: Request,
    *,
    body_limit_bytes: int,
    timeout_seconds: float,
    max_files: int,
    max_fields: int,
) -> FormData:
    """Receive and parse one form without retaining an unbounded request body."""
    if body_limit_bytes < 0:
        raise ValueError("body_limit_bytes must not be negative")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if max_files < 0 or max_fields < 0:
        raise ValueError("multipart item limits must not be negative")

    deadline_at = _monotonic_time() + timeout_seconds
    _reject_oversized_content_length(request, body_limit_bytes)
    _raise_if_deadline_expired(deadline_at)
    stream_state = _BodyStreamState()
    stream = _bounded_body_stream(
        request,
        body_limit_bytes,
        deadline_at=deadline_at,
        state=stream_state,
    )
    parser: _CompleteMultiPartParser | None = None
    parsed = False
    deadline = asyncio.timeout(timeout_seconds)
    try:
        async with deadline:
            _raise_if_deadline_expired(deadline_at)
            content_type, _ = parse_options_header(request.headers.get("content-type"))
            if content_type != b"multipart/form-data":
                async for _chunk in stream:
                    pass
                _raise_if_deadline_expired(deadline_at)
                parsed = True
                return FormData()

            parser = _CompleteMultiPartParser(
                request.headers,
                stream,
                max_files=max_files,
                max_fields=max_fields,
                max_part_size=_MULTIPART_ENVELOPE_BYTES,
            )
            form = await parser.parse()
            _raise_if_deadline_expired(deadline_at)
            if not stream_state.completed or not parser.message_complete:
                raise MultiPartException("Multipart body did not terminate cleanly.")
            parsed = True
            return form
    except ClientDisconnect:
        raise MultiPartException("Multipart body ended before ASGI stream completion.") from None
    except TimeoutError:
        if deadline.expired():
            raise RequestBodyDeadlineError from None
        raise
    finally:
        if parser is not None and not parsed:
            _close_parser_files_on_error(parser)


async def _bounded_body_stream(
    request: Request,
    body_limit_bytes: int,
    *,
    deadline_at: float,
    state: _BodyStreamState,
) -> AsyncGenerator[bytes, None]:
    received_bytes = 0
    _raise_if_deadline_expired(deadline_at)
    async for chunk in request.stream():
        _raise_if_deadline_expired(deadline_at)
        received_bytes += len(chunk)
        if received_bytes > body_limit_bytes:
            raise RequestBodyTooLargeError
        yield chunk
        _raise_if_deadline_expired(deadline_at)
    state.completed = True


def _monotonic_time() -> float:
    return asyncio.get_running_loop().time()


def _raise_if_deadline_expired(deadline_at: float) -> None:
    if _monotonic_time() >= deadline_at:
        raise RequestBodyDeadlineError


def _close_parser_files_on_error(parser: MultiPartParser) -> None:
    # Starlette has no public cleanup hook for files created before FormData exists.
    # Keep its error-owned spool registry access isolated to this compatibility seam.
    for file in parser._files_to_close_on_error:
        with suppress(OSError):
            file.close()


def _reject_oversized_content_length(request: Request, body_limit_bytes: int) -> None:
    values = request.headers.getlist("content-length")
    if len(values) != 1:
        return
    value = values[0].strip()
    if not value or not value.isascii() or not value.isdecimal():
        return
    if int(value) > body_limit_bytes:
        raise RequestBodyTooLargeError
