"""Frozen-method parity, explanatory insufficiency and actual prototype workers."""

import json
import multiprocessing
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml
from support.diploma_inputs import audio_request, video_request

from fakedetector.analyzers import _video_vrc2_prototype as prototype
from fakedetector.analyzers._catalog import (
    _EXPERIMENTAL_ANALYZER_DEFINITIONS,
    _built_in_analyzer_registrations,
    _resolve_runtime_analyzer_definition,
    _resolve_worker_definition,
    _runtime_analyzer_registrations,
)
from fakedetector.analyzers._orchestrator import _plain_json_value
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.analyzers._transport import (
    _serialize_analyzer_result,
    _WorkerArtifact,
    _WorkerRequest,
)
from fakedetector.analyzers._video_experimental import VideoRepeatedContentCorrespondenceAnalyzer
from fakedetector.analyzers._worker import _SpawnedWorkerRunner, _WorkerRunKind
from fakedetector.config.models import AppConfig
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, MediaType
from fakedetector.lifecycle._assessment import _ENSEMBLE_FAMILIES

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts import diploma_vrc_redesign_research as research


ANALYZER = prototype.VideoRepeatedContentCorrespondenceV2PrototypeAnalyzer()
KEY = "prototype.video_repeated_content_correspondence_v2.v0"
CANDIDATE = next(c for c in research.candidates() if c.id == "D2__I25__K9__R10")


def frames(count=32):
    pattern = np.indices((9, 16, 3)).sum(axis=0) % 2
    amplitude = np.maximum(0, np.arange(count) - 8) ** 2 // 8
    return (100 + amplitude[:, None, None, None] * pattern).astype("u1")


def transport(request):
    return _WorkerRequest(
        worker_key=KEY,
        analysis_id=request.analysis_id,
        media_type=request.media_type.value,
        file_facts_json=request.file_facts.model_dump_json(),
        source_path=str(request.source._local_path),
        artifacts=tuple(
            _WorkerArtifact(
                a.artifact_id,
                a.artifact_type,
                str(a.content._local_path),
                a.format,
                a.start_time_seconds,
                a.end_time_seconds,
                a.frame_index,
            )
            for a in request.artifacts
        ),
        metadata_json=json.dumps(_plain_json_value(request.metadata)),
        warnings=request.warnings,
        settings_json=request.settings.model_dump_json(),
        timeout_seconds=15,
    )


@pytest.mark.parametrize("count", [3, 4, 8, 12, 16, 24, 32])
@pytest.mark.parametrize("kind", ["random", "ramp", "static"])
def test_component_math_parity_with_independent_accepted_harness(tmp_path, count, kind):
    pixels = (
        np.random.default_rng(33).integers(0, 256, (count, 9, 16, 3), dtype="u1")
        if kind == "random"
        else frames(count)
        if kind == "ramp"
        else np.full((count, 9, 16, 3), 37, dtype="u1")
    )
    request = video_request(tmp_path, [pixels, pixels.copy(), pixels.copy()])
    groups = research.prior.groups_from_request(request)
    expected = research.measure(
        {
            "dataset": "fixture",
            "sample_id": "tiny",
            "source_family": "first-party",
            "role": "reference",
            "split": "fixture",
        },
        groups,
        (CANDIDATE,),
    )[0][0]
    result = ANALYZER.analyze(request)
    actual = result.raw_metrics
    expected_state = expected["state"] if groups else "INSUFFICIENT_RUN_SUPPORT"
    assert actual["state"] == expected_state
    for new, old in [
        ("valid_group_count", "valid_groups"),
        ("eligible_group_count", "eligible_groups"),
        ("eligible_run_count", "eligible_runs"),
        ("relative_distinctiveness", "score"),
        ("energy_p25", "energy_p25"),
        ("d_best", "d_best"),
        ("p10_distance", "p10_distance"),
        ("median_distance", "median_distance"),
    ]:
        assert actual[new] == expected[old]
    if expected["best_run"] is not None:
        assert actual["best_run"]["constituents"] == expected["best_run"]["constituents"]
        assert actual["best_run"]["run_median_distance"] == actual["d_best"]
    else:
        assert actual["best_run"] is None
    assert result.score is None and result.score_name is None and not result.candidate_findings
    assert len(_serialize_analyzer_result(result)) < 65509
    assert ANALYZER.analyze(request).raw_metrics == actual


def test_identity_applicability_missing_evidence_and_geometry(tmp_path):
    assert ANALYZER.analyzer_version == "0.1.0"
    assert ANALYZER.group == "video"
    assert ANALYZER.supported_media_types == frozenset({MediaType.VIDEO})
    request = video_request(tmp_path, [frames()])
    assert ANALYZER.check_applicability(request).applicable
    assert ANALYZER.analyze(request).raw_metrics["profile"] == "VRC2-D2-I25-K9-R10-PROTOTYPE-1"
    assert not ANALYZER.check_applicability(audio_request(tmp_path, np.zeros(16))).applicable
    with pytest.raises(ValueError, match="manifest absent"):
        ANALYZER.check_applicability(replace(request, metadata={}))
    tiny = video_request(tmp_path, [np.ones((12, 8, 15, 3), dtype="u1")])
    assert ANALYZER.check_applicability(tiny).reason_code == "dense_geometry"


def test_descriptor_signed_spatial_and_temporal_energy_exact_parity():
    values = np.random.default_rng(11).integers(0, 256, (4, 432), dtype=np.int64)
    vector, energy = prototype._descriptor_and_energy(values)
    assert np.array_equal(vector, research.descriptor(values, "D2"))
    assert energy == np.abs(research.descriptor(values, "D3")).mean()
    assert np.array_equal(prototype._descriptor_and_energy(255 - values)[0], -vector)


def native_groups(tmp_path):
    request = video_request(tmp_path, [frames(), frames()])
    windows = prototype._dense_inputs(request)
    return [
        prototype._Group(
            windows[r],
            i,
            tuple(r * 5000 + (i + n) * 40 for n in range(4)),
            np.full((4, 432), i, dtype=np.int64),
        )
        for r in range(2)
        for i in range(29)
    ]


@pytest.mark.parametrize("gap,eligible", [(1999, False), (2000, True), (2001, True)])
def test_real_pts_gate_boundary(tmp_path, gap, eligible):
    groups = native_groups(tmp_path)
    a, b = groups[0], groups[29]
    b = replace(b, ticks=tuple(a.ticks[-1] + gap + i * 31 for i in range(4)))
    assert bool(prototype._distant_pairs([a, b])) == eligible
    assert bool(prototype._distant_pairs([b, a])) == eligible


def test_i25_strictness_run_median_tie_break_and_missing_start(tmp_path, monkeypatch):
    groups = native_groups(tmp_path)
    monkeypatch.setattr(
        prototype,
        "_descriptor_and_energy",
        lambda v: (np.full(3156, float(v[0, 0])), float(v[0, 0])),
    )
    result = prototype._measure_groups(groups)
    assert result["energy_p25"] == 7.0
    assert result["eligible_group_count"] == 42  # exactly the >7 groups on both sides
    assert result["eligible_run_count"] == 13**2
    assert result["run_support"]["maximum_aligned_run_support"] == 21
    assert result["best_run"]["start_ordinal_a"] == result["best_run"]["start_ordinal_b"] == 8
    assert len(result["best_run"]["constituents"]) == 9
    assert result["relative_distinctiveness"] == 1
    assert result["run_support"]["sequences"][0]["contiguous_eligible_start_lengths"] == [21]
    broken = prototype._measure_groups([g for g in groups if g.start != 18])
    assert broken["energy_p25"] == 6.75  # removal changes the per-file population
    assert broken["run_support"]["maximum_aligned_run_support"] == 11  # starts 7..17
    monkeypatch.setattr(
        prototype, "_descriptor_and_energy", lambda v: (np.zeros(3156), float(v[0, 0]))
    )
    degenerate = prototype._measure_groups(groups)
    assert degenerate["state"] == "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"
    assert degenerate["relative_distinctiveness"] is None
    monkeypatch.setattr(prototype, "_descriptor_and_energy", lambda v: (np.zeros(3156), 4.0))
    tied = prototype._measure_groups(groups)
    assert tied["state"] == "INSUFFICIENT_LOW_INFORMATION"
    assert tied["eligible_group_count"] == 0


def test_one_supported_run_uses_nine_pair_median_and_epsilon(tmp_path, monkeypatch):
    groups = native_groups(tmp_path)
    for i in range(29, 58):
        groups[i] = replace(groups[i], values=groups[i].values + 100)

    def synthetic_descriptor(values):
        marker = int(values[0, 0])
        start = marker % 100
        distance = (
            [1, 2, 3, 4, 5, 6, 7, 8, 100][start - 8] if marker >= 100 and 8 <= start <= 16 else 0
        )
        return np.full(3156, float(distance)), float(8 <= start <= 16)

    monkeypatch.setattr(prototype, "_descriptor_and_energy", synthetic_descriptor)
    result = prototype._measure_groups(groups)
    assert result["eligible_run_count"] == 1
    assert result["d_best"] == result["p10_distance"] == 5
    assert result["relative_distinctiveness"] == 0
    assert [p["distance"] for p in result["best_run"]["constituents"]] == [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        100,
    ]
    monkeypatch.setattr(
        prototype,
        "_descriptor_and_energy",
        lambda v: (synthetic_descriptor(v)[0] * 1e-14, synthetic_descriptor(v)[1]),
    )
    assert prototype._measure_groups(groups)["state"] == "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"


def test_short_and_static_states_are_null_not_zero(tmp_path):
    short = ANALYZER.analyze(video_request(tmp_path, [frames(8)] * 2)).raw_metrics
    assert short["state"] == "INSUFFICIENT_LOW_INFORMATION"
    static = ANALYZER.analyze(
        video_request(tmp_path, [np.ones((32, 9, 16, 3), dtype="u1")] * 3)
    ).raw_metrics
    assert static["state"] == "INSUFFICIENT_LOW_INFORMATION"
    assert static["relative_distinctiveness"] is None
    no_pairs = ANALYZER.analyze(video_request(tmp_path, [frames()])).raw_metrics
    assert no_pairs["state"] == "INSUFFICIENT_RUN_SUPPORT"
    assert no_pairs["run_support"]["maximum_aligned_run_support"] == 0
    assert no_pairs["run_support"]["temporal_gap_eligible_pair_count"] == 0


def test_bounds_quantile_and_invalid_numbers(tmp_path):
    groups = native_groups(tmp_path)
    with pytest.raises(ValueError, match="budget"):
        prototype._measure_groups(groups * 2)
    with pytest.raises(ValueError, match="duplicate"):
        prototype._measure_groups(groups + [groups[0]])
    assert prototype._quantile(list(range(1, 11)), 0.1) == 1.9
    assert prototype._quantile(list(range(1, 11)), 0.5) == 5.5
    assert prototype._quantile([], 0.1) is None
    with pytest.raises(ValueError, match="nonfinite"):
        prototype._quantile([float("inf")], 0.1)


@pytest.mark.parametrize("kind", ["sparse-periodic", "low-amplitude-random"])
def test_nearly_static_variation_has_no_absolute_motion_floor(tmp_path, kind):
    pixels = np.full((32, 9, 16, 3), 100, dtype="u1")
    if kind == "sparse-periodic":
        # Only a single grid cell changes by one intensity unit in selected frames.
        pixels[9::2, 0, 0, 0] = 101
    else:
        pixels[10:] = 100 + np.random.default_rng(760).integers(0, 2, (22, 9, 16, 3), dtype="u1")
    request = video_request(tmp_path, [pixels] * 3)
    actual = ANALYZER.analyze(request).raw_metrics
    expected = research.measure(
        {
            "dataset": "fixture",
            "sample_id": "near-static",
            "source_family": "first-party",
            "role": "reference",
            "split": "fixture",
        },
        research.prior.groups_from_request(request),
        (CANDIDATE,),
    )[0][0]
    assert actual["eligible_group_count"] > 0
    assert actual["energy_p25"] < (0.01 if kind == "sparse-periodic" else 0.2)
    assert actual["energy_p25"] == expected["energy_p25"]
    assert actual["state"] == expected["state"]
    assert actual["relative_distinctiveness"] == expected["score"]
    if kind == "low-amplitude-random":
        assert actual["state"] == "MEASURED" and actual["relative_distinctiveness"] == 1
    else:
        assert actual["state"] == "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"


def test_closed_runtime_default_and_ensemble_isolation():
    definition = _resolve_worker_definition(KEY)
    assert definition.factory is type(ANALYZER)
    assert definition.max_candidate_findings == 0 and not definition.candidate_finding_types
    assert _resolve_runtime_analyzer_definition(ANALYZER.analyzer_id) is None
    core = _built_in_analyzer_registrations()
    assert {r.analyzer_id for r in core} == {
        "image_metadata_consistency",
        "image_copy_move_correspondence",
        "image_jpeg_double_quantization",
        "audio_pcm_quality",
        "video_sampled_frame_quality",
    }
    runtime = _runtime_analyzer_registrations()
    assert len(runtime) == 15 and runtime[:5] == core
    assert len(_EXPERIMENTAL_ANALYZER_DEFINITIONS) == 10
    assert ANALYZER.analyzer_id not in {r.analyzer_id for r in runtime}
    assert ANALYZER.analyzer_id not in {
        m.analyzer_id for f in _ENSEMBLE_FAMILIES for m in f.members
    }
    for name in ["config.example.yaml", "config.diploma.yaml"]:
        raw = yaml.safe_load((Path("config") / name).read_text("utf-8"))
        config = AppConfig.model_validate(raw)
        registry = AnalyzerRegistry(config, runtime)
        assert ANALYZER.analyzer_id not in {
            r.registration.analyzer_id for r in registry.active_plan(MediaType.VIDEO)
        }
        raw["analyzers"]["video"]["enabled"].append(ANALYZER.analyzer_id)
        with pytest.raises(ValueError):
            AnalyzerRegistry(AppConfig.model_validate(raw), runtime)


def test_real_worker_serialization_replay_errors_timeout_and_reap(tmp_path):
    request = video_request(tmp_path, [frames()] * 3)
    worker_request = transport(request)
    runner = _SpawnedWorkerRunner()
    before = {p.pid for p in multiprocessing.active_children()}
    results = []
    for _ in range(2):
        run = runner.run(worker_request, 15)
        assert run.kind is _WorkerRunKind.RESPONSE
        payload = json.loads(run.response)
        assert payload["kind"] == "result"
        result = AnalyzerResult.model_validate(payload["result"])
        assert result.status is AnalyzerStatus.COMPLETED
        assert result.score is None and not result.candidate_findings
        results.append(result.raw_metrics)
    assert results[0] == results[1] == ANALYZER.analyze(request).raw_metrics
    malformed = runner.run(replace(worker_request, settings_json='{"unexpected":true}'), 15)
    assert json.loads(malformed.response)["kind"] == "worker_error"
    corrupt = request.artifacts[0].content._local_path
    corrupt.write_bytes(b"invalid")
    failed = runner.run(worker_request, 15)
    assert json.loads(failed.response)["kind"] == "analyzer_error"
    assert runner.run(worker_request, 0.001).kind is _WorkerRunKind.TIMEOUT
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_vrc1_unchanged_under_prototype_execution(tmp_path):
    request = video_request(tmp_path, [frames()] * 3)
    vrc1 = VideoRepeatedContentCorrespondenceAnalyzer()
    baseline = vrc1.analyze(request).raw_metrics
    ANALYZER.analyze(request)
    assert vrc1.analyze(request).raw_metrics == baseline
    groups = research.prior.groups_from_request(request)
    assert research.prior.verify_reproduction(research.prior.enumerate_pairs(groups), baseline) == 0
