"""Closed catalog separation and real diploma-profile intake-to-persistence paths."""

import hashlib
import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image
from support.diploma_inputs import audio_request
from test_image_experimental import _periodic_tiles
from test_stage9_e2e import API_AUTH, WEB_AUTH, _post_api, _repeated_video, _wait_for_result

from fakedetector.analyzers._catalog import (
    _AnalyzerMaturity,
    _built_in_analyzer_registrations,
    _resolve_built_in_analyzer_definition,
    _resolve_runtime_analyzer_definition,
    _resolve_worker_definition,
    _runtime_analyzer_registrations,
)
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.app import create_app
from fakedetector.config.models import AppConfig
from fakedetector.domain import MediaType
from fakedetector.lifecycle._finding_formation import FindingFormationError, FindingFormationService
from fakedetector.preprocessing._requirements import ForensicCapability


def _config(root):
    raw = yaml.safe_load(Path("config/config.diploma.yaml").read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(root / "temp")
    raw["result"]["directory"] = str(root / "results")
    raw["logging"]["jsonl_path"] = str(root / "logs/application.jsonl")
    return AppConfig.model_validate(raw)


def test_catalog_preserves_five_core_and_resolves_all_opt_in_ids(tmp_path):
    core = _built_in_analyzer_registrations()
    assert {r.analyzer_id for r in core} == {
        "image_metadata_consistency",
        "image_copy_move_correspondence",
        "image_jpeg_double_quantization",
        "audio_pcm_quality",
        "video_sampled_frame_quality",
    }
    runtime = _runtime_analyzer_registrations()
    assert runtime[:5] == core
    assert len(runtime) == len({r.analyzer_id for r in runtime}) == 14
    assert len({r.worker_key for r in runtime}) == 14
    config = _config(tmp_path)
    registry = AnalyzerRegistry(config, runtime)
    assert sum(len(registry.active_plan(media)) for media in MediaType) == 14
    for r in runtime:
        definition = _resolve_runtime_analyzer_definition(r.analyzer_id)
        assert _resolve_worker_definition(r.worker_key) is definition
        assert definition.registration() == r
        assert definition.analyzer_name == definition.factory.analyzer_name
        if r not in core:
            assert _resolve_built_in_analyzer_definition(r.analyzer_id) is None
            assert definition.maturity in {
                _AnalyzerMaturity.EXPERIMENTAL,
                _AnalyzerMaturity.EXPERIMENTAL_WEAK,
            }
            assert r.max_candidate_findings == 0 and not r.candidate_finding_types
        else:
            assert definition.maturity is _AnalyzerMaturity.CORE
            assert r.analyzer_version == "1.0.0"
    assert registry.preprocessing_requirements(MediaType.VIDEO).forensic == frozenset(
        {
            ForensicCapability.DENSE_VIDEO,
            ForensicCapability.STREAM_TIMING,
        }
    )
    assert registry.preprocessing_requirements(MediaType.AUDIO).forensic == frozenset(
        {
            ForensicCapability.AUDIO_PRECISION,
            ForensicCapability.AUDIO_SAMPLES,
            ForensicCapability.AUDIO_SPECTRAL,
        }
    )


def test_experimental_finding_injection_rejected(tmp_path):
    definition = _resolve_runtime_analyzer_definition("audio_temporal_discontinuity")
    result = definition.factory().analyze(audio_request(tmp_path, np.zeros(2048)))
    forged = result.model_copy(
        update={"candidate_findings": [{"type": "audio_full_scale_saturation"}]}
    )
    with pytest.raises(FindingFormationError):
        FindingFormationService().form_findings([forged])


def _audio():
    rng = np.random.default_rng(61)
    samples = rng.integers(-6000, 6000, 65536, dtype="<i2")
    samples[32768:49152] = samples[:16384]
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(samples.tobytes())
    return output.getvalue()


def test_diploma_real_preprocessing_workers_api_webui_persistence_cleanup(
    tmp_path,
    real_worker_processes,
    real_subprocesses,
):
    config = _config(tmp_path)
    image = io.BytesIO()
    Image.fromarray(_periodic_tiles(True)).save(image, format="PNG")
    cases = [
        (MediaType.IMAGE, "image.png", "image/png", image.getvalue()),
        (MediaType.AUDIO, "audio.wav", "audio/wav", _audio()),
        (MediaType.VIDEO, "video.mp4", "video/mp4", _repeated_video(tmp_path)),
    ]
    registry = AnalyzerRegistry(config, _runtime_analyzer_registrations())
    with TestClient(create_app(config)) as client:
        for media, name, mime, payload in cases:
            response = _post_api(client, name, mime, payload)
            assert response.status_code == 202
            analysis_id = response.json()["analysis_id"]
            result = _wait_for_result(client, analysis_id, timeout_seconds=45)
            assert result["status"] == "completed", result
            assert result["file"]["sha256"] == hashlib.sha256(payload).hexdigest()
            assert [a["analyzer_id"] for a in result["analyzers"]] == list(
                registry.active_analyzer_ids(media)
            )
            for analyzer in result["analyzers"]:
                expected = (
                    "not_applicable"
                    if analyzer["analyzer_id"] == "image_jpeg_double_quantization"
                    else "completed"
                )
                assert analyzer["status"] == expected, analyzer
                if _resolve_built_in_analyzer_definition(analyzer["analyzer_id"]) is None:
                    assert analyzer["raw_metrics"]["profile"]
                    assert analyzer["score"] is None and not analyzer["candidate_findings"]
                    assert "Experimental" in analyzer["summary"]
            assert result["risk_assessment"]["probability"] is None
            assert all(
                _resolve_built_in_analyzer_definition(f["source_analyzer_id"])
                for f in result["findings"]
            )
            assert result["cleanup"]["status"] == "completed"
            assert not (Path(config.temporary_storage.root_path) / analysis_id).exists()
            page = client.get(f"/analyses/{analysis_id}/result", auth=WEB_AUTH)
            assert page.status_code == 200
            for analyzer in result["analyzers"]:
                assert analyzer["analyzer_id"] in page.text
            assert "Измерения" in page.text
            stored = client.get(f"/api/v1/analyses/{analysis_id}/result", headers=API_AUTH).json()
            assert stored == result
            encoded = json.dumps(result, allow_nan=False)
            assert str(tmp_path) not in encoded
    assert real_worker_processes and real_subprocesses
