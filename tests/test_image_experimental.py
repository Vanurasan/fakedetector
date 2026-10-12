"""Synthetic support/matching oracles for descriptive image profiles."""

import json
from dataclasses import replace

import numpy as np
import pytest
from support.diploma_inputs import audio_request, image_request, worker_request

from fakedetector.analyzers._image_experimental import (
    ImageNoiseResidualConsistencyAnalyzer,
    ImageResamplingConsistencyAnalyzer,
    _direction,
    _peers,
    _periodogram,
    _TileContext,
)
from fakedetector.analyzers._worker import _execute_worker, _SpawnedWorkerRunner
from fakedetector.domain import AnalyzerResult, AnalyzerStatus
from fakedetector.preprocessing._media_tools import TileRegion

ANALYZERS = [ImageNoiseResidualConsistencyAnalyzer(), ImageResamplingConsistencyAnalyzer()]


def _checker(size=768):
    y, x = np.indices((size, size))
    return np.repeat((128 + 2 * (2 * ((x + y) % 2) - 1))[:, :, None], 3, axis=2).astype("u1")


def test_noise_local_residual_positive_and_identical_control(tmp_path):
    pixels = _checker()
    control = ANALYZERS[0].analyze(image_request(tmp_path, pixels))
    assert control.raw_metrics["state"] == "measured"
    assert control.raw_metrics["max_log2_ratio"] == pytest.approx(0, abs=1e-12)
    pixels[:132, :132] = (128 + (pixels[:132, :132].astype(int) - 128) * 4).astype("u1")
    positive = ANALYZERS[0].analyze(image_request(tmp_path, pixels))
    assert positive.raw_metrics["tiles"][0]["mad"] == pytest.approx(8)
    assert positive.raw_metrics["max_log2_ratio"] == pytest.approx(np.log2(8.25 / 2.25))
    assert positive.raw_metrics["comparisons"][0]["tile"] == 0


def _periodic_tiles(changed):
    pixels = np.full((768, 768, 3), 128, dtype="u1")
    y, x = np.indices((132, 132))
    for row in range(4):
        for col in range(4):
            freq = 7 if changed and (row, col) == (0, 0) else 5
            signal = 128 + (2 * (y % 2) - 1) * np.rint(
                4 + 3 * np.cos(2 * np.pi * freq * (x - 2) / 128)
            )
            left, top = col * (768 - 132) // 3, row * (768 - 132) // 3
            pixels[top : top + 132, left : left + 132] = signal[:, :, None].astype("u1")
    return pixels


def test_resampling_local_periodicity_and_matched_control(tmp_path):
    control = ANALYZERS[1].analyze(image_request(tmp_path, _periodic_tiles(False)))
    positive = ANALYZERS[1].analyze(image_request(tmp_path, _periodic_tiles(True)))
    assert control.raw_metrics["max_log2_ratio"] == pytest.approx(0, abs=1e-10)
    # Frozen arithmetic oracle for this quantized periodic fixture, not a decision threshold.
    assert positive.raw_metrics["max_log2_ratio"] == pytest.approx(1.1973677781842011)
    assert any(row["tile"] == 0 for row in positive.raw_metrics["comparisons"])


def test_periodogram_notch_texture_veto_and_zero_support():
    assert _periodogram(np.ones(128))[0] is None
    y, x = np.indices((128, 128))
    magnitude = 2 + np.cos(2 * np.pi * x * 10 / 128)
    direction = _direction(magnitude, np.full((128, 128), 128.0), 0)
    assert direction.peak == 10 and not direction.veto
    assert direction.phase == pytest.approx(0)
    veto = _direction(magnitude, magnitude, 0)
    assert veto.veto
    notched = _direction(2 + np.cos(2 * np.pi * x * 16 / 128), magnitude, 0)
    assert notched.raw_peak == 16
    assert all(abs(notched.peak - 16 * m) > 2 for m in range(1, 5))


def test_matching_inclusive_bounds_no_self_and_spatial_ties():
    target = _TileContext(0, TileRegion(128, 128, 128, 128), 100.0, 0.75, True)
    candidates = [target]
    for i, (x, y) in enumerate([(0, 128), (128, 0), (256, 128), (128, 256)], 1):
        candidates.append(_TileContext(i, TileRegion(x, y, 128, 128), 116.0, 0.75, True))
    assert _peers(target, candidates) == [1, 2, 3, 4]
    assert _peers(target, [replace(c, brightness=116.0001) for c in candidates]) == []
    assert _peers(target, [replace(c, texture=2.0) for c in candidates]) == []


@pytest.mark.parametrize("analyzer", ANALYZERS, ids=lambda a: a.analyzer_id)
def test_alpha_saturation_flat_insufficient_and_dimensions(tmp_path, analyzer):
    pixels = np.full((512, 512, 4), 128, dtype="u1")
    assert (
        analyzer.analyze(image_request(tmp_path, pixels)).raw_metrics["state"]
        == "insufficient_evidence"
    )
    pixels[:, :, 3] = 255
    pixels[:, :, :3] = 4
    assert (
        analyzer.analyze(image_request(tmp_path, pixels)).raw_metrics["state"]
        == "insufficient_evidence"
    )
    pixels[:, :, :3] = 251
    assert (
        analyzer.analyze(image_request(tmp_path, pixels)).raw_metrics["state"]
        == "insufficient_evidence"
    )
    assert not analyzer.check_applicability(image_request(tmp_path, _checker(511))).applicable
    assert not analyzer.check_applicability(audio_request(tmp_path, np.zeros(2048))).applicable
    request = image_request(tmp_path, _checker())
    assert not analyzer.check_applicability(replace(request, artifacts=())).applicable
    request.artifacts[0].content._local_path.write_bytes(b"broken PNG")
    assert (
        json.loads(_execute_worker(worker_request(analyzer, request)))["kind"] == "analyzer_error"
    )


@pytest.mark.parametrize("analyzer", ANALYZERS, ids=lambda a: a.analyzer_id)
def test_image_determinism_contract_and_spawned_worker(tmp_path, analyzer):
    request = image_request(tmp_path, _periodic_tiles(True))
    assert analyzer.check_applicability(request).applicable
    result = analyzer.analyze(request)
    assert analyzer.analyze(request) == result
    assert result.score is None and not result.candidate_findings
    run = _SpawnedWorkerRunner().run(worker_request(analyzer, request), 15)
    envelope = json.loads(run.response)
    assert envelope["kind"] == "result"
    actual = AnalyzerResult.model_validate(envelope["result"])
    assert actual.status is AnalyzerStatus.COMPLETED
    assert actual.raw_metrics == result.raw_metrics
    assert len(run.response) < 65536
