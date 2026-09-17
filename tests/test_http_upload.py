"""Unit tests for the bounded HTTP receive and multipart parse boundary."""

from __future__ import annotations

import asyncio
import tempfile

import pytest
import starlette.formparsers as starlette_formparsers
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.requests import Request
from starlette.types import Message

import fakedetector._http_upload as http_upload_module
from fakedetector._http_upload import (
    RequestBodyDeadlineError,
    RequestBodyTooLargeError,
    parse_bounded_multipart,
)

_BOUNDARY = "fakedetector-boundary"


def _file_part(
    payload: bytes,
    *,
    field_name: str = "file",
    filename: str = "sample.png",
) -> bytes:
    return (
        f'Content-Disposition: form-data; name="{field_name}"; '
        f'filename="{filename}"\r\n'
        "Content-Type: image/png\r\n"
        "\r\n"
    ).encode() + payload


def _field_part(field_name: str, payload: bytes) -> bytes:
    return (
        f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode()
        + payload
    )


def _multipart_message(parts: list[bytes], *, complete: bool) -> bytes:
    separator = f"\r\n--{_BOUNDARY}\r\n".encode()
    body = f"--{_BOUNDARY}\r\n".encode() + separator.join(parts)
    if complete:
        body += f"\r\n--{_BOUNDARY}--\r\n".encode()
    return body


def _multipart_body(payload: bytes = b"payload") -> bytes:
    return _multipart_message([_file_part(payload)], complete=True)


class _ManualClock:
    def __init__(self, initial: float = 0.0) -> None:
        self.now = initial

    def __call__(self) -> float:
        return self.now


class _AdvancingClock:
    def __init__(self, step: float) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        current = self.now
        self.now += self.step
        return current


def _track_spooled_files(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tempfile.SpooledTemporaryFile[bytes]]:
    created: list[tempfile.SpooledTemporaryFile[bytes]] = []

    def create_spooled_file(*args: object, **kwargs: object):
        # The real parser owns and must close this returned spool.
        file = tempfile.SpooledTemporaryFile(*args, **kwargs)  # noqa: SIM115
        created.append(file)
        return file

    monkeypatch.setattr(
        starlette_formparsers,
        "SpooledTemporaryFile",
        create_spooled_file,
    )
    return created


def _advance_clock_after_stream(
    monkeypatch: pytest.MonkeyPatch,
    request: Request,
    clock: _ManualClock,
    *,
    elapsed: float,
) -> None:
    original_stream = request.stream

    async def stream():
        async for chunk in original_stream():
            yield chunk
        clock.now = elapsed

    monkeypatch.setattr(request, "stream", stream)


def _request(
    chunks: list[bytes],
    *,
    content_length: str | None = None,
    stream_completed: bool = True,
) -> Request:
    messages: list[Message] = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": not stream_completed or index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]

    async def receive() -> Message:
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    headers = [(b"content-type", f"multipart/form-data; boundary={_BOUNDARY}".encode())]
    if content_length is not None:
        headers.append((b"content-length", content_length.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/upload",
            "raw_path": b"/upload",
            "query_string": b"",
            "headers": headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
    )


def _parse(request: Request, *, body_limit_bytes: int, timeout_seconds: float = 1.0):
    return asyncio.run(
        parse_bounded_multipart(
            request,
            body_limit_bytes=body_limit_bytes,
            timeout_seconds=timeout_seconds,
            max_files=2,
            max_fields=2,
        )
    )


def test_exact_actual_body_cap_is_accepted_without_whole_body_buffering() -> None:
    body = _multipart_body()
    request = _request([body[:17], body[17:]], content_length=None)

    form = _parse(request, body_limit_bytes=len(body))

    try:
        assert isinstance(form.get("file"), UploadFile)
    finally:
        asyncio.run(form.close())


def test_large_upload_uses_starlette_spooled_file_instead_of_request_body_buffer() -> None:
    body = _multipart_body(b"x" * (1024 * 1024 + 1))
    request = _request(
        [body[index : index + 64 * 1024] for index in range(0, len(body), 64 * 1024)]
    )

    form = _parse(request, body_limit_bytes=len(body))

    try:
        upload = form.get("file")
        assert isinstance(upload, UploadFile)
        assert upload.size == 1024 * 1024 + 1
        assert upload.file._rolled is True
    finally:
        asyncio.run(form.close())


@pytest.mark.parametrize(
    "body",
    [
        _multipart_message(
            [_file_part(b"one", filename="one.png"), _file_part(b"two", filename="two.png")],
            complete=False,
        ),
        _multipart_message(
            [_file_part(b"one"), _field_part("unexpected", b"value")],
            complete=False,
        ),
        _multipart_message(
            [_file_part(b"one"), _field_part("source_context", b'{"channel":"api"}')],
            complete=False,
        ),
        _multipart_message([_file_part(b"incomplete")], complete=False),
    ],
    ids=[
        "completed-file-truncated-duplicate",
        "completed-file-truncated-unknown-field",
        "completed-file-truncated-source-context",
        "truncated-first-file",
    ],
)
def test_real_parser_rejects_multipart_without_complete_closing_boundary(
    body: bytes,
) -> None:
    request = _request([body])

    with pytest.raises(MultiPartException):
        _parse(request, body_limit_bytes=len(body))


def test_incomplete_real_parser_closes_partial_framework_spool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spooled_files = _track_spooled_files(monkeypatch)
    body = _multipart_message([_file_part(b"partial")], complete=False)

    with pytest.raises(MultiPartException):
        _parse(_request([body]), body_limit_bytes=len(body))

    assert len(spooled_files) == 1
    assert spooled_files[0].closed is True


def test_completed_parser_message_requires_completed_asgi_body_stream() -> None:
    body = _multipart_body()
    request = _request([body], stream_completed=False)

    with pytest.raises(MultiPartException):
        _parse(request, body_limit_bytes=len(body))


@pytest.mark.parametrize("content_length", [None, "1"])
def test_actual_byte_count_rejects_cap_plus_one_independent_of_content_length(
    content_length: str | None,
) -> None:
    body = _multipart_body()
    request = _request([body[:23], body[23:]], content_length=content_length)

    with pytest.raises(RequestBodyTooLargeError):
        _parse(request, body_limit_bytes=len(body) - 1)


def test_unambiguously_oversized_content_length_rejects_before_receive() -> None:
    receive_called = False

    async def receive() -> Message:
        nonlocal receive_called
        receive_called = True
        raise AssertionError("body receive must not start")

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/upload",
            "raw_path": b"/upload",
            "query_string": b"",
            "headers": [
                (b"content-type", f"multipart/form-data; boundary={_BOUNDARY}".encode()),
                (b"content-length", b"101"),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
    )

    with pytest.raises(RequestBodyTooLargeError):
        _parse(request, body_limit_bytes=100)

    assert receive_called is False


def test_receive_deadline_is_safe_and_deterministic() -> None:
    async def receive() -> Message:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/upload",
            "raw_path": b"/upload",
            "query_string": b"",
            "headers": [
                (b"content-type", f"multipart/form-data; boundary={_BOUNDARY}".encode())
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
    )

    with pytest.raises(RequestBodyDeadlineError):
        _parse(request, body_limit_bytes=1024, timeout_seconds=0.01)


def test_non_suspending_receive_checks_elapsed_deadline_between_ready_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _multipart_body()
    monkeypatch.setattr(http_upload_module, "_monotonic_time", _AdvancingClock(0.2))

    with pytest.raises(RequestBodyDeadlineError):
        _parse(
            _request([bytes([byte]) for byte in body]),
            body_limit_bytes=len(body),
            timeout_seconds=1.0,
        )


def test_final_deadline_check_rejects_parser_completion_after_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _ManualClock()
    monkeypatch.setattr(http_upload_module, "_monotonic_time", clock)
    body = _multipart_body()
    request = _request([body])
    _advance_clock_after_stream(monkeypatch, request, clock, elapsed=2.0)

    with pytest.raises(RequestBodyDeadlineError):
        _parse(request, body_limit_bytes=len(body), timeout_seconds=1.0)


def test_elapsed_deadline_closes_partial_real_parser_spool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spooled_files = _track_spooled_files(monkeypatch)
    clock = _ManualClock()
    monkeypatch.setattr(http_upload_module, "_monotonic_time", clock)
    body = _multipart_message([_file_part(b"partial")], complete=False)
    request = _request([body])
    _advance_clock_after_stream(monkeypatch, request, clock, elapsed=2.0)

    with pytest.raises(RequestBodyDeadlineError):
        _parse(request, body_limit_bytes=len(body), timeout_seconds=1.0)

    assert len(spooled_files) == 1
    assert spooled_files[0].closed is True
