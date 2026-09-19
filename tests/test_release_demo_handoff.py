"""Release demo-media and handoff regression tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
import wave
from pathlib import Path
from types import ModuleType
from typing import Any

import cv2
import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image

from fakedetector.app import create_app
from fakedetector.config.models import AppConfig

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "generate_release_demo_media.py"
_CONFIG = _ROOT / "config" / "config.example.yaml"
_API_AUTH = {"Authorization": "Bearer stage8-test-token"}
_EXPECTED_ANALYZERS = {
    "png": ["image_metadata_consistency", "image_copy_move_correspondence"],
    "wav": ["audio_pcm_quality"],
    "mp4": ["video_sampled_frame_quality"],
}


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_demo_generator", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generated_media(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    output = tmp_path_factory.mktemp("release-demo") / "media"
    module = _load_generator()
    paths = module.generate_demo_media(output)
    return {path.suffix.removeprefix("."): path for path in paths}


def _probe_video(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate,nb_frames:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    return payload


def _wait_for_result(client: TestClient, analysis_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/v1/analyses/{analysis_id}/result",
            headers=_API_AUTH,
        )
        if response.status_code == 200:
            payload = response.json()
            assert isinstance(payload, dict)
            return payload
        assert response.status_code == 202
        time.sleep(0.01)
    raise AssertionError("generated demo media did not finish within the test deadline")


def test_generator_cli_creates_the_documented_files(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "demo-media"

    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), "--output-dir", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    expected = {
        output / "fakedetector-demo-copy-move.png",
        output / "fakedetector-demo-audio.wav",
        output / "fakedetector-demo-video.mp4",
    }
    assert set(output.iterdir()) == expected
    assert completed.stdout.splitlines() == [
        str((output / "fakedetector-demo-copy-move.png").resolve()),
        str((output / "fakedetector-demo-audio.wav").resolve()),
        str((output / "fakedetector-demo-video.mp4").resolve()),
    ]


def test_generator_refuses_nonempty_output_without_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "demo-media"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("owner data", encoding="utf-8")
    module = _load_generator()

    with pytest.raises(module.DemoGenerationError, match="absent or empty"):
        module.generate_demo_media(output)

    assert sentinel.read_text(encoding="utf-8") == "owner data"
    assert set(output.iterdir()) == {sentinel}


@pytest.mark.parametrize("missing", ["ffmpeg", "ffprobe"])
def test_generator_fails_safely_when_media_tool_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    module = _load_generator()
    real_which = module.shutil.which
    monkeypatch.setattr(
        module.shutil,
        "which",
        lambda name: None if name == missing else real_which(name),
    )

    with pytest.raises(module.DemoGenerationError, match=missing):
        module.generate_demo_media(tmp_path / "media")

    assert not (tmp_path / "media").exists()


def test_image_audio_and_video_have_bounded_semantic_properties(
    generated_media: dict[str, Path],
) -> None:
    with Image.open(generated_media["png"]) as image:
        image.load()
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == (512, 512)
        assert np.array_equal(
            np.asarray(image)[64:176, 48:160],
            np.asarray(image)[300:412, 320:432],
        )

    with wave.open(str(generated_media["wav"]), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 8_000
        assert audio.getnframes() == 8_000
        assert audio.getcomptype() == "NONE"

    probe = _probe_video(generated_media["mp4"])
    stream = probe["streams"][0]
    assert stream["codec_type"] == "video"
    assert (stream["width"], stream["height"]) == (64, 64)
    assert stream["r_frame_rate"] == "2/1"
    assert 3.0 <= float(probe["format"]["duration"]) <= 4.0

    capture = cv2.VideoCapture(str(generated_media["mp4"]))
    frames: list[np.ndarray] = []
    try:
        while True:
            read, frame = capture.read()
            if not read:
                break
            frames.append(frame)
    finally:
        capture.release()
    assert 6 <= len(frames) <= 8
    assert all(frame.shape[:2] == (64, 64) for frame in frames)
    assert all(np.array_equal(frames[0], frame) for frame in frames[1:])


def test_png_and_wav_are_byte_deterministic(
    tmp_path: Path,
    generated_media: dict[str, Path],
) -> None:
    module = _load_generator()
    second = {path.suffix.removeprefix("."): path for path in module.generate_demo_media(tmp_path)}

    assert second["png"].read_bytes() == generated_media["png"].read_bytes()
    assert second["wav"].read_bytes() == generated_media["wav"].read_bytes()
    assert (
        _probe_video(second["mp4"])["streams"][0]
        == _probe_video(generated_media["mp4"])["streams"][0]
    )


def test_handoff_examples_are_safe_and_profile_b_valid() -> None:
    env_lines = [
        line
        for line in (_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert env_lines == [
        "MEDIA_ANALYZER_API_TOKEN=",
        "MEDIA_ANALYZER_WEBUI_CREDENTIALS=",
    ]

    raw = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    config = AppConfig.model_validate(raw)
    assert config.preprocessing.video.keyframe_interval_seconds == 1
    assert config.analyzers.image.enabled == _EXPECTED_ANALYZERS["png"]
    assert config.analyzers.audio.enabled == _EXPECTED_ANALYZERS["wav"]
    assert config.analyzers.video.enabled == _EXPECTED_ANALYZERS["mp4"]


def test_generated_media_complete_current_profile_b(
    tmp_path: Path,
    generated_media: dict[str, Path],
) -> None:
    raw = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(tmp_path / "temp")
    raw["temporary_storage"]["cleanup_retries"] = 0
    raw["temporary_storage"]["quarantine_enabled"] = False
    raw["result"]["directory"] = str(tmp_path / "results")
    raw["logging"]["jsonl_path"] = str(tmp_path / "logs" / "application.jsonl")
    raw["limits"]["max_parallel_tasks"] = {"image": 1, "audio": 1, "video": 1}
    raw["limits"]["processing_timeout_seconds"] = 60
    raw["analyzers"]["defaults"]["timeout_seconds"] = 30
    app = create_app(AppConfig.model_validate(raw))
    media = (
        ("png", "image/png"),
        ("wav", "audio/wav"),
        ("mp4", "video/mp4"),
    )

    with TestClient(app) as client:
        for extension, mime in media:
            path = generated_media[extension]
            response = client.post(
                "/api/v1/analyses",
                files={"file": (path.name, path.read_bytes(), mime)},
                headers=_API_AUTH,
            )
            assert response.status_code == 202
            analysis_id = response.json()["analysis_id"]
            result = _wait_for_result(client, analysis_id)
            assert result["status"] == "completed"
            assert result["completeness"]["status"] == "complete"
            assert [item["analyzer_id"] for item in result["analyzers"]] == (
                _EXPECTED_ANALYZERS[extension]
            )
            assert result["cleanup"]["status"] == "completed"
            assert not (tmp_path / "temp" / analysis_id).exists()
