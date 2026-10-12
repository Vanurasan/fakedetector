"""Independent arithmetic oracles and worker integration for weak audio measurements."""

import json
from dataclasses import replace

import numpy as np
import pytest
from support.diploma_inputs import audio_request, request_for, worker_request
from test_preprocessing import _image_descriptor

from fakedetector.analyzers._audio_experimental import (
    AudioBackgroundNoiseConsistencyAnalyzer,
    AudioSpectralConsistencyAnalyzer,
    AudioTemporalDiscontinuityAnalyzer,
    _atd,
    _spectral_pair,
)
from fakedetector.analyzers._worker import _execute_worker, _SpawnedWorkerRunner
from fakedetector.domain import AnalyzerResult, AnalyzerStatus
from fakedetector.lifecycle._finding_formation import FindingFormationService
from fakedetector.preprocessing._models import (
    AudioWindowDescriptor,
    ForensicManifest,
    ForensicRepresentation,
    IndexRange,
    SpectralWindowDescriptor,
)

ANALYZERS = [
    AudioTemporalDiscontinuityAnalyzer(),
    AudioSpectralConsistencyAnalyzer(),
    AudioBackgroundNoiseConsistencyAnalyzer(),
]


def test_maximum_audio_plan_has_bounded_output_and_arc_caps(tmp_path):
    from fakedetector.analyzers._audio_repeated import AudioRepeatedSegmentCorrespondenceAnalyzer

    samples = np.ones((480000, 2), dtype="<f8")
    samples[::2] = -1
    magnitude = np.ones((465, 2, 2049), dtype="<f8")
    request = audio_request(tmp_path, samples, rate=48000, magnitude=magnitude)
    manifest = request.forensic
    representations = [manifest.representations[0]]
    artifacts = []
    for index in range(3):
        for representation, artifact in zip(
            manifest.representations[1:], request.artifacts, strict=True
        ):
            facts = representation.facts
            data = facts.data.model_copy(
                update={"artifact_id": f"{facts.data.artifact_id}_{index}"}
            )
            if isinstance(facts, AudioWindowDescriptor):
                facts = facts.model_copy(
                    update={
                        "data": data,
                        "samples": IndexRange(start=index * 600000, stop=index * 600000 + 480000),
                        "first_sample_pts": index * 600000 - 1000,
                    }
                )
            else:
                assert isinstance(facts, SpectralWindowDescriptor)
                facts = facts.model_copy(
                    update={"data": data, "samples_artifact_id": f"samples_{index}"}
                )
            representations.append(
                ForensicRepresentation(provenance=representation.provenance, facts=facts)
            )
            artifacts.append(replace(artifact, artifact_id=data.artifact_id))
    manifest = ForensicManifest(
        source_sha256=manifest.source_sha256,
        media_type=manifest.media_type,
        representations=tuple(representations),
    )
    request = replace(
        request, artifacts=tuple(artifacts), metadata={"forensic": manifest.to_metadata()}
    )
    for analyzer in [*ANALYZERS, AudioRepeatedSegmentCorrespondenceAnalyzer()]:
        response = _execute_worker(worker_request(analyzer, request))
        assert len(response) < 65536
        envelope = json.loads(response)
        assert envelope["kind"] == "result", analyzer.analyzer_id
        metrics = envelope["result"]["raw_metrics"]
        if analyzer.analyzer_id == "audio_repeated_segment_correspondence":
            assert metrics["seeds_before_cap"] > 256
            assert metrics["seeds_retained"] == 256
            assert metrics["candidate_cap_hit"]
            assert len(metrics["pairs"]) == 64


def test_atd_step_constant_silence_and_earliest_tie():
    frame = np.ones(2048, dtype="<f8")
    boundary, values = _atd(frame)
    assert boundary == 768
    assert values == (None, 0, 0, None)
    assert _atd(frame * 0)[1] == (None, None, None, None)
    frame[1024:] = 3
    boundary, (jump, energy, signed, amplitude) = _atd(frame)
    assert boundary == 1024
    assert (jump, amplitude) == (1, 1)
    assert energy == pytest.approx(0.5)
    assert signed == pytest.approx(0.5)
    assert _atd(-frame)[1] == pytest.approx((jump, energy, signed, amplitude))


def test_atd_extreme_float_and_integer_precision():
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        frame = np.full(2048, -np.finfo(float).max)
        frame[1000:] *= -1
        assert _atd(frame)[1] == (1, 0, 0, 1)
        integers = np.full(2048, 2**30, dtype="<i4")
        integers[1000:] += 1
        assert _atd(integers)[0] == 1000
        assert _atd(integers)[1][0] == 1


def test_atd_support_uses_observed_samples_and_pts(tmp_path):
    samples = np.ones(2048)
    samples[1024:] = 3
    request = audio_request(tmp_path, samples, start=20000, pts=-2000)
    row = ANALYZERS[0].analyze(request).raw_metrics["windows"][0]
    assert row["J"]["max_sample"] == 21024
    assert row["J"]["support_samples"] == [20512, 21536]
    assert row["J"]["max_source_pts"] == -976


@pytest.mark.parametrize("length, frames", [(2047, 0), (2048, 1), (2559, 1), (2560, 2)])
def test_atd_frame_boundaries(tmp_path, length, frames):
    request = audio_request(tmp_path, np.zeros(length))
    result = ANALYZERS[0].analyze(request)
    assert result.raw_metrics["windows"][0]["frame_count"] == frames
    assert result.raw_metrics["state"] == ("measured" if frames else "insufficient_evidence")


def test_spectral_tv_flux_closed_form_and_gain_invariance():
    assert _spectral_pair(np.array([2.0, 0.0]), np.array([0.0, 2.0])) == (1, 0.5)
    assert _spectral_pair(np.array([2.0, 0.0]), np.array([4.0, 0.0])) == (0, pytest.approx(1 / 3))
    assert _spectral_pair(np.zeros(2), np.ones(2)) == (None, 1)
    assert _spectral_pair(np.zeros(2), np.zeros(2)) == (None, None)
    with np.errstate(over="raise", invalid="raise"):
        assert _spectral_pair(np.array([1e308, 0]), np.array([0, 1e308])) == (1, 0.5)


def test_spectral_equal_rms_frequency_transition_and_stationary_control(tmp_path):
    t = np.arange(16384)
    stable = np.sin(2 * np.pi * t / 32)
    changed = stable.copy()
    changed[8192:] = np.sin(2 * np.pi * t[8192:] / 8)
    control = ANALYZERS[1].analyze(audio_request(tmp_path, stable))
    positive = ANALYZERS[1].analyze(audio_request(tmp_path, changed))
    assert control.raw_metrics["windows"][0]["D4"]["max"] < 1e-10
    assert positive.raw_metrics["windows"][0]["D4"]["max"] > 0.99
    assert positive.raw_metrics["windows"][0]["D1"]["max"] > 0.2


@pytest.mark.parametrize("count, adjacent, separated", [(1, 0, 0), (2, 1, 0), (4, 3, 0), (5, 4, 1)])
def test_spectral_lag_boundaries(tmp_path, count, adjacent, separated):
    magnitude = np.ones((count, 1, 2049))
    request = audio_request(tmp_path, np.ones(4096 + (count - 1) * 1024), magnitude=magnitude)
    row = ANALYZERS[1].analyze(request).raw_metrics["windows"][0]
    assert row["D1"]["count"] == adjacent
    assert row["D4"]["count"] == separated


def test_low_energy_floor_changed_band_and_control(tmp_path):
    samples = np.ones(32000)
    magnitude = np.zeros((28, 1, 2049))
    magnitude[:, :, 1:129] = 1
    control = ANALYZERS[2].analyze(audio_request(tmp_path, samples, magnitude=magnitude))
    assert control.raw_metrics["contexts"][0]["tv"] == 0
    starts = np.arange(28) * 1024
    magnitude[starts >= 16000, :, 1:129] = 0
    magnitude[starts >= 16000, :, 129:257] = 1
    positive = ANALYZERS[2].analyze(audio_request(tmp_path, samples, magnitude=magnitude))
    row = positive.raw_metrics["contexts"][0]
    assert row["tv"] == 1
    assert row["signed_level_change"] == 0
    assert row["left_frames"] >= 8 and row["right_frames"] >= 8
    assert (
        positive.raw_metrics["background_attribution"]
        == "insufficient_evidence_no_independent_matching"
    )


@pytest.mark.parametrize("length, contexts", [(31999, 0), (32000, 1), (40000, 2)])
def test_floor_duration_boundary_and_silence(tmp_path, length, contexts):
    result = ANALYZERS[2].analyze(audio_request(tmp_path, np.zeros(length)))
    assert len(result.raw_metrics["contexts"]) == contexts
    for row in result.raw_metrics["contexts"]:
        assert row["tv"] is None and row["signed_level_change"] is None


@pytest.mark.parametrize("analyzer", ANALYZERS, ids=lambda a: a.analyzer_id)
def test_audio_contract_determinism_spawned_worker_and_no_risk(tmp_path, analyzer):
    request = audio_request(tmp_path, np.tile([0.25, 0.5, -0.25, -0.5], 8000))
    assert analyzer.check_applicability(request).applicable
    result = analyzer.analyze(request)
    assert result == analyzer.analyze(request)
    assert AnalyzerResult.model_validate_json(result.model_dump_json()) == result
    assert result.score is None and result.candidate_findings == []
    assert FindingFormationService().form_findings([result]) == ()
    run = _SpawnedWorkerRunner().run(worker_request(analyzer, request), 15)
    response = json.loads(run.response)
    assert response["kind"] == "result"
    decoded = AnalyzerResult.model_validate(response["result"])
    assert decoded.status is AnalyzerStatus.COMPLETED
    assert decoded.raw_metrics == result.raw_metrics
    assert len(run.response) < 65536


@pytest.mark.parametrize("analyzer", ANALYZERS, ids=lambda a: a.analyzer_id)
def test_audio_unsupported_profile_missing_corrupt_and_nonfinite(tmp_path, analyzer):
    request = audio_request(tmp_path, np.ones(16000), rate=96000)
    assert not analyzer.check_applicability(request).applicable
    request = audio_request(tmp_path, np.ones((16000, 3)))
    assert not analyzer.check_applicability(request).applicable
    image = request_for(
        tmp_path, _image_descriptor(width=512, height=512, image_format="PNG", color_mode="RGB")
    )
    assert not analyzer.check_applicability(image).applicable
    request = audio_request(tmp_path, np.ones(32000))
    assert (
        json.loads(_execute_worker(worker_request(analyzer, replace(request, metadata={}))))["kind"]
        == "analyzer_error"
    )
    selected = request.artifacts[0 if analyzer is ANALYZERS[0] else 1]
    selected.content._local_path.write_bytes(b"bad")
    assert (
        json.loads(_execute_worker(worker_request(analyzer, request)))["kind"] == "analyzer_error"
    )
    request = audio_request(tmp_path, np.ones(32000))
    selected = request.artifacts[0 if analyzer is ANALYZERS[0] else 1]
    raw = bytearray(selected.content._local_path.read_bytes())
    raw[:8] = np.array([float("nan")], dtype="<f8").tobytes()
    selected.content._local_path.write_bytes(raw)
    assert (
        json.loads(_execute_worker(worker_request(analyzer, request)))["kind"] == "analyzer_error"
    )
