"""Closed catalog separation and real diploma-profile intake-to-persistence paths."""

import hashlib
import html
import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image
from support.diploma_inputs import audio_request, image_request, video_request
from test_image_experimental import _checker, _periodic_tiles
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
from fakedetector.lifecycle._assessment import (
    _ENSEMBLE_FAMILIES,
    AnalysisAssessmentService,
    _ensemble_response,
)
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
    # Frozen fixture family-response sums divided by independent canonical-capacity oracles.
    expected_scores = {
        MediaType.IMAGE: 100 * 0.190718516274402 / 3.4375,
        MediaType.AUDIO: 100 * 1.224143925305932 / 2.8125,
        MediaType.VIDEO: 100 / 2.05,
    }
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
            risk = result["risk_assessment"]
            assert risk["model_id"] == "diploma_ensemble_v1"
            assert risk["model_version"] == "0.1.0"
            assert risk["probability"] is risk["probability_method"] is None
            assert 0 < risk["score"] <= 100
            assert risk["score"] == pytest.approx(expected_scores[media])
            if media is MediaType.AUDIO:
                assert risk["score"] > 100 / 2.8125  # More than any single family can contribute.
            if media is MediaType.VIDEO:
                # This short 2-fps fixture supports CORE repetition, but no eligible VRC pair.
                assert risk["score"] == pytest.approx(100 / 2.05)
                assert "video_repeated_content_correspondence=insufficient_evidence" in " ".join(
                    risk["limitations"]
                )
            assert risk["explanation"] and "status=complete" in risk["explanation"]
            for family in _ENSEMBLE_FAMILIES:
                if family.media_type is media:
                    assert f"family={family.key}" in risk["explanation"]
            assert all(
                _resolve_built_in_analyzer_definition(f["source_analyzer_id"])
                for f in result["findings"]
            )
            if media is MediaType.VIDEO:
                assert result["findings"]
            for finding in result["findings"]:
                source = next(
                    a
                    for a in result["analyzers"]
                    if a["analyzer_id"] == finding["source_analyzer_id"]
                )
                assert source["analyzer_version"] == finding["source_analyzer_version"]
                assert source["group"] == finding["group"]
                assert source["status"] == "completed" and source["applicable"]
            assert result["cleanup"]["status"] == "completed"
            assert not (Path(config.temporary_storage.root_path) / analysis_id).exists()
            page = client.get(f"/analyses/{analysis_id}/result", auth=WEB_AUTH)
            assert page.status_code == 200
            for analyzer in result["analyzers"]:
                assert analyzer["analyzer_id"] in page.text
            assert "Измерения" in page.text
            assert "Сводный сигнал" in page.text and "не вероятность подделки" in page.text
            assert risk["summary"] in page.text
            assert "Объяснение оценки" in page.text and risk["model_id"] in page.text
            assert risk["explanation"] in html.unescape(page.text)
            stored = client.get(f"/api/v1/analyses/{analysis_id}/result", headers=API_AUTH).json()
            assert stored == result
            persisted = json.loads(
                (Path(config.result.directory) / f"{analysis_id}.json").read_text(encoding="utf-8")
            )
            assert persisted == result
            encoded = json.dumps(result, allow_nan=False)
            assert str(tmp_path) not in encoded
    assert real_worker_processes and real_subprocesses


def test_ensemble_normalizers_consume_real_experimental_synthetic_measurements(tmp_path):
    specs = {s.analyzer_id: s for f in _ENSEMBLE_FAMILIES for s in f.members if s.normalizer}
    capacities = {MediaType.IMAGE: 3.4375, MediaType.AUDIO: 2.8125, MediaType.VIDEO: 2.05}
    samples = np.random.default_rng(61).normal(size=65536)
    samples[32768:49152] = samples[:16384]
    frames = np.zeros((12, 9, 16, 3), dtype="u1")
    frames[4:8] = 255
    for analyzer_id, spec in specs.items():
        definition = _resolve_runtime_analyzer_definition(analyzer_id)
        if analyzer_id.startswith("audio_"):
            request = audio_request(tmp_path, samples)
        elif analyzer_id.startswith("image_"):
            pixels = _periodic_tiles(True) if "resampling" in analyzer_id else _checker()
            if "noise" in analyzer_id:
                pixels[:132, :132] = (128 + (pixels[:132, :132].astype(int) - 128) * 4).astype("u1")
            request = image_request(tmp_path, pixels)
        else:
            request = video_request(
                tmp_path, [frames], ticks=[[0, 40, 80, 120, 160, 200, 240, 280, 320, 360, 360, 440]]
            )
        result = definition.factory().analyze(request)
        response, state = _ensemble_response(spec, result, ())
        assert response is not None and 0 < response <= 1 and state == "signal", analyzer_id
        assert _ensemble_response(spec, result, ()) == (response, state)
        assert result.score is None and not result.candidate_findings
        risk = AnalysisAssessmentService(_config(tmp_path).risk_assessment).assess(
            [analyzer_id], [result], []
        )[1]
        assert risk.score == pytest.approx(
            100 * response * spec.weight / capacities[result.media_type]
        )


def test_config_example_preserves_historical_assessment_and_diploma_selects_ensemble(tmp_path):
    example = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    risk = example["risk_assessment"]
    assert risk["model_id"] == "score_model_v1" and risk["model_version"] == "0.1.0"
    assert risk["thresholds"] == {"low_max": 5, "medium_max": 29}
    diploma = _config(tmp_path).risk_assessment
    assert diploma.model_id == "diploma_ensemble_v1" and diploma.model_version == "0.1.0"
    assert diploma.thresholds.low_max == 25 and diploma.thresholds.medium_max == 55
    assert not diploma.critical_override.enabled


def test_existing_spectral_roundoff_is_usable_by_ensemble(tmp_path):
    rng = np.random.default_rng(701)
    magnitude = np.zeros((200, 1, 2049))
    for i in range(0, 200, 2):
        magnitude[i, 0, :1024] = rng.random(1024)
        magnitude[i + 1, 0, 1024:] = rng.random(1025)
    definition = _resolve_runtime_analyzer_definition("audio_spectral_consistency")
    request = audio_request(tmp_path, np.ones(4096 + 199 * 1024), rate=48000, magnitude=magnitude)
    result = definition.factory().analyze(request)
    assert result.raw_metrics["windows"][0]["D1"]["max"] > 1
    risk = AnalysisAssessmentService(_config(tmp_path).risk_assessment).assess(
        [result.analyzer_id], [result], []
    )[1]
    assert risk.score == pytest.approx(100 * 0.65 / 2.8125)
