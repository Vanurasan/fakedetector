"""Demonstration provenance, retention and arithmetic, not claims of forensic accuracy."""

import copy
import csv
import hashlib
import io
import json
import sys
import wave
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from PIL import Image

from fakedetector.domain import AnalysisResult, AnalysisStatus, AnalyzerStatus, ErrorDetail
from fakedetector.lifecycle._assessment import AnalysisAssessmentService

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts import diploma_demo_evaluation as demo


def test_frozen_membership_split_roles_and_policy():
    cases = demo.samples()
    assert cases == demo.samples()
    assert hashlib.sha256(demo._json_bytes([asdict(c) for c in cases])).hexdigest() == (
        "03633647f20bf30d81645fc6ce5592bee7824cb8106e412802178525a291726f"
    )
    assert len(cases) == len({case.sample_id for case in cases}) == 40
    assert Counter(case.media_type for case in cases) == {"image": 14, "audio": 14, "video": 12}
    assert Counter(case.split for case in cases) == {
        "calibration_observation": 28,
        "holdout_demo": 12,
    }
    assert {case.role for case in cases} == {"control", "manipulated", "confound_control"}
    assert not {"real", "authentic", "fake", "deepfake"} & {case.role for case in cases}
    for pair_id in {case.pair_id for case in cases}:
        group = [case for case in cases if case.pair_id == pair_id]
        assert len({case.seed for case in group}) == len({case.split for case in group}) == 1
        assert sum(case.role == "control" for case in group) == 1
        assert group[0].split == demo._split(pair_id)
    assert {c.pair_id for c in cases if c.split == "holdout_demo"} == {
        "image-03",
        "audio-03",
        "video-03",
    }
    policy = demo._policy()
    assert policy["capacities"] == {"image": 3.4375, "audio": 2.8125, "video": 2.05}
    assert policy["family_factors"] == [1, 0.25, 0.1, 0]
    assert policy["assessment_sha256_lf"] == demo.ASSESSMENT_SHA256
    assert len(policy["families"]) == 12
    assert sum(len(f["members"]) for f in policy["families"]) == 14


@pytest.mark.parametrize("media", ["image", "audio"])
def test_byte_determinism_and_no_duplicate_padding(media):
    encode = demo._image_bytes if media == "image" else demo._audio_bytes
    digests = []
    for case in demo.samples():
        if case.media_type != media:
            continue
        frozen_parameters = copy.deepcopy(asdict(case))
        first, second = encode(case), encode(case)
        assert asdict(case) == frozen_parameters
        assert first == second
        digests.append(hashlib.sha256(first).hexdigest())
        if media == "image":
            with Image.open(io.BytesIO(first)) as image:
                image.load()
                assert min(image.size) >= 512
                if case.transformation == "exif_dimension_mismatch":
                    assert image.getexif()[0xA002] != image.width
        else:
            with wave.open(io.BytesIO(first)) as audio:
                assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (
                    8000,
                    1,
                    2,
                )
                assert audio.getnframes() == 65536
    assert len(set(digests)) == len(digests)


@pytest.mark.parametrize("path", [Path("relative"), demo.ROOT, demo.ROOT / "out", demo.ROOT.parent])
def test_output_safety_rejects_repository_and_implicit_paths(path):
    with pytest.raises(ValueError):
        demo.generate(path)


def test_no_default_output_and_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["demo", "generate"])
    with pytest.raises(SystemExit) as error:
        demo.main()
    assert error.value.code == 2
    (tmp_path / "keep.txt").write_text("owner content", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        demo.generate(tmp_path)
    assert (tmp_path / "keep.txt").read_text() == "owner content"
    for relative in ("../escape", "C:/escape", "nested/../../escape", "nested\\escape"):
        with pytest.raises(ValueError):
            demo._owned_path(tmp_path, relative)


def test_reject_directory_junction(tmp_path, directory_junction_factory):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    directory_junction_factory(link, target)
    with pytest.raises(ValueError, match="junction"):
        demo.generate(link / "corpus")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_outputs_rejected(value, tmp_path):
    with pytest.raises(ValueError):
        demo._json_bytes({"score": value})
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"score": value}), encoding="utf-8")
    with pytest.raises(ValueError, match="Nonfinite"):
        demo._read_json(path)


def _manifest_row(case):
    return {**asdict(case), "sha256": "a" * 64, "size_bytes": 1}


def test_missing_and_failed_rows_remain_in_inventory_and_pair_denominators():
    group = [c for c in demo.samples() if c.pair_id == "image-01"]
    rows = [demo.extract_result(_manifest_row(c), None, failure="harness_timeout") for c in group]
    summary = demo.aggregate(rows)
    assert summary["total"] == 3
    assert summary["inventory"]["analysis_status"] == {"harness_timeout": 3}
    assert len(summary["unassessed_samples"]) == 3
    assert summary["threshold_matrix"]["manipulated"]["unassessed"] == 1
    assert summary["metrics"]["demo_manipulated_rate_gt25"] == {
        "numerator": 0,
        "denominator": 1,
        "fraction": 0,
    }
    assert summary["metrics"]["assessed_pair_count"] == 0
    assert summary["metrics"]["pair_count"] == 1
    assert summary["metrics"]["pairwise_score_increase_rate"]["fraction"] is None
    assert all(p["delta_score"] is None for p in summary["pairs"])
    assert len(summary["analyzers"]) == 14
    assert sum(a["not_observed_count"] for a in summary["analyzers"]) == 15


def test_arithmetic_pair_matching_thresholds_and_split_boundaries():
    cases = [c for c in demo.samples() if c.pair_id == "audio-01"]
    rows = [demo.extract_result(_manifest_row(c), None) for c in cases]
    values = {"control": 25, "loop": 55, "spectral": 55.001, "splice": 25.001, "transient": 0}
    for row in rows:
        score = values[row["sample_id"].rsplit("-", 1)[1]]
        row["overall_score"] = score
        row["risk_level"] = "low" if score <= 25 else "medium" if score <= 55 else "high"
    summary = demo.aggregate(rows)
    assert summary["threshold_matrix"]["manipulated"] == {
        "low": 0,
        "medium": 1,
        "high": 1,
        "unassessed": 0,
    }
    assert summary["metrics"]["demo_elevated_control_rate_gt25"]["fraction"] == 1 / 3
    assert summary["metrics"]["demo_manipulated_rate_gt55"]["fraction"] == 1 / 2
    assert summary["metrics"]["pairwise_score_increase_rate"]["fraction"] == 1
    assert summary["metrics"]["median_pair_delta"] == pytest.approx(15.001)
    assert len(summary["pairs"]) == 4
    assert all(p["control_id"] == "audio-01-control" for p in summary["pairs"])
    changed = copy.deepcopy(rows)
    changed[0]["split"] = "holdout_demo"
    with pytest.raises(ValueError, match="one split"):
        demo.pair_deltas(changed)
    with pytest.raises(ValueError, match="exactly one"):
        demo.pair_deltas([r for r in rows if r["role"] != "control"])


def test_minimal_file_level_smoke_and_report(tmp_path, monkeypatch, real_worker_processes):
    # Six files only. Normal pytest never generates/evaluates the 40-file experiment.
    selected = tuple(
        c
        for c in demo.samples()
        if c.sample_id
        in {
            "image-01-control",
            "image-01-metadata",
            "audio-03-control",
            "audio-03-clip",
            "video-02-control",
            "video-02-timing",
        }
    )
    monkeypatch.setattr(demo, "samples", lambda: selected)
    root = tmp_path / "smoke"
    manifest = demo.generate(root)
    assert manifest == demo.load_manifest(root)
    config = demo._config(root)
    raw = demo._read_json(root / "freeze.json")["policy"]
    assert config.risk_assessment.model_dump(mode="json") == raw["risk_configuration"]
    demo.evaluate(root)
    summary = demo.report(root)
    assert summary["all"]["total"] == 6
    assert summary["all"]["inventory"]["analysis_status"] == {"completed": 6}
    assert summary["all"]["extraction_errors"] == {}
    assert len(real_worker_processes) >= 28
    assert summary["splits"]["holdout_demo"]["total"] == 2
    assert all(a["observed_count"] == 2 for a in summary["all"]["analyzers"])
    assert not list((root / "runtime/temp").glob("*"))
    rows = demo._read_json(root / "tables/samples.json")
    for row in rows:
        assert row["cleanup_status"] == "completed"
        contributions = [
            a["score_contribution"] for a in row["analyzers"] if a["score_contribution"] is not None
        ]
        assert sum(contributions) == pytest.approx(row["overall_score"])
        assert str(tmp_path) not in json.dumps(row)
    timing = next(r for r in rows if r["sample_id"] == "video-02-timing")
    observed = next(a for a in timing["analyzers"] if a["analyzer_id"] == "video_timing_anomaly")
    # Actual encoded MP4 -> intake -> dense PTS, not an injected analyzer structure.
    assert observed["normalized_response"] == pytest.approx(5 / 7)
    for filename, count in (
        ("score-by-sample.csv", 6),
        ("family-responses.csv", 24),
        ("analyzer-responses.csv", 28),
        ("pair-deltas.csv", 3),
    ):
        with (root / "tables" / filename).open(encoding="utf-8-sig", newline="") as stream:
            assert len(list(csv.DictReader(stream))) == count
    assert demo.report(root) == summary
    markdown = (root / "tables/report.md").read_text(encoding="utf-8")
    assert "calibration_observation" in markdown and "holdout_demo" in markdown
    assert "Elevated control responses" in markdown
    assert "Missed/weak controlled transformations" in markdown

    # Extraction retains PARTIAL and explicit analyzer failures without changing public objects.
    payload = demo._read_json(root / "results/audio-03-clip.json")
    result = AnalysisResult.model_validate(payload)
    sample = next(row for row in manifest["samples"] if row["sample_id"] == "audio-03-clip")
    for status in (AnalyzerStatus.ERROR, AnalyzerStatus.TIMEOUT):
        failed = result.analyzers[1].model_copy(
            update={
                "status": status,
                "errors": [
                    ErrorDetail(
                        code=f"analyzer_{status.value}",
                        category="analyzer",
                        message="Controlled test failure",
                        retryable=True,
                        analyzer_id=result.analyzers[1].analyzer_id,
                    )
                ],
            }
        )
        analyzers = [result.analyzers[0], failed, *result.analyzers[2:]]
        completeness, risk, recommendation = AnalysisAssessmentService(
            config.risk_assessment
        ).assess(
            [a.analyzer_id for a in analyzers],
            analyzers,
            result.findings,
        )
        partial = AnalysisResult.model_validate(
            {
                **result.model_dump(mode="python"),
                "status": AnalysisStatus.PARTIAL,
                "analyzers": analyzers,
                "completeness": completeness,
                "risk_assessment": risk,
                "recommendation": recommendation,
            }
        )
        extracted = demo.extract_result(sample, partial)
        assert extracted["analysis_status"] == extracted["completeness_status"] == "partial"
        assert extracted["overall_score"] is not None
        assert not extracted["extraction_errors"]
        observation = next(
            a for a in extracted["analyzers"] if a["analyzer_id"] == failed.analyzer_id
        )
        assert observation["response_state"] == status.value
        assert observation["normalized_response"] is None
        assert observation["errors"] == [f"analyzer_{status.value}"]
    invalid = result.analyzers[1].model_copy(update={"raw_metrics": {"profile": "wrong"}})
    corrupted = result.model_copy(
        update={"analyzers": [result.analyzers[0], invalid, *result.analyzers[2:]]}
    )
    assert demo.extract_result(sample, corrupted)["extraction_errors"]

    # Frozen membership, media, result and output-path tampering are rejected.
    path = root / manifest["samples"][0]["filename"]
    original = path.read_bytes()
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        demo.load_manifest(root)
    path.write_bytes(original)
    altered = tuple(replace(c, split="changed") for c in selected)
    monkeypatch.setattr(demo, "samples", lambda: altered)
    with pytest.raises(ValueError, match="membership"):
        demo.load_manifest(root)


def test_result_journal_absence_does_not_drop_generated_samples(tmp_path, monkeypatch):
    selected = tuple(c for c in demo.samples() if c.pair_id == "image-01")
    monkeypatch.setattr(demo, "samples", lambda: selected)
    root = tmp_path / "not-evaluated"
    demo.generate(root)
    summary = demo.report(root)
    assert summary["all"]["inventory"]["analysis_status"] == {"not_evaluated": 3}
    assert len(summary["all"]["unassessed_samples"]) == 3
