"""Final holdout freeze, leakage and exact source-level accounting, without media."""

import hashlib
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts.research import jpeg_dq_holdout as holdout


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


@pytest.fixture
def manifest(tmp_path):
    def asset(value):
        return {"path": tmp_path / str(value), "sha256": digest(value)}

    sources = []
    for index in range(500):
        sources.append(
            {
                "identity": {
                    "source_group": f"g{index}",
                    "scene_group": f"s{index}",
                    "source_url": f"https://example.org/{index}",
                    "original_sha256": digest(index),
                    "master_sha256": digest(f"master{index}"),
                },
                "split": "final_holdout",
                "original": asset(index),
                "master": asset(f"master{index}"),
                "endpoint": asset(f"endpoint{index}"),
                "terms": asset("terms"),
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "rights_reviewed": True,
                "format": "RAW",
                "device": "fixture",
                "content": "fixture",
            }
        )
    return holdout.HoldoutManifest(
        sources=sources,
        excluded=[
            {
                "source_group": "prior",
                "scene_group": "prior_scene",
                "source_url": "https://example.org/prior",
                "original_sha256": digest("prior"),
                "master_sha256": digest("prior_master"),
            }
        ],
        acquisition_protocol=asset("protocol"),
        exclusion_evidence=asset("exclusions"),
        implementation_evidence=asset("code"),
        repo_sha="c" * 40,
    )


@pytest.mark.parametrize("split", ["pilot_exploration", "calibration", "validation", "holdout"])
def test_only_final_holdout_split(manifest, split):
    data = manifest.model_dump()
    data["sources"][0]["split"] = split
    with pytest.raises(ValidationError):
        holdout.HoldoutManifest.model_validate(data)


@pytest.mark.parametrize(
    "key", ["source_group", "scene_group", "source_url", "original_sha256", "master_sha256"]
)
def test_prior_and_within_holdout_overlap(manifest, key):
    for identity in (manifest.excluded[0], manifest.sources[1].identity):
        data = manifest.model_dump()
        first = data["sources"][0]
        first["identity"][key] = getattr(identity, key)
        if key in ("original_sha256", "master_sha256"):
            first[key.removesuffix("_sha256")]["sha256"] = getattr(identity, key)
        with pytest.raises(ValidationError, match="overlap"):
            holdout.HoldoutManifest.model_validate(data)


def test_manifest_size_hash_and_exclusive_freeze(manifest, tmp_path):
    path = tmp_path / "holdout.json"
    expected = holdout.freeze_manifest(manifest, path)
    assert expected == hashlib.sha256(path.read_bytes()).hexdigest()
    assert holdout.load_manifest(path, expected) == manifest
    with pytest.raises(FileExistsError):
        holdout.freeze_manifest(manifest, path)
    data = manifest.model_dump()
    data["sources"] = []
    with pytest.raises(ValidationError):
        holdout.HoldoutManifest.model_validate(data)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash mismatch"):
        holdout.load_manifest(path, expected)


def outcomes(positives=0, applicable=500, failures=0, invalid=0):
    return [
        holdout.Outcome(
            source_group=f"g{i}",
            status=(
                "applicable_negative"
                if i < applicable
                else "admission_failure"
                if i < applicable + failures
                else "protocol_invalid"
                if i < applicable + failures + invalid
                else "insufficient_evidence"
            ),
            positive=i < positives if i < applicable else None,
        )
        for i in range(500)
    ]


@pytest.mark.parametrize(
    "positives,applicable,expected",
    [
        (0, 500, "PASS"),
        (1, 500, "PASS"),
        (2, 500, "FAIL"),
        (0, 299, "PASS"),
        (0, 298, "FAIL"),
        (1, 473, "PASS"),
        (1, 472, "FAIL"),
        (0, 0, "FAIL"),
    ],
)
def test_exact_actual_n_and_deterministic_aggregation(manifest, positives, applicable, expected):
    rows = outcomes(positives, applicable)
    result = holdout.aggregate(manifest, rows)
    assert result == holdout.aggregate(manifest, reversed(rows))
    assert result["result"] == "FINAL_HOLDOUT_" + expected
    assert result["applicable"] == applicable
    assert result["abstentions"] == 500 - applicable
    assert result["upper_95"] == holdout.exact_upper(positives, applicable)


def test_failure_and_invalid_not_true_negatives(manifest):
    result = holdout.aggregate(manifest, outcomes(1, 470, failures=20))
    assert result["admitted"] == 480
    assert result["admission_failures"] == 20
    assert result["abstentions"] == 10
    assert result["fpr"] == 1 / 470
    assert result["result"] == "FINAL_HOLDOUT_FAIL"
    assert holdout.aggregate(manifest, outcomes(0, 499, invalid=1))["result"] == (
        "FINAL_HOLDOUT_INVALID"
    )
    with pytest.raises(ValidationError, match="boolean"):
        holdout.Outcome(source_group="g", status="insufficient_evidence", positive=False)


def test_no_replacement_missing_or_duplicate_endpoints(manifest):
    rows = outcomes()
    for changed in (
        rows[:-1],
        rows + rows[:1],
        rows[:-1]
        + [
            holdout.Outcome(
                source_group="replacement", status="applicable_negative", positive=False
            )
        ],
    ):
        with pytest.raises(ValueError, match="frozen membership"):
            holdout.aggregate(manifest, changed)


@pytest.mark.parametrize("n,expected", [(298, "FAIL"), (299, "PASS")])
def test_owner_approved_smaller_frozen_size(manifest, n, expected):
    data = manifest.model_dump()
    data["sources"] = data["sources"][:n]
    smaller = holdout.HoldoutManifest.model_validate(data)
    report = holdout.aggregate(smaller, outcomes()[:n])
    assert report["assigned"] == report["applicable"] == n
    assert report["result"] == "FINAL_HOLDOUT_" + expected


@pytest.mark.parametrize("ordinal", [0, 1, 2, 5, 10])
def test_single_endpoint_matches_frozen_r3c_generator(manifest, tmp_path, ordinal):
    from scripts.research.jpeg_dq_corpus import generate
    from scripts.research.jpeg_dq_rule import CalibrationSource

    master = tmp_path / "master.png"
    Image.new("RGB", (80, 80), (100, 80, 120)).save(master)
    asset = holdout.Asset(path=master, sha256=hashlib.sha256(master.read_bytes()).hexdigest())
    source = CalibrationSource(
        source_group="fixture",
        scene_group="fixture",
        partition="calibration",
        pilot=False,
        source_url="https://example.org/fixture",
        device="fixture",
        content="fixture",
        original=asset,
        master=asset,
        terms=asset,
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_reviewed=True,
    )
    reference = generate(source, tmp_path / "r3c", ordinal)[0]
    path = tmp_path / "single.jpg"
    case = holdout.generate_endpoint(asset, "fixture", "fixture", ordinal, path)
    assert path.read_bytes() == Path(reference["path"]).read_bytes()
    assert case.partition == "final_holdout"
    assert case.sha256 == reference["case"]["sha256"]
    assert case.final_tables == reference["case"]["final_tables"]
    with pytest.raises(FileExistsError):
        holdout.generate_endpoint(asset, "fixture", "fixture", ordinal, path)


def test_rule_hash_checked_before_opening(manifest, tmp_path):
    path = tmp_path / "holdout.json"
    expected = holdout.freeze_manifest(manifest, path)
    rule_path = tmp_path / "wrong_rule.json"
    rule_path.write_text("{}")
    with pytest.raises(ValueError, match="rule hash mismatch"):
        holdout.open_once(path, expected, rule_path)
    assert not path.with_suffix(".opened.json").exists()


def test_open_once_checks_inputs_and_keeps_lock(manifest, tmp_path, monkeypatch):
    path = tmp_path / "holdout.json"
    expected = holdout.freeze_manifest(manifest, path)
    sentinel = object()
    monkeypatch.setattr(holdout, "load_frozen", lambda *args: sentinel)
    with pytest.raises(FileNotFoundError):
        holdout.open_once(path, expected, tmp_path / "rule.json")
    assert not path.with_suffix(".opened.json").exists()
    verified = []
    monkeypatch.setattr(holdout.Asset, "verify", lambda self: verified.append(self.sha256))
    assert holdout.open_once(path, expected, tmp_path / "rule.json") == (manifest, sentinel)
    assert len(verified) == 2003
    with pytest.raises(FileExistsError):
        holdout.open_once(path, expected, tmp_path / "rule.json")
