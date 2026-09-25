"""R3C research protocol arithmetic and partition boundaries, no external media."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts.research.jpeg_dq_corpus import generate
    from scripts.research.jpeg_dq_rule import (
        CalibrationSource,
        Rule,
        Split,
        canonical_bytes,
        classify,
        endpoint_report,
        exact_upper,
        freeze,
        load_frozen,
        score,
        select_candidate,
    )
    from scripts.research.jpeg_measurements import MODES, DQMeasurement, HistogramMeasurement


def measurements(values=(0.1, 0.2, 0.3, 0.4, 0.5), **support):
    fields = {"n": 1024, "span": 20, "occupied": 8, "zero_fraction": 0.75, "state": "measured"}
    fields.update(support)
    return tuple(
        DQMeasurement(7, u, v, 1, 0, HistogramMeasurement(**fields, empty_fraction=x, amplitude=x))
        for (u, v), x in zip(MODES, values, strict=False)
    )


def rule(**updates):
    fields = {
        "metric": "empty_fraction",
        "threshold": 0.3,
        "calibration_manifest_sha256": "a" * 64,
        "implementation_sha256": "b" * 64,
        "repo_sha": "c" * 40,
        "created_at": datetime(2026, 9, 24, tzinfo=UTC),
    }
    fields.update(updates)
    return Rule(**fields)


def test_median_boundary_and_determinism():
    rows = measurements()
    assert score(rows, "empty_fraction") == 0.3
    assert classify(rows, rule()) is False
    assert classify(rows, rule(threshold=0.299999999)) is True
    assert classify(rows, rule(threshold=0.300000001)) is False
    assert [classify(rows, rule()) for _ in range(10)] == [False] * 10
    assert score(measurements((0.1, 0.2, 0.3, 0.5, 0.7, 0.9)), "amplitude") == 0.4


@pytest.mark.parametrize(
    "support",
    [
        {"n": 1023},
        {"zero_fraction": 769 / 1024},
        {"occupied": 7},
        {"span": 15},
        {"state": "constant"},
        {"state": "histogram_limit"},
        {"state": "no_full_blocks"},
    ],
)
def test_support_abstention(support):
    assert classify(measurements(**support), rule()) is None


def test_modes_and_component_do_not_supply_extra_votes():
    rows = measurements()
    chroma = tuple(replace(r, component=1) for r in measurements((1,) * 9))
    assert score(rows + chroma, "empty_fraction") == 0.3
    assert score(rows[:4] + chroma, "empty_fraction") is None
    assert score((), "empty_fraction") is None
    with pytest.raises(ValueError, match="duplicate"):
        score(rows + rows[:1], "amplitude")


def test_source_level_counts():
    result = endpoint_report([("a", True), ("b", False), ("c", None)])
    assert result["source_groups"] == 3
    assert result["applicable"] == 2
    assert result["positive"] == 1
    assert result["rate"] == 0.5
    assert result["abstention_rate"] == 1 / 3
    with pytest.raises(ValueError, match="independent"):
        endpoint_report([("a", True), ("a", False)])
    assert endpoint_report([("a", None)])["upper_95"] is None


@pytest.mark.parametrize(
    "n,errors,expected",
    [(500, 0, 0.005974), (500, 1, 0.009452), (500, 2, 0.012538), (100, 0, 0.029513)],
)
def test_exact_upper_reference_values(n, errors, expected):
    assert exact_upper(errors, n) == pytest.approx(expected, abs=0.000001)


def test_exact_upper_boundaries():
    assert exact_upper(0, 0) is None
    assert exact_upper(1, 1) == 1
    assert exact_upper(0, 1) == 0.95
    with pytest.raises(ValueError):
        exact_upper(2, 1)


def test_freeze_roundtrip_and_tampering(tmp_path):
    path = tmp_path / "rule.json"
    r = rule()
    digest = freeze(r, path)
    assert digest == hashlib.sha256(canonical_bytes(r)).hexdigest()
    assert load_frozen(path, digest) == r
    with pytest.raises(FileExistsError):
        freeze(rule(threshold=0.5), path)
    data = json.loads(path.read_bytes())
    data["threshold"] = 0.4
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash"):
        load_frozen(path, digest)


def split_source(tmp_path, index, partition):
    asset = {"path": tmp_path / str(index), "sha256": str(index) * 64}
    return {
        "source_group": f"g{index}",
        "scene_group": f"s{index}",
        "partition": partition,
        "pilot": False,
        "source_url": f"https://example.org/{index}",
        "device": "fixture",
        "content": "fixture",
        "original": asset,
        "master": asset,
        "terms": asset,
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "rights_reviewed": True,
    }


@pytest.mark.parametrize("key", ["source_group", "scene_group", "source_url", "original", "master"])
def test_partition_leakage(tmp_path, key):
    a = split_source(tmp_path, 1, "calibration")
    b = split_source(tmp_path, 2, "validation")
    assert len(Split(sources=(a, b), pilot_groups=()).sources) == 2
    b[key] = a[key]
    with pytest.raises(ValidationError):
        Split(sources=(a, b), pilot_groups=())


def test_pilot_and_holdout_excluded(tmp_path):
    source = split_source(tmp_path, 1, "validation")
    with pytest.raises(ValidationError, match="pilot"):
        Split(sources=(source,), pilot_groups=("g1",))
    source["pilot"] = True
    with pytest.raises(ValidationError, match="pilot"):
        Split(sources=(source,), pilot_groups=())
    source.update(pilot=False, partition="holdout")
    with pytest.raises(ValidationError):
        Split(sources=(source,), pilot_groups=())


def test_selection_uses_only_calibration_and_predeclared_tie():
    rows = [
        ("calibration", "g", "single", measurements()),
        ("calibration", "g", "aligned40to90", measurements((0.9,) * 9)),
    ]
    metric, threshold, candidates = select_candidate(rows)
    assert metric == "empty_fraction"
    assert threshold == 0.3
    assert candidates[metric]["aligned_unconditional_sensitivity"] == 1
    with pytest.raises(ValueError, match="validation"):
        select_candidate([("validation", *rows[0][1:])])
    with pytest.raises(ValueError, match="duplicate"):
        select_candidate(rows + rows[:1])


def test_controlled_histories_deterministic_and_grayscale(tmp_path):
    master = tmp_path / "master.png"
    Image.new("RGB", (80, 80), (100, 80, 120)).save(master)
    source = split_source(tmp_path, 1, "calibration")
    asset = {"path": master, "sha256": hashlib.sha256(master.read_bytes()).hexdigest()}
    source.update(original=asset, master=asset, terms=asset)
    source = CalibrationSource.model_validate(source)
    rows = generate(source, tmp_path / "corpus", 0)
    assert rows == generate(source, tmp_path / "corpus", 0)
    assert len(rows) == 7
    by_name = {r["case"]["variant"]: r for r in rows}
    assert all(r["case"]["mode"] == "L" for r in rows)
    same = by_name["same75"]["case"]
    assert same["first_tables"] == same["final_tables"]
    assert by_name["aligned40to90"]["case"]["first_quality"] == 40
    assert by_name["aligned90to40"]["case"]["first_quality"] == 90
    assert len(by_name["repeat"]["chain"]) == 5  # grayscale, four JPEG encodes
