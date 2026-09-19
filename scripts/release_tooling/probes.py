"""Real API/WebUI analysis, result semantics and persisted restart retrieval."""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from . import common, transport

_EXPECTED_ANALYZERS = {
    ".png": (
        ("image_metadata_consistency", "1.0.0"),
        ("image_copy_move_correspondence", "1.0.0"),
    ),
    ".wav": (("audio_pcm_quality", "1.0.0"),),
    ".mp4": (("video_sampled_frame_quality", "1.0.0"),),
}


_MEDIA_MIME = {
    ".png": "image/png",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
}


def _multipart(path: Path, mime: str) -> tuple[bytes, str]:
    boundary = f"fakedetector-release-{secrets.token_hex(12)}"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("ascii")
    body = header + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    return body, f"multipart/form-data; boundary={boundary}"


def _poll_api_result(
    *,
    base_url: str,
    analysis_id: str,
    bearer_header: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + common._PHASE_TIMEOUTS["analysis"]
    url = f"{base_url}/api/v1/analyses/{analysis_id}/result"
    while time.monotonic() < deadline:
        try:
            status, _headers, body = transport._http_exchange(
                "GET",
                url,
                headers={"Authorization": bearer_header},
                timeout=2.0,
            )
        except OSError:
            raise common.ReleaseVerificationError(
                "analysis",
                "Loopback result polling failed.",
                analysis_id=analysis_id,
            ) from None
        if status == 200:
            return transport._json_object(body, phase="analysis")
        if status != 202:
            raise common.ReleaseVerificationError(
                "analysis",
                f"Result polling returned HTTP {status}.",
                analysis_id=analysis_id,
            )
        time.sleep(0.1)
    raise common.ReleaseVerificationError(
        "analysis",
        "Analysis polling exceeded its deadline.",
        analysis_id=analysis_id,
    )


def _validate_result(
    *,
    result: dict[str, Any],
    analysis_id: str,
    suffix: str,
    expected_application_version: str,
) -> dict[str, Any]:
    expected_analyzers = _EXPECTED_ANALYZERS[suffix]
    actual_analyzers = tuple(
        (item.get("analyzer_id"), item.get("analyzer_version"))
        for item in result.get("analyzers", [])
    )
    checks = {
        "schema_version": result.get("schema_version") == "1.0",
        "analysis_id": result.get("analysis_id") == analysis_id,
        "status": result.get("status") == "completed",
        "stage": result.get("stage") == "finished",
        "completeness": result.get("completeness", {}).get("status") == "complete",
        "analyzers": actual_analyzers == expected_analyzers,
        "analyzer_statuses": all(
            item.get("status") == "completed" for item in result.get("analyzers", [])
        ),
        "risk_present": isinstance(result.get("risk_assessment"), dict)
        and result["risk_assessment"].get("final_level") is not None,
        "recommendation_present": isinstance(result.get("recommendation"), dict)
        and bool(result["recommendation"].get("text")),
        "cleanup": result.get("cleanup", {}).get("status") == "completed",
        "application_version": result.get("processing", {}).get("application_version")
        == expected_application_version,
    }
    if not all(checks.values()):
        raise common.ReleaseVerificationError(
            "analysis",
            "Terminal result failed structural validation: " + json.dumps(checks, sort_keys=True),
            analysis_id=analysis_id,
        )
    return {
        "status": "passed",
        "analysis_id": analysis_id,
        "terminal_status": result["status"],
        "completeness_status": result["completeness"]["status"],
        "analyzers": [
            {"analyzer_id": analyzer_id, "analyzer_version": analyzer_version}
            for analyzer_id, analyzer_version in actual_analyzers
        ],
        "risk_present": True,
        "recommendation_present": True,
        "cleanup_status": result["cleanup"]["status"],
        "schema_version": result["schema_version"],
    }


def _verify_persistence_and_cleanup(
    *,
    result: dict[str, Any],
    analysis_id: str,
    config_raw: dict[str, Any],
) -> dict[str, Any]:
    result_path = Path(config_raw["result"]["directory"]) / f"{analysis_id}.json"
    if not result_path.is_file():
        raise common.ReleaseVerificationError(
            "persistence", "Canonical result file is missing.", analysis_id=analysis_id
        )
    try:
        persisted = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise common.ReleaseVerificationError(
            "persistence", "Canonical result file is unreadable.", analysis_id=analysis_id
        ) from None
    if persisted != result:
        raise common.ReleaseVerificationError(
            "persistence",
            "HTTP result differs from canonical persisted JSON.",
            analysis_id=analysis_id,
        )
    temp_root = Path(config_raw["temporary_storage"]["root_path"])
    workspace_absent = not (temp_root / analysis_id).exists()
    quarantine_absent = not (temp_root.parent / "quarantine" / analysis_id).exists()
    if not workspace_absent or not quarantine_absent:
        raise common.ReleaseVerificationError(
            "cleanup", "Analysis workspace or quarantine residue remains.", analysis_id=analysis_id
        )
    return {
        "analysis_id": analysis_id,
        "canonical_result": result_path.name,
        "semantic_match": True,
        "workspace_absent": True,
        "quarantine_residue_absent": True,
    }


def _submit_api_analysis(
    *,
    base_url: str,
    path: Path,
    bearer_header: str,
    config_raw: dict[str, Any],
    expected_application_version: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    body, content_type = _multipart(path, _MEDIA_MIME[path.suffix])
    _headers, response_body = transport._require_http(
        "POST",
        f"{base_url}/api/v1/analyses",
        expected_status=202,
        phase="api_upload",
        headers={
            "Authorization": bearer_header,
            "Content-Type": content_type,
        },
        data=body,
        timeout=30.0,
    )
    submission = transport._json_object(response_body, phase="api_upload")
    analysis_id = submission.get("analysis_id")
    if not isinstance(analysis_id, str) or not analysis_id:
        raise common.ReleaseVerificationError("api_upload", "Submission lacks analysis_id.")
    result = _poll_api_result(
        base_url=base_url,
        analysis_id=analysis_id,
        bearer_header=bearer_header,
    )
    evidence = _validate_result(
        result=result,
        analysis_id=analysis_id,
        suffix=path.suffix,
        expected_application_version=expected_application_version,
    )
    _status_headers, status_body = transport._require_http(
        "GET",
        f"{base_url}/api/v1/analyses/{analysis_id}",
        expected_status=200,
        phase="api_status",
        headers={"Authorization": bearer_header},
    )
    status_payload = transport._json_object(status_body, phase="api_status")
    if not status_payload.get("result_available"):
        raise common.ReleaseVerificationError(
            "api_status", "Completed result is not marked available.", analysis_id=analysis_id
        )
    persistence = _verify_persistence_and_cleanup(
        result=result,
        analysis_id=analysis_id,
        config_raw=config_raw,
    )
    return result, evidence, persistence


def _exercise_webui(
    *,
    base_url: str,
    image_path: Path,
    basic_header: str,
    bearer_header: str,
    config_raw: dict[str, Any],
    expected_application_version: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    unauth_headers, _unauth_body = transport._require_http(
        "GET", base_url + "/", expected_status=401, phase="webui_auth"
    )
    if "basic" not in unauth_headers.get("www-authenticate", "").casefold():
        raise common.ReleaseVerificationError("webui_auth", "WebUI challenge lacks Basic scheme.")
    _root_headers, root_body = transport._require_http(
        "GET",
        base_url + "/",
        expected_status=200,
        phase="webui",
        headers={"Authorization": basic_header},
    )
    if b"FakeDetector" not in root_body:
        raise common.ReleaseVerificationError("webui", "Authenticated upload page is invalid.")
    css_headers, css_body = transport._require_http(
        "GET",
        base_url + "/static/styles.css",
        expected_status=200,
        phase="webui_static",
        headers={"Authorization": basic_header},
    )
    if not css_body or "text/css" not in css_headers.get("content-type", ""):
        raise common.ReleaseVerificationError("webui_static", "Required CSS asset is invalid.")

    multipart_body, content_type = _multipart(image_path, _MEDIA_MIME[image_path.suffix])
    upload_headers, _upload_body = transport._require_http(
        "POST",
        base_url + "/analyses",
        expected_status=303,
        phase="webui_upload",
        headers={
            "Authorization": basic_header,
            "Origin": base_url,
            "Content-Type": content_type,
        },
        data=multipart_body,
        timeout=30.0,
    )
    status_location = upload_headers.get("location")
    if not status_location:
        raise common.ReleaseVerificationError("webui_upload", "WebUI upload lacks status redirect.")
    analysis_id = status_location.rstrip("/").rsplit("/", maxsplit=1)[-1]
    status_url = urljoin(base_url, status_location)
    deadline = time.monotonic() + common._PHASE_TIMEOUTS["analysis"]
    result_location: str | None = None
    while time.monotonic() < deadline:
        try:
            status, response_headers, _body = transport._http_exchange(
                "GET",
                status_url,
                headers={"Authorization": basic_header},
                timeout=2.0,
            )
        except OSError:
            raise common.ReleaseVerificationError(
                "webui_upload", "WebUI status polling failed.", analysis_id=analysis_id
            ) from None
        if status == 303:
            result_location = response_headers.get("location")
            break
        if status != 200:
            raise common.ReleaseVerificationError(
                "webui_upload",
                f"WebUI status returned HTTP {status}.",
                analysis_id=analysis_id,
            )
        time.sleep(0.1)
    if result_location is None:
        raise common.ReleaseVerificationError(
            "webui_upload", "WebUI analysis exceeded its deadline.", analysis_id=analysis_id
        )
    _result_headers, result_page = transport._require_http(
        "GET",
        urljoin(base_url, result_location),
        expected_status=200,
        phase="webui_result",
        headers={"Authorization": basic_header},
    )
    if analysis_id.encode() not in result_page or "Результат анализа".encode() not in result_page:
        raise common.ReleaseVerificationError(
            "webui_result", "WebUI result page is invalid.", analysis_id=analysis_id
        )
    result = _poll_api_result(
        base_url=base_url,
        analysis_id=analysis_id,
        bearer_header=bearer_header,
    )
    evidence = _validate_result(
        result=result,
        analysis_id=analysis_id,
        suffix=".png",
        expected_application_version=expected_application_version,
    )
    persistence = _verify_persistence_and_cleanup(
        result=result,
        analysis_id=analysis_id,
        config_raw=config_raw,
    )
    webui = {
        "status": "passed",
        "unauthenticated_status": 401,
        "basic_authenticated_root": 200,
        "css_status": 200,
        "upload_status": 303,
        "same_origin_header": "Origin",
        "analysis_id": analysis_id,
        "status_redirect": 303,
        "result_status": 200,
    }
    return result, evidence, persistence, webui


def _exercise_api_auth(base_url: str, bearer_header: str) -> dict[str, Any]:
    for label, headers in (
        ("missing", {}),
        ("invalid", {"Authorization": "Bearer invalid-release-gate-token"}),
    ):
        _response_headers, body = transport._require_http(
            "GET",
            f"{base_url}/api/v1/analyses/unknown",
            expected_status=401,
            phase="api_auth",
            headers=headers,
        )
        payload = transport._json_object(body, phase="api_auth")
        if payload.get("error", {}).get("category") != "authentication":
            raise common.ReleaseVerificationError(
                "api_auth", f"{label} Bearer response is invalid."
            )
    _headers, body = transport._require_http(
        "GET",
        f"{base_url}/api/v1/analyses/unknown",
        expected_status=404,
        phase="api_auth",
        headers={"Authorization": bearer_header},
    )
    transport._json_object(body, phase="api_auth")
    return {
        "status": "passed",
        "missing_bearer_status": 401,
        "invalid_bearer_status": 401,
        "valid_bearer_reached_route_status": 404,
    }


def _retrieve_after_restart(
    *,
    base_url: str,
    results: dict[str, dict[str, Any]],
    bearer_header: str,
) -> dict[str, Any]:
    retrieved: dict[str, Any] = {}
    for analysis_id, expected in results.items():
        _headers, body = transport._require_http(
            "GET",
            f"{base_url}/api/v1/analyses/{analysis_id}/result",
            expected_status=200,
            phase="restart_retrieval",
            headers={"Authorization": bearer_header},
        )
        actual = transport._json_object(body, phase="restart_retrieval")
        if actual != expected:
            raise common.ReleaseVerificationError(
                "restart_retrieval",
                "Restart result differs from the first process result.",
                analysis_id=analysis_id,
            )
        _status_headers, status_body = transport._require_http(
            "GET",
            f"{base_url}/api/v1/analyses/{analysis_id}",
            expected_status=200,
            phase="restart_retrieval",
            headers={"Authorization": bearer_header},
        )
        status_payload = transport._json_object(status_body, phase="restart_retrieval")
        if not status_payload.get("result_available"):
            raise common.ReleaseVerificationError(
                "restart_retrieval",
                "Restart status does not expose the persisted result.",
                analysis_id=analysis_id,
            )
        retrieved[analysis_id] = {
            "result_status": 200,
            "status_status": 200,
            "result_available": True,
            "semantic_match": True,
        }
    return retrieved
