"""Bounded HTTP transport without redirects or proxy inheritance."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from . import common

_MAX_HTTP_BODY_BYTES = 2 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


def _http_exchange(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, str], bytes]:
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        response = opener.open(request, timeout=timeout)
    except HTTPError as error:
        response = error
    except URLError as error:
        reason = error.reason
        if isinstance(reason, OSError):
            raise reason from error
        raise OSError("loopback request failed") from None
    with response:
        payload = response.read(_MAX_HTTP_BODY_BYTES + 1)
        if len(payload) > _MAX_HTTP_BODY_BYTES:
            raise common.ReleaseVerificationError("http", "HTTP response exceeded the gate bound.")
        return (
            int(response.status),
            {name.casefold(): value for name, value in response.headers.items()},
            payload,
        )


def _require_http(
    method: str,
    url: str,
    *,
    expected_status: int,
    phase: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 10.0,
) -> tuple[dict[str, str], bytes]:
    try:
        status, response_headers, body = _http_exchange(
            method,
            url,
            headers=headers,
            data=data,
            timeout=timeout,
        )
    except OSError:
        raise common.ReleaseVerificationError(phase, "Loopback HTTP request failed.") from None
    if status != expected_status:
        raise common.ReleaseVerificationError(
            phase,
            f"Expected HTTP {expected_status}, received HTTP {status}.",
        )
    return response_headers, body


def _json_object(body: bytes, *, phase: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise common.ReleaseVerificationError(phase, "HTTP response is not valid JSON.") from None
    if not isinstance(payload, dict):
        raise common.ReleaseVerificationError(phase, "HTTP response JSON is not an object.")
    return payload
