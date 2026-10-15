"""First-party tiny fixtures only; never run the accepted external corpus in pytest."""

import copy
import csv
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from support.diploma_inputs import video_request

from fakedetector.analyzers._video_experimental import (
    VideoRepeatedContentCorrespondenceAnalyzer,
    _block_descriptor,
)
from fakedetector.lifecycle._assessment import _video_repetition_response

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts import diploma_vrc_redesign_research as research


def group(start=0, region=0, ticks=None, values=None, base=Fraction(1, 1000)):
    return research.prior.Group(
        0,
        region,
        start,
        ticks if ticks is not None else tuple(region * 5000 + (start + i) * 100 for i in range(4)),
        base,
        (16, 9, 9, 16, 3),
        np.zeros((4, 432), dtype=np.int64) if values is None else values,
    )


def identity(dataset="benign", family="video-01", role="BENIGN_REFERENCE", split="observation"):
    return {
        "dataset": dataset,
        "source_family": family,
        "role": role,
        "split": split,
        "sample_id": f"{dataset}-{family}-{role}",
    }


def grid_fixture():
    time, row, col, channel = np.indices((4, 9, 16, 3))
    return (20 + time * col + 2 * row + 3 * channel + col).reshape(4, 432)


@pytest.mark.parametrize("count", [3, 4, 8, 9, 16, 32])
def test_exact_production_control_reproduction(tmp_path, count):
    frames = np.random.default_rng(120).integers(0, 256, (count, 19, 33, 3), dtype=np.uint8)
    request = video_request(tmp_path, [frames, frames.copy()])
    groups = research.prior.groups_from_request(request)
    metrics = VideoRepeatedContentCorrespondenceAnalyzer().analyze(request).raw_metrics
    assert research.prior.verify_reproduction(research.prior.enumerate_pairs(groups), metrics) == 0
    control = next(c for c in research.candidates() if c.id == research.PRODUCTION)
    rows, _ = research.measure(identity(), groups, (control,))
    assert rows[0]["score"] == _video_repetition_response(metrics)
    if groups:
        assert np.array_equal(groups[0].values[0], _block_descriptor(frames[0]))


def test_centered_grid_channel_offset_invariance():
    values = grid_fixture()
    centered = research.descriptor(values, "D1").reshape(4, 9, 16, 3)
    np.testing.assert_allclose(centered.mean(axis=(1, 2)), 0, atol=1e-14)
    shifted = values.reshape(4, 9, 16, 3) + np.array([[[[17, 3, 22]]]])
    assert np.array_equal(research.descriptor(shifted.reshape(4, 432), "D1"), centered.ravel())
    assert not np.array_equal(research.descriptor(values[:, ::-1], "D1"), centered.ravel())


def test_signed_spatial_gradients_exact_construction():
    grid = grid_fixture().reshape(4, 9, 16, 3)
    actual = research.descriptor(grid.reshape(4, 432), "D2")
    expected = [
        int(grid[t, r, c + 1, ch] - grid[t, r, c, ch])
        for t in range(4)
        for r in range(9)
        for c in range(15)
        for ch in range(3)
    ]
    expected += [
        int(grid[t, r + 1, c, ch] - grid[t, r, c, ch])
        for t in range(4)
        for r in range(8)
        for c in range(16)
        for ch in range(3)
    ]
    assert np.array_equal(actual, expected)
    assert actual.size == 3156
    reverse = research.descriptor((200 - grid).reshape(4, 432), "D2")
    assert np.array_equal(reverse, -actual)


def test_temporal_residual_energy_and_hybrid_component_weighting():
    values = grid_fixture()
    residual = research.descriptor(values, "D3")
    # Temporal increment at column c is c minus its spatial mean, 7.5.
    expected = np.tile(
        np.broadcast_to(np.arange(16)[None, :, None] - 7.5, (9, 16, 3)), (3, 1, 1, 1)
    )
    assert np.array_equal(residual, expected.ravel())
    assert residual.size == 1296
    energy, keep, p25 = research.information([group(values=values)], "I0")
    assert energy.tolist() == [4.0] and p25 == 4.0 and keep.tolist() == [True]
    hybrid = research.descriptor(values, "D4")
    spatial = research.descriptor(values, "D2")
    assert hybrid.size == 4452
    assert np.array_equal(hybrid, np.concatenate((spatial, residual)))
    assert np.abs(hybrid).mean() == pytest.approx(
        (np.abs(spatial).sum() + np.abs(residual).sum()) / 4452
    )


@pytest.mark.parametrize(
    "gap,eligible",
    [(Fraction(1999, 1000), False), (Fraction(2), True), (Fraction(2001, 1000), True)],
)
def test_exact_pts_gate_without_fps_assumption(gap, eligible):
    a = group(ticks=(-100, 70, 150, 300))
    first = Fraction(3, 10) + gap
    b = group(
        region=1, ticks=tuple(int(first * 3000) + i * 17 for i in range(4)), base=Fraction(1, 3000)
    )
    assert bool(research.distant_pairs([a, b])) is eligible
    assert bool(research.distant_pairs([b, a])) is eligible
    assert not research.distant_pairs([a, replace(b, stream=1)])
    assert not research.distant_pairs([a, replace(b, geometry=(1, 2, 3))])


def test_unknown_or_nonmonotone_pts_never_interpolated(tmp_path):
    frames = np.ones((10, 9, 16, 3), dtype=np.uint8)
    request = video_request(
        tmp_path,
        [frames],
        ticks=[list(range(0, 1000, 100))],
        masks=[[5, 5, 4, 5, 5, 5, 5, 5, 5, 5]],
    )
    assert [g.start for g in research.prior.groups_from_request(request)] == [3, 4, 5, 6]
    other = tmp_path / "other"
    other.mkdir()
    request = video_request(
        other, [frames], ticks=[[0, 100, 200, 300, 300, 500, 600, 700, 800, 900]]
    )
    assert [g.start for g in research.prior.groups_from_request(request)] == [0, 4, 5, 6]


def test_i25_strict_ties_and_all_static_insufficiency():
    static = group(values=np.full((4, 432), 90, dtype=np.int64))
    dynamic = group(values=grid_fixture())
    energies, keep, p25 = research.information([static, static, dynamic, dynamic], "I25")
    assert p25 == 0 and energies.tolist() == [0, 0, 4, 4]
    assert keep.tolist() == [False, False, True, True]
    assert research.information([dynamic] * 4, "I25")[1].tolist() == [False] * 4
    groups = [
        replace(static, region=r, start=s, ticks=tuple(r * 5000 + (s + i) * 100 for i in range(4)))
        for r in (0, 1)
        for s in range(12)
    ]
    variants = tuple(c for c in research.candidates() if c.descriptor == "D1")
    rows, _ = research.measure(identity(), groups, variants)
    assert all(r["score"] is None for r in rows)
    assert {r["state"] for r in rows if r["information"] == "I25"} == {
        "INSUFFICIENT_LOW_INFORMATION"
    }
    assert {r["state"] for r in rows if r["information"] == "I0"} == {
        "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"
    }


@pytest.mark.parametrize("k", [3, 5, 9])
def test_complete_aligned_runs_and_missing_start_breaks(k):
    groups = [group(s, r) for r in (0, 1) for s in range(12)]
    runs = research.aligned_runs(groups, np.ones(24, dtype=bool), k)
    assert len(runs) == (12 - k + 1) ** 2
    for run in runs:
        assert np.array_equal(np.diff(run, axis=1), np.ones((2, k - 1)))
    filtered = [g for g in groups if not (g.region == 0 and g.start == 4)]
    broken = research.aligned_runs(filtered, np.ones(len(filtered), dtype=bool), k)
    for run in broken:
        assert all(np.all(np.diff([filtered[i].start for i in side]) == 1) for side in run)
    keep = np.ones(24, dtype=bool)
    keep[4] = False
    assert len(broken) == len(research.aligned_runs(groups, keep, k))
    assert not len(research.aligned_runs(groups[:2], np.ones(2, dtype=bool), k))


def test_every_constituent_must_pass_pts_gap_and_signed_mean_distance():
    groups = [group(s, 0) for s in range(3)] + [group(s, 1) for s in range(3)]
    groups[-1] = replace(groups[-1], ticks=(2400, 2500, 2600, 2700))
    assert len(research.aligned_runs(groups, np.ones(6, dtype=bool), 3)) == 0
    a = group(values=grid_fixture())
    b = replace(a, values=200 - a.values)
    distance = research.distance_matrix([a, b], "D2")[0, 1]
    assert (
        distance
        == np.abs(research.descriptor(a.values, "D2") - research.descriptor(b.values, "D2")).mean()
    )


def test_run_uses_median_and_preserves_explanatory_constituents(monkeypatch):
    groups = [group(s, r, values=grid_fixture()) for r in (0, 1) for s in range(3)]
    matrix = np.zeros((6, 6))
    matrix[0, 3], matrix[1, 4], matrix[2, 5] = 1, 5, 100
    monkeypatch.setattr(research, "distance_matrix", lambda *_: matrix)
    candidate = research.candidates()[0]
    rows, populations = research.measure(identity(), groups, (candidate,))
    assert rows[0]["d_best"] == 5 and rows[0]["eligible_runs"] == 1
    assert list(populations.values())[0].tolist() == [5]
    assert [p["distance"] for p in rows[0]["best_run"]["constituents"]] == [1, 5, 100]
    assert rows[0]["score"] == 0  # A sole run is not distinctive against itself.


@pytest.mark.parametrize("rule,expected", [("R10", 1 - 1 / 1.9), ("R50", 1 - 1 / 5.5)])
def test_relative_formulas_linear_quantiles_and_scale_invariance(rule, expected):
    values = list(range(1, 11))
    score, state = research.relative_score(values, rule)
    assert state == "MEASURED" and score == pytest.approx(expected)
    assert research.relative_score([x * 12 for x in values], rule)[0] == pytest.approx(score)


def test_raw_control_preserves_joint_descriptor_and_known_repeat_location():
    values = grid_fixture()
    groups = [group(6 + s, region, values=values + s) for region in (0, 2) for s in range(3)]
    distances = research.distance_matrix(groups, "raw")
    for pair in research.prior.enumerate_pairs(groups):
        if pair.gap >= 2:
            a = next(i for i, g in enumerate(groups) if g.key == pair.a.key)
            b = next(i for i, g in enumerate(groups) if g.key == pair.b.key)
            assert distances[a, b] == pair.distance
    run = np.array([[0, 1, 2], [3, 4, 5]])
    energy = research.information(groups, "I0")[0]
    sample = identity("paired", role="repeat")
    detail = research.run_details(groups, run, distances, energy, sample)
    assert detail["known_inserted_episode_selected"] is True
    groups[3] = replace(groups[3], start=7)
    assert (
        research.run_details(groups, run, distances, energy, sample)[
            "known_inserted_episode_selected"
        ]
        is False
    )


def test_empty_groups_are_explicit_insufficient_and_no_other_candidates_evaluated(monkeypatch):
    candidate = research.candidates()[0]
    rows, _ = research.measure(identity(), [], (candidate,))
    assert rows[0]["score"] is None
    assert rows[0]["state"] == "INSUFFICIENT_VALID_GROUPS"
    original = research.distance_matrix
    seen = []

    def tracked(groups, kind):
        seen.append(kind)
        return original(groups, kind)

    monkeypatch.setattr(research, "distance_matrix", tracked)
    groups = [group(s, r, values=grid_fixture()) for r in (0, 1) for s in range(4)]
    research.measure(identity(), groups, (candidate,))
    assert seen == ["D1"]


@pytest.mark.parametrize(
    "values,state",
    [
        ([], "INSUFFICIENT_RUN_SUPPORT"),
        ([0] * 4, "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"),
        ([1e-13] * 4, "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"),
        ([7] * 4, "MEASURED"),
    ],
)
def test_degenerate_distributions_explicit_state_not_zero(values, state):
    score, actual = research.relative_score(values, "R10")
    assert actual == state
    assert (score is None) == (state != "MEASURED")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_numbers_rejected(value):
    with pytest.raises(ValueError):
        research.relative_score([value], "R50")


def scored_rows(
    candidate=None, families=5, split="observation", benign_score=0.2, repeat_score=0.8
):
    candidate = candidate or research.candidates()[0].id
    rows = []
    for number in range(1, families + 1):
        for dataset, role, score in (
            ("benign", "BENIGN_REFERENCE", benign_score),
            ("benign", "BENIGN_PROCESSING", benign_score),
            ("paired", "reference", benign_score),
            ("paired", "repeat", repeat_score),
        ):
            rows.append(
                {
                    **identity(dataset, f"video-{number:02}", role, split),
                    "candidate_id": candidate,
                    "score": score,
                    "state": "MEASURED" if score is not None else "INSUFFICIENT_RUN_SUPPORT",
                    "deterministic": True,
                }
            )
    return rows


def test_family_denominators_paired_deltas_roles_and_insufficient_counts():
    rows = scored_rows()
    summary = research.summarize(rows)
    assert summary["observation_ready"]
    assert summary["families"] == 5 and summary["benign"]["n"] == 10
    assert summary["paired_total"] == 5 and summary["paired_positive"] == 5
    assert summary["paired"]["median"] == pytest.approx(0.6)
    assert summary["by_role"]["BENIGN_PROCESSING"]["n"] == 5
    assert summary["by_role"]["BENIGN_PROCESSING"]["ge075"] == 0
    rows[0].update(score=None, state="INSUFFICIENT_LOW_INFORMATION")
    reduced = research.summarize(rows)
    assert reduced["benign"]["n"] == 9 and reduced["benign_total"] == 10
    assert reduced["measurable_families"] == 4 and not reduced["observation_ready"]
    assert reduced["insufficient_reasons"] == {"INSUFFICIENT_LOW_INFORMATION": 1}
    rows[2].update(score=None, state="INSUFFICIENT_RUN_SUPPORT")
    assert research.paired_deltas(rows)[0]["delta"] is None
    with pytest.raises(ValueError, match="isolation"):
        research.paired_deltas(rows + [rows[2]])
    rows[2]["split"] = "holdout_benign"
    with pytest.raises(ValueError, match="split"):
        research.paired_deltas(rows)


def test_observation_screen_all_gates_and_single_family_improvement():
    rows = scored_rows()
    for row in rows:
        if (
            row["dataset"] == "paired"
            and row["role"] == "repeat"
            and row["source_family"] != "video-01"
        ):
            row["score"] = 0.2
    summary = research.summarize(rows)
    assert summary["paired_positive"] == 1
    assert not summary["observation_gates"]["distributed_improvement"]
    assert not summary["observation_ready"]
    assert not research.summarize(scored_rows(benign_score=0.76))["observation_ready"]


def test_deterministic_ranking_simplicity_short_runs_and_lexical_tie():
    summaries = [research.summarize(scored_rows(c.id)) for c in research.candidates()[:48]]
    summaries.reverse()
    ranked = sorted(summaries, key=research.rank_key)
    assert ranked[0]["candidate_id"] == "D1__I0__K3__R10"
    assert [r["candidate_id"] for r in ranked[:4]] == [
        "D1__I0__K3__R10",
        "D1__I0__K3__R50",
        "D1__I25__K3__R10",
        "D1__I25__K3__R50",
    ]
    contender = copy.deepcopy(ranked[-1])
    contender["paired"]["median"] += 0.1
    assert research.rank_key(contender) < research.rank_key(ranked[0])
    contender["observation_ready"] = False
    assert research.rank_key(contender) > research.rank_key(ranked[0])
    with pytest.raises(ValueError, match="Controls"):
        research.rank_key(research.summarize(scored_rows(research.PRODUCTION)))


@pytest.mark.parametrize("gate", list("ABCDEFGHIJ"))
def test_readiness_each_required_gate_and_no_negative_diagnostic_promotion(gate):
    selected = {"observation_ready": True}
    held = research.summarize(scored_rows(families=3, split="holdout_benign"))
    combined = research.summarize(scored_rows(families=8))
    production = research.summarize(scored_rows(families=8, benign_score=0.99))
    assert (
        research.readiness(selected, held, combined, production, unchanged=True)["disposition"]
        == "VRC2_METHOD_CANDIDATE_READY_FOR_PROTOTYPE"
    )
    if gate == "A":
        selected["observation_ready"] = False
    if gate == "B":
        held["measurable_families"] = 2
    if gate == "C":
        held["paired_positive"] = 2
    if gate == "D":
        combined["paired_positive"] = 6
    if gate == "E":
        combined["paired"]["median"] = 0.149
    if gate == "F":
        combined["benign"]["median"] = 0.501
    if gate == "G":
        combined["benign_ge075"] = 5
    if gate == "H":
        combined["repeat"]["median"] = 0.699
    if gate == "I":
        combined["deterministic_finite"] = False
    result = research.readiness(selected, held, combined, production, unchanged=gate != "J")
    assert result["disposition"] != "VRC2_METHOD_CANDIDATE_READY_FOR_PROTOTYPE"
    assert not next(v for k, v in result["gates"].items() if k.startswith(gate + "_"))


def test_matrix_exactly_50_fingerprint_and_no_extra_variants():
    matrix = research.research_matrix()
    assert len(matrix["variants"]) == len({c.id for c in research.candidates()}) == 50
    assert {c.descriptor for c in research.candidates()[:48]} == {"D1", "D2", "D3", "D4"}
    assert {c.k for c in research.candidates()[:48]} == {3, 5, 9}
    before = research.demo._digest(research.demo._json_bytes(matrix))
    assert before == research.demo._digest(research.demo._json_bytes(research.research_matrix()))
    matrix["numerical_epsilon"] = 0.1
    assert before != research.demo._digest(research.demo._json_bytes(matrix))


def test_split_filter_and_observation_rejects_any_holdout_outcome(tmp_path):
    rows = scored_rows() + scored_rows(split="holdout_benign") + [identity(dataset="demo")]
    assert len(research.phase_samples(rows, "observation")) == 20
    assert len(research.phase_samples(rows, "holdout")) == 20
    assert len(research.phase_samples(rows, "demo")) == 1
    with pytest.raises(ValueError, match="cannot enter"):
        research.freeze_selection(tmp_path, rows)


def test_no_candidate_cache_read_before_selected_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "verify_freeze", lambda *_: {})
    monkeypatch.setattr(research, "check_receipt", lambda *_: None)
    (tmp_path / "freeze").mkdir()
    research.benign._seal(
        tmp_path,
        "freeze/prepared.json",
        {"baseline_receipt": {}, "design_receipt": {}, "paired_qa_receipt": {}},
    )
    monkeypatch.setattr(
        research, "load_groups", lambda *_: pytest.fail("Holdout cache read before freeze")
    )
    with pytest.raises(FileNotFoundError):
        research.evaluate_phase(tmp_path, "holdout")
    assert not (tmp_path / "holdout/run.json").exists()


@pytest.mark.parametrize(
    "path",
    [Path("relative"), research.demo.ROOT, research.demo.ROOT / "media", research.demo.ROOT.parent],
)
def test_no_repository_media_output_or_relative_workspace(path):
    with pytest.raises(ValueError):
        research.evaluate_phase(path, "observation")


def test_output_escape_and_finite_csv_json(tmp_path):
    for unsafe in ("../outside", "C:/outside", "a\\b"):
        with pytest.raises(ValueError):
            research.demo._owned_path(tmp_path, unsafe)
    target = tmp_path / "table.csv"
    research.prior.write_csv(target, [{"score": None, "state": "INSUFFICIENT", "details": [1, 2]}])
    with target.open(encoding="utf-8", newline="") as stream:
        assert list(csv.DictReader(stream))[0]["score"] == "null"
    with pytest.raises(ValueError):
        research.prior.write_csv(tmp_path / "bad.csv", [{"score": float("nan")}])
    assert not (tmp_path / "bad.csv").exists()
    with pytest.raises(ValueError):
        research.demo._json_bytes({"score": float("inf")})


def install_workflow_fixture(tmp_path, monkeypatch):
    pixels = np.random.default_rng(48).integers(0, 256, (16, 9, 16, 3), dtype=np.uint8)
    request = video_request(tmp_path, [pixels, pixels.copy()])
    groups = research.prior.groups_from_request(request)
    metrics = VideoRepeatedContentCorrespondenceAnalyzer().analyze(request).raw_metrics
    roots = [tmp_path / name for name in ("benign", "demo", "paired")]
    for path in roots:
        path.mkdir()
    media = tmp_path / "tiny.fixture"
    media.write_bytes(b"first-party fixture; decoder replaced only in this orchestration test")
    samples = []
    for n in range(1, 9):
        split = "holdout_benign" if n in {3, 6, 8} else "observation"
        for dataset, role in (
            ("benign", "BENIGN_REFERENCE"),
            ("benign", "BENIGN_PROCESSING"),
            ("paired", "reference"),
            ("paired", "repeat"),
        ):
            s = identity(dataset, f"video-{n:02}", role, split)
            s["sample_id"] = (
                f"video-{n:02}-{'reference' if role == 'BENIGN_REFERENCE' else 'processed'}"
                if dataset == "benign"
                else f"paired-video-{n:02}-{role}"
            )
            samples.append(
                {
                    **s,
                    "path": str(media),
                    "size_bytes": media.stat().st_size,
                    "sha256": research.benign._hash_file(media),
                    "accepted_production": metrics,
                }
            )
    samples.append({**samples[0], "dataset": "demo", "sample_id": "video-03-static"})
    research.validate_inventory(samples)
    monkeypatch.setattr(research, "accepted_inputs", lambda *_: (samples, {}))
    monkeypatch.setattr(research, "decode_sample", lambda *_: (groups, metrics))
    monkeypatch.setattr(research.demo, "_environment", lambda: {"fixture": True})
    monkeypatch.setattr(
        research.prior, "verify_control_pixels", lambda *_: {"copy_pixels_exact": True}
    )
    research.benign._seal(
        roots[2],
        "paired-qa.json",
        [{"source_family": f"video-{n:02}", "copy_pixels_exact": True} for n in range(1, 9)],
    )
    root = tmp_path / "research"
    research.prepare(root, *roots)
    return root, samples


def test_full_phase_order_holdout_only_selected_replay_tables_and_tampering(tmp_path, monkeypatch):
    root, samples = install_workflow_fixture(tmp_path, monkeypatch)
    selected = research.observation(root)
    assert selected["holdout_consumed"] is False
    assert not selected["observation_ready"]
    assert not (root / "holdout/run.json").exists()
    frozen = (root / "selected-candidate.json").read_bytes()
    actual_measure = research.measure
    calls = []

    def inspect(sample, groups, variants):
        calls.append((sample["split"], {c.id for c in variants}))
        return actual_measure(sample, groups, variants)

    monkeypatch.setattr(research, "measure", inspect)
    decision = research.holdout(root)
    assert all(split == "holdout_benign" for split, _ in calls)
    assert all(ids == {selected["candidate"]["id"], research.PRODUCTION} for _, ids in calls)
    assert decision["disposition"] != "VRC2_METHOD_CANDIDATE_READY_FOR_PROTOTYPE"
    summary = research.finish(root)
    assert summary["matrix_variants"] == 50 and summary["baseline_samples"] == 33
    assert (root / "selected-candidate.json").read_bytes() == frozen
    assert len(list((root / "tables").glob("*.csv"))) == 14
    assert len(research.benign._sealed(root, "observation/results.json")) == 1000
    assert len(research.benign._sealed(root, "holdout/results.json")) == 24
    with pytest.raises(ValueError, match="after selection"):
        research.observation(root)
    target = next((root / "input/groups").glob("*.npz"))
    target.write_bytes(b"corrupt")
    sample = next(s for s in samples if research.cache_name(s) == target.stem)
    with pytest.raises(ValueError, match="Evidence changed"):
        research.load_groups(root, sample)


def test_inventory_split_and_production_code_matrix_freeze_guards(tmp_path, monkeypatch):
    root, samples = install_workflow_fixture(tmp_path, monkeypatch)
    wrong = copy.deepcopy(samples)
    wrong[0]["split"] = "holdout_benign"
    with pytest.raises(ValueError, match="split"):
        research.validate_inventory(wrong)
    with pytest.raises(ValueError, match="Duplicate"):
        research.validate_inventory(samples + [samples[0]])
    research.verify_freeze(root)
    with monkeypatch.context() as patch:
        patch.setattr(research.demo, "_policy", lambda: {"changed": True})
        with pytest.raises(ValueError, match="freeze changed"):
            research.verify_freeze(root)
    with monkeypatch.context() as patch:
        patch.setattr(research, "fingerprint", lambda: {"changed": "code"})
        with pytest.raises(ValueError, match="freeze changed"):
            research.verify_freeze(root)
    (root / "research-matrix.json").write_text(json.dumps({"variants": []}))
    with pytest.raises(ValueError, match="Seal"):
        research.verify_freeze(root)
