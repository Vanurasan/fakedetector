"""Production-composed Stage 6 configuration and media lifecycle verticals."""

from __future__ import annotations

import shutil
import subprocess
import wave
from io import BytesIO
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import cast

import numpy as np
import yaml
from PIL import Image

from fakedetector._runtime import _ProductionRuntime
from fakedetector.app import create_app
from fakedetector.config.loader import load_config
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalysisStatus,
    AnalyzerStatus,
    FindingSeverity,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
)
from fakedetector.intake import Stage3Accepted
from fakedetector.lifecycle.models import AnalysisTask

_EXAMPLE_CONFIG = Path("config/config.example.yaml")


def _config(tmp_path: Path) -> AppConfig:
    raw = yaml.safe_load(_EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(tmp_path / "temp")
    raw["logging"]["jsonl_path"] = str(tmp_path / "logs" / "application.jsonl")
    raw["result"]["directory"] = str(tmp_path / "results")
    raw["limits"]["max_parallel_tasks"] = {"image": 1, "audio": 1, "video": 1}
    raw["limits"]["processing_timeout_seconds"] = 60
    raw["analyzers"]["defaults"]["timeout_seconds"] = 30
    raw["preprocessing"]["video"]["keyframe_interval_seconds"] = 1
    return AppConfig.model_validate(raw)


def _production_runtime(config: AppConfig) -> _ProductionRuntime:
    app = create_app(config)
    return cast(_ProductionRuntime, app.state.runtime)


def _run(
    runtime: _ProductionRuntime,
    payload: bytes,
    *,
    original_name: str,
    declared_content_type: str,
) -> tuple[Stage3Accepted, AnalysisTask]:
    runtime.scheduler.start()
    try:
        accepted = runtime.intake.process(
            BytesIO(payload),
            original_name=original_name,
            declared_content_type=declared_content_type,
            source=SourceContext(channel=SourceChannel.API),
        )
        assert isinstance(accepted, Stage3Accepted)
    finally:
        runtime.scheduler.shutdown(drain=True)
    task = runtime.registry._tasks[accepted.analysis_id]
    return accepted, task


def _png_bytes(pixels: np.ndarray) -> bytes:
    output = BytesIO()
    with Image.fromarray(pixels) as image:
        image.save(output, format="PNG")
    return output.getvalue()


def _copy_move_image() -> bytes:
    rng = np.random.default_rng(217)
    canvas = np.full((512, 512, 3), 24, dtype=np.uint8)
    patch = rng.integers(0, 256, size=(112, 112, 3), dtype=np.uint8)
    canvas[64:176, 48:160] = patch
    canvas[300:412, 320:432] = patch
    return _png_bytes(canvas)


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


def _video_bytes(tmp_path: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None, "FFmpeg is a mandatory runtime dependency"
    path = tmp_path / "repeated-frames.mp4"
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


def test_canonical_example_activates_valid_profile_b_in_production_order() -> None:
    config = load_config(_EXAMPLE_CONFIG)
    runtime = _production_runtime(config)

    expected = {
        MediaType.IMAGE: [
            "image_metadata_consistency",
            "image_copy_move_correspondence",
        ],
        MediaType.AUDIO: ["audio_pcm_quality"],
        MediaType.VIDEO: ["video_sampled_frame_quality"],
    }
    for media_type, analyzer_ids in expected.items():
        plan = runtime.analyzer_registry.active_plan(media_type)
        assert [item.registration.analyzer_id for item in plan] == analyzer_ids
        assert all(media_type in item.registration.supported_media_types for item in plan)
        assert all(
            item.registration.settings_model.model_validate_json(item.settings_json).__class__
            is item.registration.settings_model
            for item in plan
        )


def test_production_image_vertical_publishes_authoritative_results_and_findings(
    tmp_path: Path,
    real_worker_processes: list[BaseProcess],
) -> None:
    runtime = _production_runtime(_config(tmp_path))
    accepted, task = _run(
        runtime,
        _copy_move_image(),
        original_name="copy-move.png",
        declared_content_type="image/png",
    )

    results = runtime.registry._read_stage5_analyzer_results(task)
    assert [result.analyzer_id for result in results] == [
        "image_metadata_consistency",
        "image_copy_move_correspondence",
    ]
    assert all(result.status is AnalyzerStatus.COMPLETED for result in results)
    assert all(result.score is None and result.score_name is None for result in results)
    assert task.stage6_data is not None
    findings = runtime.registry._read_stage6_findings(task)
    assert findings
    assert {finding.source_analyzer_id for finding in findings} <= {
        result.analyzer_id for result in results
    }
    assert all(finding.severity is FindingSeverity.WEAK for finding in findings)
    assert all(
        finding.source_score is None
        and finding.score_impact is None
        and not finding.critical_override_eligible
        for finding in findings
    )
    expected = tuple(finding.model_dump(mode="json") for finding in findings)
    findings[0].description = "mutated detached value"
    assert (
        tuple(
            finding.model_dump(mode="json")
            for finding in runtime.registry._read_stage6_findings(task)
        )
        == expected
    )
    snapshot = runtime.registry.snapshot(accepted.analysis_id)
    assert snapshot.status is AnalysisStatus.COMPLETED
    assert snapshot.stage is ProcessingStage.FINISHED
    assert len(real_worker_processes) == 2


def test_production_image_no_candidates_publishes_empty_stage6_state(
    tmp_path: Path,
    real_worker_processes: list[BaseProcess],
) -> None:
    runtime = _production_runtime(_config(tmp_path))
    _, task = _run(
        runtime,
        _png_bytes(np.full((256, 256, 3), 127, dtype=np.uint8)),
        original_name="plain.png",
        declared_content_type="image/png",
    )

    results = runtime.registry._read_stage5_analyzer_results(task)
    assert all(result.status is AnalyzerStatus.COMPLETED for result in results)
    assert task.stage6_data is not None
    assert runtime.registry._read_stage6_findings(task) == ()
    assert len(real_worker_processes) == 2


def test_production_not_applicable_analyzer_creates_no_finding(
    tmp_path: Path,
    real_worker_processes: list[BaseProcess],
) -> None:
    runtime = _production_runtime(_config(tmp_path))
    _, task = _run(
        runtime,
        _png_bytes(np.full((64, 64, 3), 127, dtype=np.uint8)),
        original_name="small.png",
        declared_content_type="image/png",
    )

    results = runtime.registry._read_stage5_analyzer_results(task)
    assert [result.status for result in results] == [
        AnalyzerStatus.COMPLETED,
        AnalyzerStatus.NOT_APPLICABLE,
    ]
    assert task.stage6_data is not None
    assert runtime.registry._read_stage6_findings(task) == ()
    assert len(real_worker_processes) == 2


def test_production_audio_vertical_preserves_time_localization(
    tmp_path: Path,
    real_worker_processes: list[BaseProcess],
) -> None:
    runtime = _production_runtime(_config(tmp_path))
    _, task = _run(
        runtime,
        _saturated_wav(),
        original_name="saturated.wav",
        declared_content_type="audio/wav",
    )

    results = runtime.registry._read_stage5_analyzer_results(task)
    assert [result.analyzer_id for result in results] == ["audio_pcm_quality"]
    assert results[0].status is AnalyzerStatus.COMPLETED
    findings = runtime.registry._read_stage6_findings(task)
    assert task.stage6_data is not None
    assert findings
    assert all(finding.source_analyzer_id == "audio_pcm_quality" for finding in findings)
    assert all(finding.localization.type == "time_interval" for finding in findings)
    assert len(real_worker_processes) == 1


def test_production_video_vertical_uses_sampled_frames_and_publishes_findings(
    tmp_path: Path,
    real_worker_processes: list[BaseProcess],
) -> None:
    runtime = _production_runtime(_config(tmp_path))
    _, task = _run(
        runtime,
        _video_bytes(tmp_path),
        original_name="repeated-frames.mp4",
        declared_content_type="video/mp4",
    )

    results = runtime.registry._read_stage5_analyzer_results(task)
    assert [result.analyzer_id for result in results] == ["video_sampled_frame_quality"]
    assert results[0].status is AnalyzerStatus.COMPLETED
    assert task.stage5_data is not None
    sampled_frames = [
        artifact
        for artifact in task.stage5_data.prepared_media.artifacts
        if artifact.artifact_type == "sampled_frame"
    ]
    assert len(sampled_frames) >= 3
    findings = runtime.registry._read_stage6_findings(task)
    assert task.stage6_data is not None
    assert findings
    assert all(finding.source_analyzer_id == "video_sampled_frame_quality" for finding in findings)
    assert len(real_worker_processes) == 1
