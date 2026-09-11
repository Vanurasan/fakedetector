"""Contract tests for the Stage 8 asynchronous HTTP API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from stage8_helpers import (
    StubApplicationService,
    make_config,
    make_error,
    make_rejected_result,
    make_status,
)

from fakedetector.api import install_api
from fakedetector.app import create_app
from fakedetector.application import (
    AnalysisInternalError,
    AnalysisNotFoundError,
    AnalysisPendingError,
    AnalysisPersistenceUnavailableError,
    AnalysisSubmission,
    AnalysisSubmissionError,
)
from fakedetector.auth import APIBearerAuthenticator
from fakedetector.domain import AnalysisStatus, ProcessingStage

TOKEN = "stage8-api-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _client(
    service: StubApplicationService,
    *,
    require_auth: bool = True,
) -> TestClient:
    app = FastAPI()
    install_api(
        app,
        service=service,
        authenticator=APIBearerAuthenticator(TOKEN) if require_auth else None,
    )
    return TestClient(app)


def _upload(
    client: TestClient,
    *,
    source_context: str | None = None,
    headers: dict[str, str] | None = None,
):
    data = {} if source_context is None else {"source_context": source_context}
    return client.post(
        "/api/v1/analyses",
        files={"file": ("sample.png", b"png-bytes", "image/png")},
        data=data,
        headers=AUTH if headers is None else headers,
    )


def _malformed_multipart(
    client: TestClient,
    *,
    authorization: str | None,
):
    headers = {"Content-Type": "multipart/form-data"}
    if authorization is not None:
        headers["Authorization"] = authorization
    return client.post(
        "/api/v1/analyses",
        content=b"not-a-valid-multipart-body",
        headers=headers,
    )


def test_accepted_multipart_upload_uses_factual_sampled_state_and_default_source() -> None:
    service = StubApplicationService()
    service.submission = AnalysisSubmission(
        analysis_id="analysis-fast",
        status=AnalysisStatus.COMPLETED,
        stage=ProcessingStage.PERSISTENCE,
        terminal_result=None,
    )

    response = _upload(_client(service))

    assert response.status_code == 202
    assert response.json() == {
        "analysis_id": "analysis-fast",
        "status": "completed",
        "stage": "persistence",
        "status_url": "/api/v1/analyses/analysis-fast",
        "result_url": "/api/v1/analyses/analysis-fast/result",
    }
    assert service.sources[0].model_dump(mode="json") == {
        "channel": "api",
        "connector": None,
        "external_system": None,
        "external_reference": None,
    }


@pytest.mark.parametrize(
    ("original_name", "declared_content_type", "payload"),
    [
        ("sample.png", "image/png", b"image-transport"),
        ("sample.wav", "audio/wav", b"audio-transport"),
        ("sample.mp4", "video/mp4", b"video-transport"),
    ],
)
def test_multipart_transport_preserves_each_media_boundary_input(
    original_name: str,
    declared_content_type: str,
    payload: bytes,
) -> None:
    service = StubApplicationService()
    source = {
        "channel": "api",
        "connector": "transport-test",
        "external_system": None,
        "external_reference": original_name,
    }

    response = _client(service).post(
        "/api/v1/analyses",
        files={"file": (original_name, payload, declared_content_type)},
        data={"source_context": json.dumps(source)},
        headers=AUTH,
    )

    assert response.status_code == 202
    assert service.original_names == [original_name]
    assert service.declared_content_types == [declared_content_type]
    assert service.payloads == [payload]
    assert service.sources[0].model_dump(mode="json") == source


def test_valid_api_source_context_is_attribution_only() -> None:
    service = StubApplicationService()
    source = {
        "channel": "api",
        "connector": "mail_connector",
        "external_system": "gateway",
        "external_reference": "mail-42",
    }

    response = _upload(_client(service), source_context=json.dumps(source))

    assert response.status_code == 202
    assert service.sources[0].model_dump(mode="json") == source


@pytest.mark.parametrize(
    ("source_context", "expected_status", "expected_code"),
    [
        ("{broken", 400, "invalid_source_context_json"),
        ("[]", 422, "invalid_source_context"),
        ("{}", 422, "invalid_source_context"),
        ('{"channel":"webui"}', 422, "invalid_source_context"),
        ('{"channel":"api","unknown":"value"}', 422, "invalid_source_context"),
    ],
)
def test_invalid_source_context_fails_before_submission(
    source_context: str,
    expected_status: int,
    expected_code: str,
) -> None:
    service = StubApplicationService()

    response = _upload(_client(service), source_context=source_context)

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert "analysis_id" not in response.json()
    assert service.sources == []


def test_malformed_multipart_is_rejected_only_after_bearer_guard() -> None:
    service = StubApplicationService()
    client = _client(service)

    missing = _malformed_multipart(client, authorization=None)
    invalid = _malformed_multipart(client, authorization="Bearer wrong")
    valid = _malformed_multipart(client, authorization=f"Bearer {TOKEN}")

    for response in (missing, invalid):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"]["category"] == "authentication"
    assert missing.json()["error"]["code"] == "authentication_required"
    assert invalid.json()["error"]["code"] == "authentication_failed"
    assert valid.status_code == 400
    assert valid.json()["error"]["code"] == "invalid_multipart"
    assert set(valid.json()) == {"error", "request_id"}
    assert service.sources == []


def test_missing_and_empty_file_are_transport_400_without_analysis_id() -> None:
    service = StubApplicationService()
    client = _client(service)

    missing = client.post("/api/v1/analyses", headers=AUTH)
    empty = client.post(
        "/api/v1/analyses",
        files={"file": ("empty.png", b"", "image/png")},
        headers=AUTH,
    )

    assert (missing.status_code, missing.json()["error"]["code"]) == (400, "file_missing")
    assert (empty.status_code, empty.json()["error"]["code"]) == (400, "file_empty")
    assert "analysis_id" not in missing.json()
    assert "analysis_id" not in empty.json()
    assert service.sources == []


@pytest.mark.parametrize(
    ("code", "category", "expected_status"),
    [
        ("file_too_large", "resource_limit", 413),
        ("unsupported_extension", "unsupported_media", 415),
        ("unsupported_mime_type", "unsupported_media", 415),
        ("file_signature_mismatch", "validation", 415),
        ("unsafe_or_unreadable_file", "validation", 422),
    ],
)
def test_persisted_stage3_rejection_uses_mixed_http_semantics_and_links(
    code: str,
    category: str,
    expected_status: int,
) -> None:
    service = StubApplicationService()
    result = make_rejected_result(code=code, category=category)
    service.submission = AnalysisSubmission(
        analysis_id=result.analysis_id,
        status=result.status,
        stage=result.stage,
        terminal_result=result,
    )

    response = _upload(_client(service))

    assert response.status_code == expected_status
    payload = response.json()
    assert payload["error"]["code"] == code
    assert payload["analysis_id"] == result.analysis_id
    assert payload["status_url"].endswith(result.analysis_id)
    assert payload["result_url"].endswith(f"{result.analysis_id}/result")


def test_persisted_stage3_failed_is_safe_500_with_links() -> None:
    service = StubApplicationService()
    result = make_rejected_result(
        status=AnalysisStatus.FAILED,
        code="internal_error",
        category="internal",
    )
    service.submission = AnalysisSubmission(
        analysis_id=result.analysis_id,
        status=result.status,
        stage=result.stage,
        terminal_result=result,
    )

    response = _upload(_client(service))

    assert response.status_code == 500
    assert response.json()["analysis_id"] == result.analysis_id


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (AnalysisSubmissionError(), 500, "internal_error"),
        (AnalysisPersistenceUnavailableError(), 503, "result_write_failed"),
        (AnalysisInternalError(), 500, "internal_error"),
    ],
)
def test_submission_failures_do_not_promise_an_id_or_links(
    error: Exception,
    status: int,
    code: str,
) -> None:
    service = StubApplicationService()
    service.submit_error = error

    response = _upload(_client(service))

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert set(response.json()) == {"error", "request_id"}


def test_status_returns_all_factual_nullable_timestamps_without_updated_at() -> None:
    service = StubApplicationService()

    response = _client(service).get("/api/v1/analyses/analysis-001", headers=AUTH)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "analysis_id",
        "status",
        "stage",
        "created_at",
        "queued_at",
        "started_at",
        "finished_at",
        "result_available",
        "errors",
    }
    assert payload["finished_at"] is None
    assert "updated_at" not in payload


def test_status_exposes_accepted_persistence_failure_without_result_availability() -> None:
    service = StubApplicationService()
    service.status = make_status(
        status=AnalysisStatus.COMPLETED,
        stage=ProcessingStage.PERSISTENCE,
        errors=(make_error("result_write_failed", "storage"),),
    )

    response = _client(service).get("/api/v1/analyses/analysis-001", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["stage"] == "persistence"
    assert response.json()["result_available"] is False
    assert response.json()["errors"][0]["code"] == "result_write_failed"


def test_result_ready_pending_unknown_persistence_and_internal_semantics() -> None:
    service = StubApplicationService()
    client = _client(service)

    ready = client.get("/api/v1/analyses/analysis-001/result", headers=AUTH)
    assert ready.status_code == 200
    assert ready.json() == service.result.model_dump(mode="json")

    pending_status = make_status(stage=ProcessingStage.ANALYSIS)
    service.result_error = AnalysisPendingError(pending_status)
    pending = client.get("/api/v1/analyses/analysis-001/result", headers=AUTH)
    assert pending.status_code == 202
    assert pending.json()["stage"] == "analysis"

    service.result_error = AnalysisNotFoundError()
    unknown = client.get("/api/v1/analyses/unknown/result", headers=AUTH)
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (
        404,
        "result_not_found",
    )

    service.result_error = AnalysisPersistenceUnavailableError()
    unavailable = client.get("/api/v1/analyses/analysis-001/result", headers=AUTH)
    assert (unavailable.status_code, unavailable.json()["error"]["code"]) == (
        503,
        "result_write_failed",
    )

    service.result_error = AnalysisInternalError()
    internal = client.get("/api/v1/analyses/analysis-001/result", headers=AUTH)
    assert (internal.status_code, internal.json()["error"]["code"]) == (
        500,
        "internal_error",
    )


def test_status_unknown_and_repository_failure_are_safe() -> None:
    service = StubApplicationService()
    client = _client(service)
    service.status_error = AnalysisNotFoundError()
    unknown = client.get("/api/v1/analyses/unknown", headers=AUTH)
    assert unknown.status_code == 404

    service.status_error = RuntimeError("PRIVATE C:\\secret\\result.json")
    failed = client.get("/api/v1/analyses/analysis-001", headers=AUTH)
    assert failed.status_code == 500
    assert "PRIVATE" not in failed.text
    assert "secret" not in failed.text


def test_bearer_authentication_missing_invalid_and_valid() -> None:
    service = StubApplicationService()
    client = _client(service)

    missing = client.get("/api/v1/analyses/analysis-001")
    invalid = client.get(
        "/api/v1/analyses/analysis-001",
        headers={"Authorization": "Bearer wrong"},
    )
    valid = client.get("/api/v1/analyses/analysis-001", headers=AUTH)

    for response in (missing, invalid):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"]["category"] == "authentication"
    assert missing.json()["error"]["code"] == "authentication_required"
    assert invalid.json()["error"]["code"] == "authentication_failed"
    assert valid.status_code == 200


def test_openapi_declares_exact_routes_multipart_bearer_and_response_models() -> None:
    service = StubApplicationService()
    schema = _client(service).get("/openapi.json").json()

    assert set(schema["paths"]) == {
        "/api/v1/analyses",
        "/api/v1/analyses/{analysis_id}",
        "/api/v1/analyses/{analysis_id}/result",
    }
    post = schema["paths"]["/api/v1/analyses"]["post"]
    request_body = post["requestBody"]
    multipart_schema = request_body["content"]["multipart/form-data"]["schema"]
    assert request_body["required"] is True
    assert multipart_schema["required"] == ["file"]
    assert multipart_schema["properties"] == {
        "file": {"type": "string", "format": "binary"},
        "source_context": {"type": "string"},
    }
    assert post["security"] == [{"BearerAuth": []}]
    assert set(post["responses"]) >= {"202", "400", "401", "413", "415", "422", "500", "503"}
    assert post["responses"]["202"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AnalysisSubmissionResponse"
    }
    assert post["responses"]["400"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/APIErrorResponse"
    }
    assert schema["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"


def test_disabled_api_registers_no_analysis_routes(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        api_enabled=False,
        webui_enabled=False,
    )
    app = create_app(config)

    assert not any(path.startswith("/api/") for path in app.openapi()["paths"])
