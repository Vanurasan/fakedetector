"""Bounded multipart receive and parse boundary for HTTP upload adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress

from python_multipart.multipart import parse_options_header
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartParser
from starlette.requests import Request

from fakedetector.config.models import AppConfig

_BYTES_PER_MEBIBYTE = 1024 * 1024
_MULTIPART_ENVELOPE_BYTES = 1024 * 1024


class RequestBodyTooLargeError(Exception):
    """Signal an actual or unambiguously declared body above the global cap."""


class RequestBodyDeadlineError(Exception):
    """Signal that bounded request receive or multipart parsing missed its deadline."""


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

    _reject_oversized_content_length(request, body_limit_bytes)
    stream = _bounded_body_stream(request, body_limit_bytes)
    parser: MultiPartParser | None = None
    parsed = False
    deadline = asyncio.timeout(timeout_seconds)
    try:
        async with deadline:
            content_type, _ = parse_options_header(request.headers.get("content-type"))
            if content_type != b"multipart/form-data":
                async for _chunk in stream:
                    pass
                parsed = True
                return FormData()

            parser = MultiPartParser(
                request.headers,
                stream,
                max_files=max_files,
                max_fields=max_fields,
                max_part_size=_MULTIPART_ENVELOPE_BYTES,
            )
            form = await parser.parse()
            parsed = True
            return form
    except TimeoutError:
        if deadline.expired():
            raise RequestBodyDeadlineError from None
        raise
    finally:
        if parser is not None and not parsed:
            for file in parser._files_to_close_on_error:
                with suppress(OSError):
                    file.close()


async def _bounded_body_stream(
    request: Request,
    body_limit_bytes: int,
) -> AsyncGenerator[bytes, None]:
    received_bytes = 0
    async for chunk in request.stream():
        received_bytes += len(chunk)
        if received_bytes > body_limit_bytes:
            raise RequestBodyTooLargeError
        yield chunk


def _reject_oversized_content_length(request: Request, body_limit_bytes: int) -> None:
    values = request.headers.getlist("content-length")
    if len(values) != 1:
        return
    value = values[0].strip()
    if not value or not value.isascii() or not value.isdecimal():
        return
    if int(value) > body_limit_bytes:
        raise RequestBodyTooLargeError
