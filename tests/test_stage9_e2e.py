"""Full-path Profile B reliability and security proof for Stage 9 Macro 4."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import wave
from io import BytesIO
from multiprocessing.process import BaseProcess
from pathlib import Path
from threading import Event, Lock
from typing import Any, NoReturn

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

from fakedetector._http_upload import multipart_body_limit_bytes
from fakedetector.app import create_app
from fakedetector.config.models import AppConfig
from fakedetector.domain import MediaType
from fakedetector.intake import TemporaryInputCleanupError
from fakedetector.intake.media_tools import MediaToolSystemError
from fakedetector.repositories import ResultRepositoryError

API_AUTH = {"Authorization": "Bearer stage8-test-token"}
WEB_AUTH = ("stage8-user", "stage8-password")
_EXAMPLE_CONFIG = Path("config/config.example.yaml")


def _profile_b_config(
    root: Path,
    *,
    image_workers: int = 1,
    small_transport_limits: bool = False,
    cleanup_retries: int = 0,
) -> AppConfig:
    raw = yaml.safe_load(_EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(root / "temp")
    raw["temporary_storage"]["cleanup_retries"] = cleanup_retries
    raw["temporary_storage"]["quarantine_enabled"] = False
    raw["logging"]["jsonl_path"] = str(root / "logs" / "application.jsonl")
    raw["result"]["directory"] = str(root / "results")
    raw["limits"]["max_parallel_tasks"] = {
        "image": image_workers,
        "audio": 1,
        "video": 1,
    }
    raw["limits"]["processing_timeout_seconds"] = 60
    raw["analyzers"]["defaults"]["timeout_seconds"] = 30
    raw["preprocessing"]["video"]["keyframe_interval_seconds"] = 1
    if small_transport_limits:
        raw["limits"]["max_file_size_mb"] = {"image": 1, "audio": 1, "video": 1}
    return AppConfig.model_validate(raw)


def _saturated_wav() -> bytes:
    samples = np.full(8_000, 1_000, dtype="<i2")
    samples[::100] = 32_767
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(samples.tobytes())
    return output.getvalue()


def _repeated_video(tmp_path: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None, "FFmpeg is a mandatory runtime dependency"
    path = tmp_path / "profile-b-video.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:r=2",
            "-t",
            "3.2",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15.0,
        check=True,
    )
    return path.read_bytes()


def _wait_for_result(
    client: TestClient,
    analysis_id: str,
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/v1/analyses/{analysis_id}/result",
            headers=API_AUTH,
        )
        if response.status_code == 200:
            payload = response.json()
            assert isinstance(payload, dict)
            return payload
        assert response.status_code == 202
        time.sleep(0.01)
    raise AssertionError("analysis did not publish a result within the test deadline")


def _wait_for_status(
    client: TestClient,
    analysis_id: str,
    predicate,
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/analyses/{analysis_id}", headers=API_AUTH)
        assert response.status_code == 200
        payload = response.json()
        if predicate(payload):
            return payload
        time.sleep(0.01)
    raise AssertionError("analysis did not reach the expected status within the test deadline")


def _post_api(client: TestClient, name: str, mime: str, payload: bytes):
    return client.post(
        "/api/v1/analyses",
        files={"file": (name, payload, mime)},
        headers=API_AUTH,
    )


def _assert_completed_profile_b_result(
    *,
    result: dict[str, Any],
    analysis_id: str,
    media_type: str,
    analyzer_ids: list[str],
    fixture_bytes: bytes,
    private_root: Path,
) -> None:
    assert result["schema_version"] == "1.0"
    assert result["analysis_id"] == analysis_id
    assert result["status"] == "completed"
    assert result["stage"] == "finished"
    assert result["file"]["media_type"] == media_type
    assert result["file"]["size_bytes"] == len(fixture_bytes)
    assert result["file"]["signature_match"] is True
    assert result["file"]["safe_read"] is True
    assert [item["analyzer_id"] for item in result["analyzers"]] == analyzer_ids
    assert all(item["status"] == "completed" for item in result["analyzers"])
    assert all(item["raw_metrics"] == {} for item in result["analyzers"])
    assert result["findings"]
    assert {finding["source_analyzer_id"] for finding in result["findings"]} <= set(analyzer_ids)
    assert result["completeness"]["status"] == "complete"
    assert result["completeness"]["planned_analyzers"] == len(analyzer_ids)
    assert result["completeness"]["completed_analyzers"] == len(analyzer_ids)
    assert result["risk_assessment"]["model_id"] == "score_model_v1"
    assert result["risk_assessment"]["probability"] is None
    assert result["risk_assessment"]["probability_method"] is None
    assert result["risk_assessment"]["final_level"] is not None
    assert result["recommendation"]["text"]
    assert result["cleanup"]["status"] == "completed"
    assert result["cleanup"]["original_file_deleted"] is True
    assert result["cleanup"]["intermediate_files_deleted"] is True

    serialized = json.dumps(result, ensure_ascii=False)
    assert str(private_root) not in serialized
    assert "source_file_ref" not in serialized
    assert "workspace_path" not in serialized
    assert fixture_bytes[:32].hex() not in serialized


def _raw_file_multipart(payload: bytes) -> tuple[bytes, str]:
    boundary = "stage9-e2e-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="sample.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + payload
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


def _create_stale_workspace(root: Path, analysis_id: str) -> Path:
    workspace = root / analysis_id
    workspace.mkdir(parents=True)
    (workspace / "source").write_bytes(b"stale")
    old = time.time() - 7_200
    os.utime(workspace / "source", (old, old))
    os.utime(workspace, (old, old))
    return workspace


def test_profile_b_api_success_matrix_runs_real_stage3_through_stage8(
    tmp_path: Path,
    copy_move_png_bytes: bytes,
    real_worker_processes: list[BaseProcess],
    real_subprocesses: list[subprocess.Popen[bytes]],
) -> None:
    config = _profile_b_config(tmp_path)
    app = create_app(config)
    video = _repeated_video(tmp_path)
    cases = [
        (
            "image",
            "copy-move.png",
            "image/png",
            copy_move_png_bytes,
            ["image_metadata_consistency", "image_copy_move_correspondence"],
        ),
        ("audio", "saturated.wav", "audio/wav", _saturated_wav(), ["audio_pcm_quality"]),
        (
            "video",
            "repeated.mp4",
            "video/mp4",
            video,
            ["video_sampled_frame_quality"],
        ),
    ]

    with TestClient(app) as client:
        for media_type, name, mime, payload, analyzers in cases:
            created = _post_api(client, name, mime, payload)
            assert created.status_code == 202
            submission = created.json()
            analysis_id = submission["analysis_id"]
            assert submission["status_url"] == f"/api/v1/analyses/{analysis_id}"
            assert submission["result_url"] == f"/api/v1/analyses/{analysis_id}/result"
            assert app.state.runtime.registry.contains(analysis_id)

            result = _wait_for_result(client, analysis_id)
            status = client.get(
                f"/api/v1/analyses/{analysis_id}",
                headers=API_AUTH,
            )
            assert status.status_code == 200
            assert status.json()["status"] == "completed"
            assert status.json()["stage"] == "finished"
            assert status.json()["result_available"] is True

            _assert_completed_profile_b_result(
                result=result,
                analysis_id=analysis_id,
                media_type=media_type,
                analyzer_ids=analyzers,
                fixture_bytes=payload,
                private_root=tmp_path,
            )
            stored = app.state.runtime.result_repository.get(analysis_id)
            assert stored is not None
            assert stored.model_dump(mode="json") == result
            assert not (Path(config.temporary_storage.root_path) / analysis_id).exists()

    assert app.state.runtime.scheduler.is_stopped
    assert app.state.runtime.scheduler._threads == []
    assert real_worker_processes
    assert all(process._closed for process in real_worker_processes)
    assert real_subprocesses
    assert all(process.poll() is not None for process in real_subprocesses)


def test_webui_success_uses_same_profile_b_service_and_persisted_result(
    tmp_path: Path,
    copy_move_png_bytes: bytes,
) -> None:
    config = _profile_b_config(tmp_path)
    app = create_app(config)
    assert app.state.application_service is app.state.runtime.application_service

    with TestClient(app) as client:
        upload_page = client.get("/", auth=WEB_AUTH)
        assert upload_page.status_code == 200
        assert "FakeDetector" in upload_page.text

        created = client.post(
            "/analyses",
            files={"file": ("web-copy-move.png", copy_move_png_bytes, "image/png")},
            headers={"Origin": "http://testserver"},
            auth=WEB_AUTH,
            follow_redirects=False,
        )
        assert created.status_code == 303
        status_url = created.headers["location"]
        analysis_id = status_url.rsplit("/", maxsplit=1)[-1]
        backend_result = _wait_for_result(client, analysis_id)

        web_status = client.get(status_url, auth=WEB_AUTH, follow_redirects=False)
        assert web_status.status_code == 303
        result_page = client.get(web_status.headers["location"], auth=WEB_AUTH)
        assert result_page.status_code == 200
        assert "Результат анализа" in result_page.text
        assert analysis_id in result_page.text
        assert backend_result["file"]["original_name"] in result_page.text
        stored = app.state.runtime.result_repository.get(analysis_id)
        assert stored is not None
        assert stored.model_dump(mode="json") == backend_result
        assert backend_result["source"]["channel"] == "webui"


def test_restart_reads_profile_b_result_without_old_registry_and_sweeps_stale_workspaces(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    config = _profile_b_config(tmp_path)
    temp_root = Path(config.temporary_storage.root_path)
    startup_stale = _create_stale_workspace(temp_root, "a" * 32)
    first_app = create_app(config)

    with TestClient(first_app) as client:
        assert not startup_stale.exists()
        created = _post_api(client, "restart.png", "image/png", media_files["png"].read_bytes())
        assert created.status_code == 202
        analysis_id = created.json()["analysis_id"]
        expected = _wait_for_result(client, analysis_id)
        shutdown_stale = _create_stale_workspace(temp_root, "b" * 32)
        assert shutdown_stale.exists()

    assert first_app.state.runtime.scheduler.is_stopped
    assert not shutdown_stale.exists()
    assert first_app.state.runtime.result_repository.exists(analysis_id)

    restarted_app = create_app(config)
    assert not restarted_app.state.runtime.registry.contains(analysis_id)
    with TestClient(restarted_app) as restarted_client:
        persisted = restarted_client.get(
            f"/api/v1/analyses/{analysis_id}/result",
            headers=API_AUTH,
        )
        status = restarted_client.get(
            f"/api/v1/analyses/{analysis_id}",
            headers=API_AUTH,
        )

    assert persisted.status_code == 200
    assert persisted.json() == expected
    assert status.status_code == 200
    assert status.json()["result_available"] is True


def test_stage3_mime_signature_mismatch_is_persisted_rejected_with_cleanup(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    config = _profile_b_config(tmp_path)
    app = create_app(config)

    with TestClient(app) as client:
        rejected = _post_api(
            client,
            "mismatch.wav",
            "audio/wav",
            media_files["png"].read_bytes(),
        )
        assert rejected.status_code == 415
        payload = rejected.json()
        assert payload["error"]["code"] == "file_signature_mismatch"
        analysis_id = payload["analysis_id"]
        result = client.get(payload["result_url"], headers=API_AUTH)

    assert result.status_code == 200
    terminal = result.json()
    assert terminal["analysis_id"] == analysis_id
    assert terminal["status"] == "rejected"
    assert terminal["stage"] == "finished"
    assert terminal["analyzers"] == []
    assert terminal["findings"] == []
    assert terminal["completeness"]["status"] == "not_assessed"
    assert terminal["risk_assessment"] is None
    assert terminal["cleanup"]["status"] == "completed"
    assert not (Path(config.temporary_storage.root_path) / analysis_id).exists()


def test_media_tool_infrastructure_failure_is_safe_persisted_failed(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _profile_b_config(tmp_path)
    app = create_app(config)
    inspector = app.state.runtime.intake._validator._media_inspector

    def fail_probe(_path: Path) -> NoReturn:
        raise MediaToolSystemError("PRIVATE C:\\sensitive\\ffprobe failure")

    monkeypatch.setattr(inspector, "probe", fail_probe)
    with TestClient(app) as client:
        failed = _post_api(client, "failure.wav", "audio/wav", media_files["wav"].read_bytes())
        assert failed.status_code == 500
        payload = failed.json()
        assert payload["error"]["code"] == "internal_error"
        analysis_id = payload["analysis_id"]
        result = client.get(payload["result_url"], headers=API_AUTH)

    assert result.status_code == 200
    terminal = result.json()
    assert terminal["analysis_id"] == analysis_id
    assert terminal["status"] == "failed"
    assert terminal["errors"][0]["code"] == "internal_error"
    assert terminal["cleanup"]["status"] == "completed"
    serialized = json.dumps({"response": payload, "result": terminal})
    assert "PRIVATE" not in serialized
    assert "sensitive" not in serialized
    assert str(tmp_path) not in serialized


def test_persistence_failure_stays_persistence_without_retry_or_false_finished(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _profile_b_config(tmp_path)
    app = create_app(config)
    save_calls = 0

    def fail_save(_result: object) -> NoReturn:
        nonlocal save_calls
        save_calls += 1
        raise ResultRepositoryError("PRIVATE result path")

    monkeypatch.setattr(app.state.runtime.result_repository, "save", fail_save)
    with TestClient(app) as client:
        created = _post_api(client, "persistence.png", "image/png", media_files["png"].read_bytes())
        assert created.status_code == 202
        analysis_id = created.json()["analysis_id"]
        status = _wait_for_status(
            client,
            analysis_id,
            lambda item: (
                item["stage"] == "persistence"
                and any(error["code"] == "result_write_failed" for error in item["errors"])
            ),
        )
        result = client.get(f"/api/v1/analyses/{analysis_id}/result", headers=API_AUTH)

    assert status["status"] == "completed"
    assert status["stage"] == "persistence"
    assert status["finished_at"] is None
    assert status["result_available"] is False
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "result_write_failed"
    assert save_calls == 1
    assert not app.state.runtime.result_repository.exists(analysis_id)
    assert not (Path(config.temporary_storage.root_path) / analysis_id).exists()


def test_cleanup_failure_preserves_primary_result_and_reports_retained_residue(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _profile_b_config(tmp_path, cleanup_retries=1)
    app = create_app(config)
    owner = app.state.runtime.intake._owner
    cleanup_calls = 0

    def fail_cleanup(_owned_source: object) -> NoReturn:
        nonlocal cleanup_calls
        cleanup_calls += 1
        raise TemporaryInputCleanupError()

    monkeypatch.setattr(owner, "cleanup", fail_cleanup)
    with TestClient(app) as client:
        created = _post_api(client, "cleanup.png", "image/png", media_files["png"].read_bytes())
        analysis_id = created.json()["analysis_id"]
        result = _wait_for_result(client, analysis_id)
        workspace = Path(config.temporary_storage.root_path) / analysis_id
        assert workspace.exists()

    assert result["status"] == "completed"
    assert result["stage"] == "finished"
    assert result["cleanup"]["status"] == "failed"
    assert result["cleanup"]["original_file_deleted"] is False
    assert result["cleanup"]["errors"][0]["code"] == "cleanup_failed"
    assert cleanup_calls == 1 + config.temporary_storage.cleanup_retries


def test_assembled_app_guards_auth_and_actual_oversized_body_before_registration(
    tmp_path: Path,
) -> None:
    config = _profile_b_config(tmp_path, small_transport_limits=True)
    app = create_app(config)
    body_limit = multipart_body_limit_bytes(config)
    oversized, content_type = _raw_file_multipart(b"x" * body_limit)
    assert len(oversized) > body_limit

    with TestClient(app) as client:
        unauthenticated = client.post(
            "/api/v1/analyses",
            content=oversized,
            headers={"Content-Type": content_type},
        )
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["error"]["code"] == "authentication_required"
        assert app.state.runtime.registry._tasks == {}
        assert not Path(config.temporary_storage.root_path).exists()
        assert not Path(config.result.directory).exists()

        def chunks():
            midpoint = len(oversized) // 2
            yield oversized[:midpoint]
            yield oversized[midpoint:]

        authenticated = client.post(
            "/api/v1/analyses",
            content=chunks(),
            headers={**API_AUTH, "Content-Type": content_type},
        )
        assert authenticated.status_code == 413
        assert authenticated.json()["error"]["code"] == "file_too_large"
        assert "analysis_id" not in authenticated.json()
        assert app.state.runtime.registry._tasks == {}
        assert not Path(config.temporary_storage.root_path).exists()
        assert not Path(config.result.directory).exists()


def test_two_profile_b_analyses_remain_independent_while_one_persistence_is_blocked(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _profile_b_config(tmp_path, image_workers=2)
    app = create_app(config)
    repository = app.state.runtime.result_repository
    real_save = repository.save
    first_save_entered = Event()
    release_first_save = Event()
    save_lock = Lock()
    save_order = 0

    def controlled_save(result) -> None:
        nonlocal save_order
        with save_lock:
            save_order += 1
            order = save_order
        if order == 1:
            first_save_entered.set()
            assert release_first_save.wait(20.0)
        real_save(result)

    monkeypatch.setattr(repository, "save", controlled_save)
    assert app.state.runtime.scheduler.capacity(MediaType.IMAGE) == 2

    first_id = ""
    try:
        with TestClient(app) as client:
            first = _post_api(client, "first.png", "image/png", media_files["png"].read_bytes())
            first_id = first.json()["analysis_id"]
            assert first_save_entered.wait(20.0)

            second = _post_api(client, "second.png", "image/png", media_files["png"].read_bytes())
            second_id = second.json()["analysis_id"]
            assert first_id != second_id
            second_result = _wait_for_result(client, second_id)

            first_status = client.get(
                f"/api/v1/analyses/{first_id}",
                headers=API_AUTH,
            )
            first_pending = client.get(
                f"/api/v1/analyses/{first_id}/result",
                headers=API_AUTH,
            )
            assert first_status.json()["stage"] == "persistence"
            assert first_status.json()["result_available"] is False
            assert first_pending.status_code == 202
            assert second_result["analysis_id"] == second_id
            assert second_result["file"]["original_name"] == "second.png"
            assert repository.exists(second_id)
            assert not repository.exists(first_id)

            release_first_save.set()
            first_result = _wait_for_result(client, first_id)
            assert first_result["analysis_id"] == first_id
            assert first_result["file"]["original_name"] == "first.png"
            assert repository.exists(first_id)
            assert not (Path(config.temporary_storage.root_path) / first_id).exists()
            assert not (Path(config.temporary_storage.root_path) / second_id).exists()
    finally:
        release_first_save.set()

    assert first_id
    assert save_order == 2
