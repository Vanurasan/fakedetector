"""Small first-party fixtures; the external research corpus is never read by pytest."""

import copy
import csv
import json
import subprocess
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
    from scripts import diploma_vrc_targeted_research as research


def group(region=0, start=0, ticks=None, value=0, base=Fraction(1, 1000)):
    return research.Group(
        0,
        region,
        start,
        ticks or tuple(range(start * 100, start * 100 + 400, 100)),
        base,
        (16, 9, 9, 16, 3),
        np.full((4, 432), value, dtype=np.int64),
    )


def pair(a=0, b=5, color=0, delta=0):
    return research.Pair(group(start=a), group(start=b), color, delta, 0, 0)


@pytest.mark.parametrize("count", [3, 4, 8, 9, 20, 32])
def test_exact_baseline_production_reproduction(tmp_path, count):
    rng = np.random.default_rng(63)
    frames = rng.integers(0, 256, size=(count, 19, 33, 3), dtype=np.uint8)
    request = video_request(tmp_path, [frames, frames.copy()])
    pairs = research.enumerate_pairs(research.groups_from_request(request))
    metrics = VideoRepeatedContentCorrespondenceAnalyzer().analyze(request).raw_metrics
    assert research.verify_reproduction(pairs, metrics) == 0
    assert research.retained_response(pairs)[0] == _video_repetition_response(metrics)
    if pairs:
        wrong = copy.deepcopy(metrics)
        wrong["minimum_color_pair"]["color_numerator"] += 1
        with pytest.raises(ValueError, match="reproduction mismatch"):
            research.verify_reproduction(pairs, wrong)


def test_current_ordinal_rule_and_strict_real_pts():
    a = group()
    assert not research.enumerate_pairs([a, group(start=4)])
    assert len(research.enumerate_pairs([a, group(start=5)])) == 1
    assert not research.enumerate_pairs([a, group(region=1, ticks=(300, 400, 500, 600))])
    assert not research.enumerate_pairs([a, replace(group(start=5), stream=1)])
    assert not research.enumerate_pairs([a, replace(group(start=5), geometry=(20, 9, 9, 16, 3))])
    assert research.enumerate_pairs([group(start=5), a])[0].a.key == a.key


@pytest.mark.parametrize("gap", [Fraction(499, 1000), Fraction(1, 2), Fraction(1), Fraction(2)])
def test_temporal_gates_use_real_pts_not_frame_ordinals(gap):
    a = group(ticks=(-900, -780, -610, -300))
    start_tick = -300 + int(gap * 1000)
    b = group(region=1, ticks=tuple(start_tick + n * 13 for n in range(4)))
    item = research.enumerate_pairs([a, b])[0]
    assert item.gap == gap
    assert research.eligible(item, research.GATES[0])
    assert research.eligible(item, research.GATES[1]) == (gap >= Fraction(1, 2))
    assert research.eligible(item, research.GATES[2]) == (gap >= 1)
    assert research.eligible(item, research.GATES[3]) == (gap >= 2)
    assert research.eligible(item, research.GATES[4])


def test_different_time_bases_and_unknown_pts(tmp_path):
    a = group(ticks=(0, 1, 2, 3), base=Fraction(1, 10))
    b = group(region=1, ticks=(8, 9, 10, 11), base=Fraction(1, 10))
    assert research.eligible(research.enumerate_pairs([a, b])[0], research.GATES[1])
    b = replace(b, base=Fraction(1, 20))
    assert not research.eligible(research.enumerate_pairs([a, b])[0], research.GATES[1])
    frames = np.zeros((9, 9, 16, 3), dtype=np.uint8)
    request = video_request(tmp_path, [frames], masks=[[5, 5, 5, 4, 5, 5, 5, 5, 5]])
    assert [g.start for g in research.groups_from_request(request)] == [4, 5]


def test_distance_integer_oracles_and_joint_retention_loss():
    a, b = group(), group(start=5, value=255)
    p = research.enumerate_pairs([a, b])[0]
    assert (p.color, p.delta, p.distance, p.similarity) == (440640, 0, 1, 0)
    a.values[1::2] = 255
    b.values[1::2] = 0
    p = research.enumerate_pairs([a, b])[0]
    assert (p.color, p.delta) == (440640, 660960)
    pairs = [
        pair(color=0, delta=660960),
        pair(color=440640, delta=0),
        pair(color=220320, delta=330480),
    ]
    assert research.retained_response(pairs)[0] == 0
    assert research.pooling(pairs)["strongest"] == 0.5
    frame = np.zeros((9, 32, 3), dtype=np.uint8)
    frame[:, 1::2] = 1
    assert (_block_descriptor(frame) == 1).all()


def test_quantiles_top_k_constant_and_short_sets():
    assert research.quantile([], 0.99) is None
    assert research.quantile([0, 10, 20, 30], 0.25) == 7.5
    assert research.quantile([8], 0.95) == 8
    assert research.quantile([2, 2, 2], 0.01) == 2
    for values, p in (([float("nan")], 0.5), ([1], float("inf")), ([1], 1.1)):
        with pytest.raises(ValueError):
            research.quantile(values, p)
    empty = research.pooling([])
    assert empty["eligible_pairs"] == empty["disjoint_support"] == 0
    assert all(empty[key] is None for key in research.POOLS)
    short = research.pooling([pair(color=44064), pair(color=88128)])
    assert short["strongest"] == 0.9
    assert short["second"] == 0.8
    assert short["third"] is short["fifth"] is short["top3_mean"] is None
    constant = research.pooling([pair(n, n + 20) for n in range(5)])
    assert all(constant[key] == 1 for key in research.POOLS)


def test_greedy_group_identity_not_frame_overlap_and_stable_ties():
    candidates = [pair(0, 5), pair(0, 8), pair(1, 6), pair(5, 9), pair(2, 7)]
    selected = research.greedy_disjoint(candidates)
    assert [(p.a.start, p.b.start) for p in selected] == [(0, 5), (1, 6), (2, 7)]
    assert research.pooling([pair(0, 5), pair(0, 8)])["disjoint_support"] == 1


def test_source_family_selection_and_matched_isolation():
    samples = [
        {"dataset": "benign", "role": "BENIGN_REFERENCE", "source_family": "video-02"},
        {"dataset": "benign", "role": "BENIGN_REFERENCE", "source_family": "video-01"},
        {"dataset": "demo", "role": "BENIGN_REFERENCE", "source_family": "video-01"},
    ]
    assert [r["source_family"] for r in research.paired_sources(samples)] == [
        "video-01",
        "video-02",
    ]
    with pytest.raises(ValueError, match="one benign reference"):
        research.paired_sources(samples + [samples[0]])
    rows = []
    for gate in research.GATES:
        for role, value in (("reference", 0.5), ("repeat", 0.75)):
            rows.append(
                dict(
                    dataset="paired",
                    gate=gate,
                    source_family="video-01",
                    role=role,
                    sample_id=role,
                    split="holdout_benign",
                    disjoint_support=3,
                    **dict.fromkeys(research.POOLS, value),
                )
            )
    deltas = research.paired_deltas(rows)
    assert len(deltas) == 50
    assert all(r["delta"] == 0.25 and r["supported"] for r in deltas)
    with pytest.raises(ValueError, match="isolation"):
        research.paired_deltas(rows + [rows[0]])
    rows[0]["split"] = "observation"
    with pytest.raises(ValueError, match="split"):
        research.paired_deltas(rows)


def test_matrix_seal_and_production_freeze_guard(tmp_path, monkeypatch):
    root = tmp_path / "external"
    root.mkdir()
    matrix = research.research_matrix()
    assert len(matrix["variants"]) == 50
    research.benign._seal(root, "research-matrix.json", matrix)
    assert research.verify_matrix(root) == matrix
    policy = research.demo._policy()
    monkeypatch.setattr(research.demo, "_environment", lambda: {})
    research.benign._seal(
        root,
        "freeze.json",
        {
            "policy": policy,
            "environment": {},
            "matrix_sha256": research.benign._hash_file(root / "research-matrix.json"),
            "source_manifests": {},
        },
    )
    research.verify_freeze(root)
    monkeypatch.setattr(research.demo, "_policy", lambda: {**policy, "model": "changed"})
    with pytest.raises(ValueError, match="freeze changed"):
        research.verify_freeze(root)
    changed = copy.deepcopy(matrix)
    changed["gates"].pop()
    assert research.demo._digest(research.demo._json_bytes(changed)) != research.demo._digest(
        research.demo._json_bytes(matrix)
    )
    (root / "research-matrix.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="Seal"):
        research.verify_matrix(root)


def test_deterministic_nested_extrema_and_finite_outputs(tmp_path):
    pairs = [pair(n, n + 20, color=n * 1000) for n in range(20)]
    rows = research.subset_diagnostics("synthetic", research.GATES[0], pairs)
    assert rows == research.subset_diagnostics("synthetic", research.GATES[0], pairs)
    for replicate in range(16):
        values = [r["strongest"] for r in rows if r["replicate"] == replicate]
        assert values == sorted(values)
    finite = [{"zero": 0, "missing": None, "nested": [0, 1]}]
    for name in ("a.csv", "b.csv"):
        research.write_csv(tmp_path / name, finite)
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()
    with (tmp_path / "a.csv").open(encoding="utf-8", newline="") as stream:
        assert next(csv.DictReader(stream))["missing"] == "null"
    for value in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError):
            research.write_csv(tmp_path / "bad.csv", [{"bad": [value]}])
        with pytest.raises(ValueError):
            research.demo._json_bytes({"bad": value})


@pytest.mark.parametrize(
    "destination", [research.demo.ROOT, research.demo.ROOT / "media", research.demo.ROOT.parent]
)
def test_no_media_in_repo_and_output_path_safety(destination):
    with pytest.raises(ValueError, match="outside"):
        research.prepare(destination, destination / "benign", destination / "demo")
    with pytest.raises(ValueError, match="outside"):
        research.evaluate(destination)
    with pytest.raises(ValueError, match="outside"):
        research.write_csv(destination / "unwanted.csv", [])


def test_relative_paths_and_symlink_escape(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        research.evaluate(type(tmp_path)("relative"))
    for name in ("../escape.csv", "C:/escape.csv", "a\\escape.csv"):
        with pytest.raises(ValueError, match="Unsafe"):
            research.demo._owned_path(tmp_path, name)


def test_real_dense_preprocessing_matched_repeat_and_no_production_mutation(tmp_path):
    root = tmp_path / "external"
    root.mkdir()
    (root / "artifacts").mkdir()
    source = root / "source.mp4"
    before = research.demo._policy()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=96x54:rate=24:duration=12",
            "-an",
            "-c:v",
            "mpeg4",
            "-q:v",
            "2",
            "-g",
            "1",
            "-threads",
            "1",
            "-flags:v",
            "+bitexact",
            "-pix_fmt",
            "yuv420p",
            "-video_track_timescale",
            "24000",
            str(source),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    samples = []
    for role in ("reference", "repeat"):
        path = root / f"{role}.mp4"
        command = research.paired_command(str(source), str(path), repeat=role == "repeat")
        subprocess.run(command, capture_output=True, check=True, timeout=30)
        second = root / f"{role}-second.mp4"
        subprocess.run([*command[:-1], str(second)], capture_output=True, check=True, timeout=30)
        assert path.read_bytes() == second.read_bytes()
        assert research.probe_pts(path) == list(range(0, 288000, 1000))
        facts = {
            "extension": "mp4",
            "declared_mime_type": "video/mp4",
            "detected_mime_type": "video/mp4",
            "media_type": "video",
            "size_bytes": path.stat().st_size,
            "sha256": research.benign._hash_file(path),
            "signature_match": True,
            "safe_read": True,
            "technical_parameters": {
                "duration_seconds": 12,
                "container": "mp4",
                "video_codec": "mpeg4",
                "width": 96,
                "height": 54,
                "fps": 24,
                "has_audio": False,
            },
        }
        samples.append({"path": str(path), "facts": facts, "sha256": facts["sha256"]})
    assert research.verify_control_pixels(*samples, root)["distinct_source_frames"] > 1
    pairs, metrics = research.sample_pairs(samples[1], root)
    assert metrics["eligible_pairs"] == 3423
    assert research.retained_response(pairs)[0] == 1
    distant = [p for p in pairs if research.eligible(p, research.GATES[4])]
    assert research.pooling(distant)["strongest"] == 1
    assert research.demo._policy() == before
    assert not list((root / "artifacts").iterdir())


def test_readiness_does_not_promote_saturated_positive_pairs():
    rows = []
    baselines = {}
    for index in range(8):
        family = f"family-{index}"
        for gate in research.GATES:
            for role, dataset, value in (
                ("a", "benign", 0.98),
                ("b", "benign", 0.98),
                ("reference", "paired", 0.98),
                ("repeat", "paired", 1.0),
            ):
                sid = f"{family}-{role}"
                rows.append(
                    dict(
                        dataset=dataset,
                        source_family=family,
                        gate=gate,
                        role=role,
                        sample_id=sid,
                        split="observation",
                        disjoint_support=3,
                        **dict.fromkeys(research.POOLS, value),
                    )
                )
                if dataset == "benign":
                    baselines[sid] = 0.99
    variants = research.variant_summaries(rows, research.paired_deltas(rows), baselines)
    assert all(v["positive"] == 8 and not v["ready_for_prototype"] for v in variants)
