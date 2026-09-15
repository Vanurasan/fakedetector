"""Unit tests for the bounded HTTP receive and multipart parse boundary."""

from __future__ import annotations

import asyncio

import pytest
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.types import Message

import fakedetector._http_upload as http_upload_module
from fakedetector._http_upload import (
    RequestBodyDeadlineError,
    RequestBodyTooLargeError,
    parse_bounded_multipart,
)

_BOUNDARY = "fakedetector-boundary"


def _multipart_body(payload: bytes = b"payload") -> bytes:
    return (
        f"--{_BOUNDARY}\r\n"
        'Content-Disposition: form-data; name="file"; filename="sample.png"\r\n'
        "Content-Type: image/png\r\n"
        "\r\n"
    ).encode() + payload + f"\r\n--{_BOUNDARY}--\r\n".encode()


def _request(
    chunks: list[bytes],
    *,
    content_length: str | None = None,
) -> Request:
    messages: list[Message] = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
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


def test_parse_deadline_closes_partial_framework_spool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CloseProbe:
        closed = False

        def close(self) -> None:
            self.closed = True

    close_probe = CloseProbe()

    class BlockingParser:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self._files_to_close_on_error = [close_probe]

        async def parse(self) -> None:
            await asyncio.Event().wait()

    monkeypatch.setattr(http_upload_module, "MultiPartParser", BlockingParser)
    request = _request([_multipart_body()])

    with pytest.raises(RequestBodyDeadlineError):
        _parse(request, body_limit_bytes=1024, timeout_seconds=0.01)

    assert close_probe.closed is True
