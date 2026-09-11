"""Contract tests for the server-rendered Stage 8 WebUI."""

from __future__ import annotations

from base64 import b64encode
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from stage8_helpers import (
    StubApplicationService,
    make_config,
    make_error,
    make_rejected_result,
    make_status,
)

from fakedetector.app import create_app
from fakedetector.application import (
    AnalysisInternalError,
    AnalysisNotFoundError,
    AnalysisPendingError,
    AnalysisPersistenceUnavailableError,
    AnalysisSubmission,
)
from fakedetector.auth import WebUIBasicAuthenticator
from fakedetector.domain import AnalysisStatus, ProcessingStage
from fakedetector.webui import install_webui, is_same_origin

AUTH = ("analyst", "stage8-password")
SAME_ORIGIN = {"Origin": "http://testserver"}
VALID_BASIC_PAYLOAD = b64encode(b"analyst:stage8-password").decode("ascii")


def _basic_authorization(credentials: bytes) -> str:
    return f"Basic {b64encode(credentials).decode('ascii')}"


def _asgi_request_with_security_header(
    *,
    scheme: str,
    host: str,
    header_name: str,
    header_value: str,
) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": scheme,
            "path": "/analyses",
            "raw_path": b"/analyses",
            "query_string": b"",
            "headers": [
                (b"host", host.encode("ascii")),
                (header_name.encode("ascii"), header_value.encode("latin-1")),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


def _client(
    tmp_path: Path,
    service: StubApplicationService,
    *,
    require_auth: bool = True,
) -> TestClient:
    app = FastAPI()
    install_webui(
        app,
        service=service,
        authenticator=(
            WebUIBasicAuthenticator(*AUTH)
            if require_auth
            else None
        ),
        config=make_config(tmp_path),
    )
    return TestClient(app)


def test_http_basic_missing_wrong_and_valid_credentials(tmp_path: Path) -> None:
    client = _client(tmp_path, StubApplicationService())

    missing = client.get("/")
    wrong = client.get("/", auth=("analyst", "wrong"))
    valid = client.get("/", auth=AUTH)

    for response in (missing, wrong):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Basic realm="FakeDetector"'
        assert "Запрос не выполнен" in response.text
        assert "Not authenticated" not in response.text
    assert "authentication_required" in missing.text
    assert "authentication_failed" in wrong.text
    assert valid.status_code == 200


@pytest.mark.parametrize(
    "authorization",
    [
        f"Basic !!!{VALID_BASIC_PAYLOAD}",
        f"Basic {VALID_BASIC_PAYLOAD[:8]}!{VALID_BASIC_PAYLOAD[8:]}",
        f"Basic {VALID_BASIC_PAYLOAD.rstrip('=')}",
        _basic_authorization(b"analyst"),
    ],
    ids=[
        "invalid-prefix",
        "invalid-middle",
        "invalid-padding",
        "missing-delimiter",
    ],
)
def test_http_basic_malformed_payloads_are_safe_401_pages(
    tmp_path: Path,
    authorization: str,
) -> None:
    response = _client(tmp_path, StubApplicationService()).get(
        "/",
        headers={"Authorization": authorization},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="FakeDetector"'
    assert response.headers["content-type"].startswith("text/html")
    assert "authentication_failed" in response.text
    assert "Запрос не выполнен" in response.text
    assert "Not authenticated" not in response.text


def test_upload_page_shows_formats_limits_and_disclaimer(tmp_path: Path) -> None:
    response = _client(tmp_path, StubApplicationService()).get("/", auth=AUTH)

    assert response.status_code == 200
    assert "jpg, jpeg, png, webp" in response.text
    assert "20 МБ" in response.text
    assert "не является окончательной экспертной экспертизой" in response.text


def test_upload_page_locks_submit_button_after_form_submission(tmp_path: Path) -> None:
    response = _client(tmp_path, StubApplicationService()).get("/", auth=AUTH)

    assert 'id="analysis-upload"' in response.text
    assert '.addEventListener("submit"' in response.text
    assert 'document.getElementById("analysis-submit").disabled = true' in response.text


def test_same_origin_post_is_accepted_and_maps_webui_source(tmp_path: Path) -> None:
    service = StubApplicationService()

    response = _client(tmp_path, service).post(
        "/analyses",
        files={"file": ("sample.png", b"png", "image/png")},
        headers=SAME_ORIGIN,
        auth=AUTH,
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/analyses/analysis-001"
    assert service.sources[0].channel.value == "webui"


def test_same_origin_referer_is_accepted_when_origin_is_absent(tmp_path: Path) -> None:
    service = StubApplicationService()

    response = _client(tmp_path, service).post(
        "/analyses",
        files={"file": ("sample.png", b"png", "image/png")},
        headers={"Referer": "http://testserver/"},
        auth=AUTH,
        follow_redirects=False,
    )

    assert response.status_code == 303


@pytest.mark.parametrize(
    ("scheme", "host", "header_name", "header_value"),
    [
        ("http", "testserver", "origin", "http://testserver:80"),
        ("https", "testserver", "referer", "https://testserver:443/form"),
        ("http", "testserver:8080", "origin", "http://testserver:8080"),
        ("http", "127.0.0.1:8080", "origin", "http://127.0.0.1:8080"),
        ("http", "[2001:db8::1]", "origin", "http://[2001:db8::1]"),
        (
            "http",
            "[2001:db8::1]:8080",
            "referer",
            "http://[2001:db8::1]:8080/form",
        ),
    ],
)
def test_same_origin_preserves_port_and_ipv6_normalization(
    scheme: str,
    host: str,
    header_name: str,
    header_value: str,
) -> None:
    request = _asgi_request_with_security_header(
        scheme=scheme,
        host=host,
        header_name=header_name,
        header_value=header_value,
    )

    assert is_same_origin(request)


@pytest.mark.parametrize("header_name", ["origin", "referer"])
def test_same_origin_rejects_all_ascii_control_characters_before_normalization(
    header_name: str,
) -> None:
    for codepoint in (*range(0x20), 0x7F):
        request = _asgi_request_with_security_header(
            scheme="http",
            host="testserver",
            header_name=header_name,
            header_value=f"http://test{chr(codepoint)}server",
        )

        assert not is_same_origin(request), f"accepted U+{codepoint:04X}"


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://test\tserver"},
        {"Origin": "http://test\x00server"},
        {"Referer": "http://test\tserver/form"},
        {"Referer": "http://test\x7fserver/form"},
    ],
    ids=["origin-htab", "origin-nul", "referer-htab", "referer-del"],
)
def test_control_characters_are_rejected_before_multipart_and_application(
    tmp_path: Path,
    headers: dict[str, str],
) -> None:
    service = StubApplicationService()

    response = _client(tmp_path, service).post(
        "/analyses",
        content=b"not-a-valid-multipart-body",
        headers={"Content-Type": "multipart/form-data", **headers},
        auth=AUTH,
    )

    assert response.status_code == 403
    assert "same_origin_required" in response.text
    assert "invalid_multipart" not in response.text
    assert service.sources == []


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "null"},
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver/"},
        {"Origin": "http://testserver/unsafe/path"},
        {"Referer": "http://evil.example/form"},
    ],
)
def test_mutating_post_rejects_missing_malformed_or_cross_origin_evidence(
    tmp_path: Path,
    headers: dict[str, str],
) -> None:
    service = StubApplicationService()

    response = _client(tmp_path, service).post(
        "/analyses",
        files={"file": ("sample.png", b"png", "image/png")},
        headers=headers,
        auth=AUTH,
    )

    assert response.status_code == 403
    assert "same_origin_required" in response.text
    assert service.sources == []


def test_malformed_multipart_is_rejected_only_after_auth_and_origin_guards(
    tmp_path: Path,
) -> None:
    service = StubApplicationService()
    client = _client(tmp_path, service)
    malformed_headers = {"Content-Type": "multipart/form-data"}
    malformed_authorization = f"Basic !!!{VALID_BASIC_PAYLOAD}"

    missing_auth = client.post(
        "/analyses",
        content=b"not-a-valid-multipart-body",
        headers=malformed_headers,
    )
    malformed_auth_before_origin = client.post(
        "/analyses",
        content=b"not-a-valid-multipart-body",
        headers={
            **malformed_headers,
            "Origin": "https://evil.example",
            "Authorization": malformed_authorization,
        },
    )
    malformed_auth_before_multipart = client.post(
        "/analyses",
        content=b"not-a-valid-multipart-body",
        headers={
            **malformed_headers,
            **SAME_ORIGIN,
            "Authorization": malformed_authorization,
        },
    )
    cross_origin = client.post(
        "/analyses",
        content=b"not-a-valid-multipart-body",
        headers={**malformed_headers, "Origin": "https://evil.example"},
        auth=AUTH,
    )
    same_origin = client.post(
        "/analyses",
        content=b"not-a-valid-multipart-body",
        headers={**malformed_headers, **SAME_ORIGIN},
        auth=AUTH,
    )

    assert missing_auth.status_code == 401
    assert missing_auth.headers["www-authenticate"] == 'Basic realm="FakeDetector"'
    assert "authentication_required" in missing_auth.text
    for response in (malformed_auth_before_origin, malformed_auth_before_multipart):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Basic realm="FakeDetector"'
        assert "authentication_failed" in response.text
        assert "same_origin_required" not in response.text
        assert "invalid_multipart" not in response.text
    assert cross_origin.status_code == 403
    assert "same_origin_required" in cross_origin.text
    assert same_origin.status_code == 400
    assert "invalid_multipart" in same_origin.text
    assert "Missing boundary" not in same_origin.text
    assert service.sources == []


def test_missing_and_empty_upload_are_safe_400_pages(tmp_path: Path) -> None:
    client = _client(tmp_path, StubApplicationService())
    missing = client.post("/analyses", headers=SAME_ORIGIN, auth=AUTH)
    empty = client.post(
        "/analyses",
        files={"file": ("empty.png", b"", "image/png")},
        headers=SAME_ORIGIN,
        auth=AUTH,
    )

    assert missing.status_code == 400
    assert "file_missing" in missing.text
    assert empty.status_code == 400
    assert "file_empty" in empty.text


def test_pending_status_contains_meta_refresh(tmp_path: Path) -> None:
    response = _client(tmp_path, StubApplicationService()).get(
        "/analyses/analysis-001",
        auth=AUTH,
    )

    assert response.status_code == 200
    assert 'http-equiv="refresh"' in response.text
    assert "analysis" in response.text


def test_ready_status_redirects_to_result(tmp_path: Path) -> None:
    service = StubApplicationService()
    service.status = make_status(
        status=AnalysisStatus.COMPLETED,
        stage=ProcessingStage.FINISHED,
        result_available=True,
    )

    response = _client(tmp_path, service).get(
        "/analyses/analysis-001",
        auth=AUTH,
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/analyses/analysis-001/result"


def test_result_page_renders_canonical_result_without_recalculation(tmp_path: Path) -> None:
    service = StubApplicationService()

    response = _client(tmp_path, service).get(
        "/analyses/analysis-001/result",
        auth=AUTH,
    )

    assert response.status_code == 200
    assert service.result.analysis_id in response.text
    assert service.result.risk_assessment is not None
    assert service.result.risk_assessment.final_level.value in response.text
    assert service.result.completeness.explanation in response.text
    assert service.result.recommendation is not None
    assert service.result.recommendation.text in response.text
    assert "не заменяет окончательную экспертную экспертизу" in response.text


def test_result_page_handles_nullable_stage3_result_fields(tmp_path: Path) -> None:
    service = StubApplicationService()
    service.result = make_rejected_result()

    response = _client(tmp_path, service).get(
        "/analyses/analysis-rejected/result",
        auth=AUTH,
    )

    assert response.status_code == 200
    assert "Оценка отсутствует" in response.text
    assert "unsupported_extension" in response.text


def test_result_pending_is_consistent_202_status_page(tmp_path: Path) -> None:
    service = StubApplicationService()
    service.result_error = AnalysisPendingError(service.status)

    response = _client(tmp_path, service).get(
        "/analyses/analysis-001/result",
        auth=AUTH,
    )

    assert response.status_code == 202
    assert 'http-equiv="refresh"' in response.text


def test_immediate_rejection_has_safe_result_navigation(tmp_path: Path) -> None:
    service = StubApplicationService()
    result = make_rejected_result()
    service.submission = AnalysisSubmission(
        analysis_id=result.analysis_id,
        status=result.status,
        stage=result.stage,
        terminal_result=result,
    )

    response = _client(tmp_path, service).post(
        "/analyses",
        files={"file": ("bad.bin", b"bad", "application/octet-stream")},
        headers=SAME_ORIGIN,
        auth=AUTH,
    )

    assert response.status_code == 415
    assert f"/analyses/{result.analysis_id}/result" in response.text
    assert "unsupported_extension" in response.text


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (AnalysisPersistenceUnavailableError(), 503, "result_write_failed"),
        (AnalysisInternalError(), 500, "internal_error"),
    ],
)
def test_submission_finalization_failures_are_safe_pages(
    tmp_path: Path,
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    service = StubApplicationService()
    service.submit_error = error

    response = _client(tmp_path, service).post(
        "/analyses",
        files={"file": ("sample.png", b"png", "image/png")},
        headers=SAME_ORIGIN,
        auth=AUTH,
    )

    assert response.status_code == expected_status
    assert expected_code in response.text


def test_unknown_and_persistence_failure_have_safe_pages(tmp_path: Path) -> None:
    service = StubApplicationService()
    client = _client(tmp_path, service)
    service.status_error = AnalysisNotFoundError()
    unknown = client.get("/analyses/unknown", auth=AUTH)
    assert unknown.status_code == 404
    assert "result_not_found" in unknown.text

    service.status_error = None
    service.result_error = AnalysisPersistenceUnavailableError()
    unavailable = client.get("/analyses/analysis-001/result", auth=AUTH)
    assert unavailable.status_code == 503
    assert "result_write_failed" in unavailable.text


def test_status_page_maps_live_persistence_failure_to_503(tmp_path: Path) -> None:
    service = StubApplicationService()
    service.status = make_status(
        status=AnalysisStatus.COMPLETED,
        stage=ProcessingStage.PERSISTENCE,
        errors=(make_error("result_write_failed", "storage"),),
    )

    response = _client(tmp_path, service).get(
        "/analyses/analysis-001",
        auth=AUTH,
    )

    assert response.status_code == 503
    assert "result_write_failed" in response.text


def test_internal_failure_page_does_not_leak_paths_or_secrets(tmp_path: Path) -> None:
    service = StubApplicationService()
    service.result_error = RuntimeError("PRIVATE C:\\users\\secret-token")

    response = _client(tmp_path, service).get(
        "/analyses/analysis-001/result",
        auth=AUTH,
    )

    assert response.status_code == 500
    assert "PRIVATE" not in response.text
    assert "secret-token" not in response.text


def test_webui_routes_are_absent_from_openapi_and_static_is_packaged(tmp_path: Path) -> None:
    service = StubApplicationService()
    client = _client(tmp_path, service)
    schema = client.get("/openapi.json").json()

    assert schema["paths"] == {}
    static = client.get("/static/styles.css")
    assert static.status_code == 200
    assert ".container" in static.text


def test_disabled_webui_registers_no_html_or_static_surface(tmp_path: Path) -> None:
    app = create_app(
        make_config(
            tmp_path,
            api_enabled=False,
            webui_enabled=False,
        )
    )
    client = TestClient(app)

    assert client.get("/").status_code == 404
    assert client.get("/analyses/unknown").status_code == 404
    assert client.get("/static/styles.css").status_code == 404
