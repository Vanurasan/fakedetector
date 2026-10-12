"""ARC arithmetic and bounded retrieval: no attribution or accuracy claims."""

import json
import math
from dataclasses import replace

import numpy as np
import pytest
from support.diploma_inputs import audio_request, worker_request

from fakedetector.analyzers._audio_repeated import (
    AudioRepeatedSegmentCorrespondenceAnalyzer,
    _best,
    _centered,
    _checked,
    _lag_ncc,
    _support,
)
from fakedetector.analyzers._worker import _execute_worker, _SpawnedWorkerRunner
from fakedetector.domain import AnalyzerResult

ANALYZER = AudioRepeatedSegmentCorrespondenceAnalyzer()


def test_ncc_against_fsum_scalar_oracle_and_signed_gain():
    rng = np.random.default_rng(12)
    a = rng.uniform(-1, 1, 8192)
    b = rng.uniform(-1, 1, 8200)
    b[4:8196] = a * 0.25 + 0.1
    rhos = _lag_ncc(a, b)
    for lag in (0, 4, 8):
        x, y = a.tolist(), b[lag : lag + len(a)].tolist()
        xm, ym = math.fsum(x) / len(x), math.fsum(y) / len(y)
        xc, yc = [v - xm for v in x], [v - ym for v in y]
        oracle = math.fsum(u * v for u, v in zip(xc, yc, strict=True)) / math.sqrt(
            math.fsum(v * v for v in xc) * math.fsum(v * v for v in yc)
        )
        assert rhos[lag] == pytest.approx(oracle, abs=2e-14)
    assert _support(a, -a) == pytest.approx(-1)
    assert _support(a, a * 0.1) == pytest.approx(1)


def test_periodic_numeric_guard_zero_variance_and_tie_order():
    t = np.arange(8192)
    tone = np.sin(2 * np.pi * t / 32) + 0.25 * np.cos(2 * np.pi * t / 17)
    search = np.tile(tone, 2)
    assert _lag_ncc(tone, search)[0] == pytest.approx(1, abs=2e-14)
    assert _centered(np.zeros(8192)) is None
    assert _support(np.ones(8192), tone) is None
    assert np.isnan(_lag_ncc(np.ones(8192), search)).all()
    assert _best(np.ones(3), np.array([-1, 1, 2])) == 0
    assert _best(np.ones(3), np.array([-1, 0, 1])) == 1
    assert _best(np.full(3, np.nan), np.array([-1, 0, 1])) is None
    with pytest.raises(ValueError):
        _checked(np.array([1 + 65 * 2.0**-52]))


def _copy(tmp_path, *, channels=1):
    rng = np.random.default_rng(18)
    samples = rng.normal(0, 0.1, (65536, channels))
    samples[32768 + 137 : 32768 + 137 + 16384] = samples[:16384]
    if channels == 2:
        samples[:, 1] = 0
    return audio_request(tmp_path, samples)


def test_exact_copy_refined_offset_and_support(tmp_path):
    result = ANALYZER.analyze(_copy(tmp_path))
    copies = [
        p
        for p in result.raw_metrics["pairs"]
        if p["state"] == "measured" and p["channels"][0]["exact_decoded"]
    ]
    assert copies
    assert all(p["b_interval"][0] - p["a_interval"][0] == 32768 + 137 for p in copies)
    assert all(p["channels"][0]["structural_support"] for p in copies)
    assert all(p["channels"][0]["rho"] == pytest.approx(1) for p in copies)
    assert all(p["channels"][0]["support_rhos"] == pytest.approx([1, 1]) for p in copies)
    assert result.score is None and not result.candidate_findings


def test_unrelated_control_and_short_or_silent_support(tmp_path):
    request = audio_request(tmp_path, np.random.default_rng(19).normal(0, 0.1, 65536))
    result = ANALYZER.analyze(request)
    assert result.raw_metrics["pairs"]
    assert all(
        not c["exact_decoded"]
        for p in result.raw_metrics["pairs"]
        if p["state"] == "measured"
        for c in p["channels"]
    )
    assert (
        max(
            p["mean_selection_rho"] for p in result.raw_metrics["pairs"] if p["state"] == "measured"
        )
        < 0.1
    )
    for samples in (np.ones(16000), np.zeros(65536), np.ones(65536)):
        result = ANALYZER.analyze(audio_request(tmp_path, samples))
        assert result.raw_metrics["state"] == "insufficient_evidence"


def test_stereo_silent_channel_not_independent_support(tmp_path):
    result = ANALYZER.analyze(_copy(tmp_path, channels=2))
    measured = [p for p in result.raw_metrics["pairs"] if p["state"] == "measured"]
    assert measured
    for pair in measured:
        silent = pair["channels"][1]
        assert silent["exact_decoded"]
        assert not silent["structural_support"] and silent["rho"] is None
        assert silent["support_rhos"] == [None, None]


def test_arc_determinism_worker_contract_and_corruption(tmp_path):
    request = _copy(tmp_path)
    result = ANALYZER.analyze(request)
    assert result == ANALYZER.analyze(request)
    assert ANALYZER.check_applicability(request).applicable
    run = _SpawnedWorkerRunner().run(worker_request(ANALYZER, request), 15)
    envelope = json.loads(run.response)
    assert envelope["kind"] == "result"
    assert AnalyzerResult.model_validate(envelope["result"]).raw_metrics == result.raw_metrics
    assert len(run.response) < 65536
    assert (
        json.loads(_execute_worker(worker_request(ANALYZER, replace(request, metadata={}))))["kind"]
        == "analyzer_error"
    )
    request.artifacts[0].content._local_path.write_bytes(b"invalid")
    assert (
        json.loads(_execute_worker(worker_request(ANALYZER, request)))["kind"] == "analyzer_error"
    )


def test_arc_not_applicable_rate(tmp_path):
    assert not ANALYZER.check_applicability(
        audio_request(tmp_path, np.ones(8000), rate=96000)
    ).applicable
