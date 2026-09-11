"""Cross-channel production composition tests for Stage 8 Macro 2."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient
from stage8_helpers import make_config

from fakedetector.app import create_app

API_AUTH = {"Authorization": "Bearer stage8-test-token"}
WEB_AUTH = ("stage8-user", "stage8-password")


def _wait_for_api_result(
    client: TestClient,
    analysis_id: str,
    *,
    timeout_seconds: float = 8.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/v1/analyses/{analysis_id}/result",
            headers=API_AUTH,
        )
        if response.status_code == 200:
            return response.json()
        assert response.status_code == 202
        time.sleep(0.02)
    raise AssertionError("analysis did not publish a result within the test deadline")


def test_api_and_webui_share_one_production_service_and_results(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    config = make_config(tmp_path)
    app = create_app(config)

    assert app.state.application_service is app.state.runtime.application_service

    with TestClient(app) as client:
        api_created = client.post(
            "/api/v1/analyses",
            files={"file": ("api.png", media_files["png"].read_bytes(), "image/png")},
            headers=API_AUTH,
        )
        assert api_created.status_code == 202
        api_id = api_created.json()["analysis_id"]
        api_result = _wait_for_api_result(client, api_id)

        web_status = client.get(
            f"/analyses/{api_id}",
            auth=WEB_AUTH,
            follow_redirects=False,
        )
        assert web_status.status_code == 303
        web_result = client.get(web_status.headers["location"], auth=WEB_AUTH)
        assert web_result.status_code == 200
        assert api_id in web_result.text

        web_created = client.post(
            "/analyses",
            files={"file": ("web.png", media_files["png"].read_bytes(), "image/png")},
            headers={"Origin": "http://testserver"},
            auth=WEB_AUTH,
            follow_redirects=False,
        )
        assert web_created.status_code == 303
        web_id = web_created.headers["location"].rsplit("/", maxsplit=1)[-1]
        web_result_json = _wait_for_api_result(client, web_id)

        stored_api = app.state.runtime.result_repository.get(api_id)
        stored_web = app.state.runtime.result_repository.get(web_id)
        assert stored_api is not None
        assert stored_web is not None
        assert api_result == stored_api.model_dump(mode="json")
        assert web_result_json == stored_web.model_dump(mode="json")
        api_source = api_result["source"]
        web_source = web_result_json["source"]
        assert isinstance(api_source, dict)
        assert isinstance(web_source, dict)
        assert api_source["channel"] == "api"
        assert web_source["channel"] == "webui"


def test_restart_exposes_persisted_result_and_lost_inflight_id_is_unknown(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    config = make_config(tmp_path)
    first_app = create_app(config)
    with TestClient(first_app) as client:
        created = client.post(
            "/api/v1/analyses",
            files={"file": ("sample.png", media_files["png"].read_bytes(), "image/png")},
            headers=API_AUTH,
        )
        analysis_id = created.json()["analysis_id"]
        expected = _wait_for_api_result(client, analysis_id)

    restarted_app = create_app(config)
    assert not restarted_app.state.runtime.registry.contains(analysis_id)
    with TestClient(restarted_app) as restarted_client:
        persisted = restarted_client.get(
            f"/api/v1/analyses/{analysis_id}/result",
            headers=API_AUTH,
        )
        web_status = restarted_client.get(
            f"/analyses/{analysis_id}",
            auth=WEB_AUTH,
            follow_redirects=False,
        )
        assert web_status.status_code == 303
        assert web_status.headers["location"] == f"/analyses/{analysis_id}/result"
        web_result = restarted_client.get(
            web_status.headers["location"],
            auth=WEB_AUTH,
        )
        missing = restarted_client.get(
            "/api/v1/analyses/lost-inflight-id",
            headers=API_AUTH,
        )

    assert persisted.status_code == 200
    assert persisted.json() == expected
    assert web_result.status_code == 200
    assert analysis_id in web_result.text
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "result_not_found"
