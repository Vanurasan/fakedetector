"""Local fixtures only; no external download or full benign corpus in pytest."""

import copy
import csv
import io
import subprocess
import sys
import wave
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts import diploma_benign_validation as benign


def source(spec):
    return {
        **asdict(spec),
        "source_family": spec.source_id,
        "split": spec.split,
        "media_type": spec.source_id.split("-")[0],
        "source_page_url": "https://commons.wikimedia.org/wiki/File:Fixture",
        "page_revision": 1,
        "direct_media_url": "https://upload.wikimedia.org/fixture",
        "creator": "Local test fixture",
        "license_name": "CC0",
        "license_url": benign.LICENSES["CC0"],
        "source_description": "First-party pytest fixture",
        "source_credit": "Generated locally; not external research evidence",
        "original_size_bytes": 100,
        "source_duration_seconds": 12,
        "original_filename": f"sources/{spec.source_id}{Path(spec.title).suffix}",
        "source_start_seconds": 0,
        "source_end_seconds": 12,
        "api_url": "https://commons.wikimedia.org/w/api.php",
        "license_snapshot": f"licenses/{spec.source_id}.json",
        "page_snapshot": f"licenses/{spec.source_id}.html",
        "license_checked_at": "2026-10-13T00:00:00+00:00",
        "license_sha256": "0" * 64,
        "page_sha256": "0" * 64,
    }


def records():
    return [source(s) for s in benign.SOURCES]


def acquired_records():
    return [
        {**r, "original_sha256": "a" * 64, "retrieved_at": "2026-10-13T00:00:00+00:00"}
        for r in records()
    ]


def test_source_schema_roles_and_source_family_split_isolation():
    rows = records()
    benign.validate_sources(rows)
    benign.validate_sources(acquired_records(), acquired=True)
    design = benign.sample_design(acquired_records())
    assert len(design) == len({r["sample_id"] for r in design}) == 32
    assert sum(r["split"] == "holdout_benign" for r in design) == 12
    assert sum(r["role"] == "BENIGN_CONFOUND" for r in design) == 4
    assert sum(r["role"] == "BENIGN_REFERENCE" for r in design) == 16
    assert {r["role"] for r in design} == set(benign.ROLES)
    for family in {r["source_family"] for r in design}:
        group = [r for r in design if r["source_family"] == family]
        assert len(group) == 2
        assert len({r["split"] for r in group}) == 1
    assert design == benign.sample_design(acquired_records())
    assert design[0]["sample_id"] == "audio-01-reference"
    assert design[0]["filename"] == "corpus/audio-01-reference.wav"
    assert design[-1]["filename"] == "corpus/video-08-processed.mp4"


@pytest.mark.parametrize(
    "key,value",
    [
        ("split", "holdout_benign"),
        ("source_family", "other"),
        ("license_name", "CC BY-NC 4.0"),
        ("license_url", "https://example.org/free"),
        ("creator", ""),
        ("original_filename", "../escape.wav"),
        ("original_size_bytes", benign.MAX_SOURCE_BYTES + 1),
        ("source_end_seconds", 99),
    ],
)
def test_invalid_source_declaration_rejected(key, value):
    rows = records()
    rows[0][key] = value
    with pytest.raises(ValueError):
        benign.validate_sources(rows)


def test_license_allowlist_and_required_schema():
    for name, url in benign.LICENSES.items():
        assert benign._license(name, url) == url
    assert (
        benign._license("CC0", "http://creativecommons.org/publicdomain/zero/1.0/deed.en")
        == benign.LICENSES["CC0"]
    )
    for name in ("royalty free", "CC BY-NC 4.0", "CC BY-ND 3.0", "Free Art License", "CC BY 2.0"):
        with pytest.raises(ValueError):
            benign._license(name, "https://creativecommons.org/licenses/by/4.0/")
    rows = records()
    rows.pop()
    with pytest.raises(ValueError, match="membership"):
        benign.validate_sources(rows)
    rows = acquired_records()
    rows[0]["original_sha256"] = "not a digest"
    with pytest.raises(ValueError, match="SHA-256"):
        benign.validate_sources(rows, acquired=True)


@pytest.mark.parametrize(
    "path",
    [Path("relative"), benign.demo.ROOT, benign.demo.ROOT / "media", benign.demo.ROOT.parent],
)
def test_output_safety_all_entry_points(path):
    for command in (benign.declare, benign.acquire, benign.prepare, benign.evaluate, benign.report):
        with pytest.raises(ValueError):
            command(path)


def test_output_artifact_escape_and_exclusive_evidence(tmp_path):
    for relative in ("../escape", "C:/escape", "a\\b", "/absolute"):
        with pytest.raises(ValueError):
            benign.demo._owned_path(tmp_path, relative)
    benign._seal(tmp_path, "evidence.json", {"value": 1})
    with pytest.raises(FileExistsError):
        benign._seal(tmp_path, "evidence.json", {"value": 2})
    assert benign._sealed(tmp_path, "evidence.json") == {"value": 1}
    (tmp_path / "evidence.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Seal"):
        benign._sealed(tmp_path, "evidence.json")


def test_hash_verification_and_streaming_download_bounds(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        headers = {}

        def geturl(self):
            return "https://upload.wikimedia.org/fixture"

    class Opener:
        payload = b"12345"
        headers = {}

        def open(self, request, timeout):
            response = Response(self.payload)
            response.headers = self.headers
            return response

    opener = Opener()
    monkeypatch.setattr(benign.urllib.request, "build_opener", lambda *args: opener)
    url = "https://upload.wikimedia.org/fixture"
    receipt = benign._download(url, tmp_path / "ok.bin", 6, 5)
    benign._check_file(tmp_path, "ok.bin", 5, receipt["sha256"])
    with pytest.raises(ValueError, match="SHA-256"):
        benign._check_file(tmp_path, "ok.bin", 5, "0" * 64)
    with pytest.raises(ValueError, match="Streaming"):
        benign._download(url, tmp_path / "over.bin", 4)
    opener.headers = {"Content-Length": "1000"}
    with pytest.raises(ValueError, match="Announced"):
        benign._download(url, tmp_path / "announced.bin", 6)
    assert not (tmp_path / "announced.bin").exists()
    opener.headers = {"Content-Length": "5"}
    with pytest.raises(ValueError, match="size changed"):
        benign._download(url, tmp_path / "changed.bin", 6, 4)
    for url in (
        "http://upload.wikimedia.org/a",
        "https://example.org/a",
        "file:///etc/passwd",
        "https://localhost/a",
        "https://user:password@commons.wikimedia.org/a",
    ):
        with pytest.raises(ValueError):
            benign._url(url)
    with pytest.raises(ValueError):
        benign._Redirect().redirect_request(None, None, 302, "", {}, "https://example.org/a")


def test_pearson_spearman_ties_and_constant_vectors():
    assert benign.pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1)
    assert benign.pearson([1, 2, 3], [6, 4, 2]) == pytest.approx(-1)
    assert benign.pearson([1, 2, 3], [1, 0, 1]) == pytest.approx(0)
    assert benign.ranks([4, 1, 1, 3]) == [4, 1.5, 1.5, 3]
    assert benign.spearman([1, 2, 3, 4], [1, 10, 100, 1000]) == pytest.approx(1)
    assert benign.spearman([1, 1, 2, 3], [3, 3, 2, 1]) == pytest.approx(-1)
    for function in (benign.pearson, benign.spearman):
        assert function([1, 1], [1, 2]) is None
        assert function([], []) is None
        assert function([1], [2]) is None
        with pytest.raises(ValueError):
            function([1], [1, 2])
        with pytest.raises(ValueError):
            function([0, float("nan")], [0, 1])


def test_vrc_buckets_and_linear_quantiles():
    summary = benign.vrc_distribution([0, 0.01, 0.249, 0.25, 0.499, 0.5, 0.749, 0.75, 1])
    assert summary["buckets"] == {
        "zero": 1,
        "gt0_lt025": 2,
        "ge025_lt050": 2,
        "ge050_lt075": 2,
        "ge075": 2,
    }
    assert benign.distribution([0, 1, 2, 3])["p25"] == 0.75
    assert benign.distribution([])["median"] is None
    with pytest.raises(ValueError):
        benign.vrc_distribution([1.01])


def test_failed_samples_source_family_aggregation_and_missing_vs_zero():
    samples = benign.sample_design(acquired_records())
    chosen = [samples[0], samples[1], samples[2]]
    rows = [
        benign.extract_result(s, None, failure="harness_timeout" if i == 2 else None)
        for i, s in enumerate(chosen)
    ]
    rows[0].update(overall_score=26, risk_level="medium")
    rows[1].update(overall_score=60, risk_level="high")
    result = benign.aggregate(rows)["media"]["audio"]
    assert result["samples"] == 3 and result["source_families"] == 2
    assert result["gt25"]["sample"] == {"numerator": 2, "denominator": 3, "rate": 2 / 3}
    assert result["gt25"]["source_family_any"]["rate"] == 0.5
    assert result["gt25"]["assessed_sample"]["rate"] == 1
    assert result["unassessed"] == 1
    assert rows[2]["analysis_status"] == "harness_timeout"
    video = [benign.extract_result(s, None) for s in samples if s["media_type"] == "video"]
    assert benign.correlation(video)["unavailable"] == 16
    assert benign.correlation(video)["both_zero"] == 0
    assert benign.aggregate(video)["vrc"]["n"] == 0


def test_json_csv_finite_and_zero_is_not_null(tmp_path):
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            benign._csv(tmp_path / "bad.csv", [{"value": bad}])
        with pytest.raises(ValueError):
            benign.demo._json_bytes({"value": bad})
    benign._csv(
        tmp_path / "ok.csv", [{"sample_id": "a", "value": 0}, {"sample_id": "b", "value": None}]
    )
    with (tmp_path / "ok.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream)) == [
            {"sample_id": "a", "value": "0"},
            {"sample_id": "b", "value": ""},
        ]


def test_video_joint_counts_and_grouped_correlation():
    samples = [r for r in benign.sample_design(acquired_records()) if r["media_type"] == "video"][
        :4
    ]
    rows = [benign.extract_result(sample, None) for sample in samples]
    for row, quality, repetition in zip(rows, [0, 1, 0, 1], [0, 0.35, 0.1, 0], strict=True):
        for family in row["families"]:
            family["usable_members"] = 1
            if family["evidence_family"] == "video_quality":
                family["response"] = quality
            if family["evidence_family"] == "video_repetition":
                family["response"] = repetition
        for analyzer in row["analyzers"]:
            if analyzer["analyzer_id"] == benign.VRC:
                analyzer["normalized_response"] = repetition / 0.35
    aggregate = benign.aggregate(rows)
    result = aggregate["video_correlation"]
    for key in ("joint_nonzero", "quality_only", "repetition_only", "both_zero"):
        assert result[key] == 1
    assert result["pearson"] == pytest.approx(np.corrcoef([0, 1, 0, 1], [0, 0.35, 0.1, 0])[0, 1])
    assert result["joint_family_any"]["rate"] == 0.5
    assert result["source_family_means"]["pearson"] is None
    assert aggregate["vrc"]["ge075_family_any"]["rate"] == 0.5


@pytest.fixture
def local_workspace(tmp_path, monkeypatch):
    specs = (
        benign.SourceSpec("audio-01", "test.wav", "local_fixture"),
        benign.SourceSpec("video-01", "test.mp4", "local_fixture"),
    )
    monkeypatch.setattr(benign, "SOURCES", specs)
    (tmp_path / "sources").mkdir()
    (tmp_path / "licenses").mkdir()
    rate = 16000
    t = np.arange(rate * 12) / rate
    samples = np.rint(5000 * np.sin(2 * np.pi * (170 * t + 3 * t**2))).astype("<i2")
    with wave.open(str(tmp_path / "sources/audio-01.wav"), "wb") as stream:
        stream.setparams((1, 2, rate, len(samples), "NONE", "not compressed"))
        stream.writeframes(samples.tobytes())
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=12:duration=12",
            "-an",
            "-c:v",
            "mpeg4",
            "-threads",
            "1",
            "-q:v",
            "2",
            str(tmp_path / "sources/video-01.mp4"),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    rows = records()
    acquired = []
    for row in rows:
        for path_key, hash_key in (
            ("license_snapshot", "license_sha256"),
            ("page_snapshot", "page_sha256"),
        ):
            path = tmp_path / row[path_key]
            path.write_bytes(b"first-party local test fixture")
            row[hash_key] = benign._hash_file(path)
        path = tmp_path / row["original_filename"]
        row["original_size_bytes"] = path.stat().st_size
        acquired.append(
            {
                **row,
                "original_sha256": benign._hash_file(path),
                "retrieved_at": "2026-10-13T00:00:00+00:00",
            }
        )
    benign._seal(
        tmp_path,
        "source-plan.json",
        {
            "policy": benign.demo._policy(),
            "environment": benign.demo._environment(),
            "sources": rows,
        },
    )
    benign._seal(
        tmp_path,
        "source-manifest.json",
        {
            "source_plan_sha256": benign._hash_file(tmp_path / "source-plan.json"),
            "sources": acquired,
        },
    )
    return tmp_path


def test_model_freeze_and_hash_guard(local_workspace, monkeypatch):
    original = benign.demo._policy()
    assert original["model"] == "diploma_ensemble_v1@0.1.0"
    assert original["assessment_sha256_lf"] == benign.demo.ASSESSMENT_SHA256
    assert original["capacities"] == {"image": 3.4375, "audio": 2.8125, "video": 2.05}
    changed = copy.deepcopy(original)
    changed["family_factors"][1] = 0.5
    monkeypatch.setattr(benign.demo, "_policy", lambda: changed)
    with pytest.raises(ValueError, match="changed since"):
        benign._plan(local_workspace)


def test_existing_acquisition_is_verified_without_network(local_workspace, monkeypatch):
    def unexpected_network(*args, **kwargs):
        pytest.fail("Recorded originals must be checked without redownloading")

    monkeypatch.setattr(benign, "_download", unexpected_network)
    assert len(benign.acquire(local_workspace)) == 2
    (local_workspace / "sources/audio-01.wav").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        benign.acquire(local_workspace)


def test_local_four_file_e2e_projection_determinism_and_report(local_workspace):
    root = local_workspace
    manifest = benign.prepare(root)
    for row in manifest["samples"]:
        command = row["ffmpeg_command"].copy()
        second = root / (row["sample_id"] + "." + row["file_format"])
        command[-1] = str(second)
        subprocess.run(command, cwd=root, check=True, capture_output=True, timeout=30)
        assert benign._hash_file(second) == row["sha256"]
    before = benign.report(root)
    assert before["all"]["statuses"] == {"not_evaluated": 4}
    benign.evaluate(root)
    summary = benign.report(root)
    rows = benign.demo._read_json(root / "tables/samples.json")
    assert summary["all"]["statuses"] == {"completed": 4}
    for row in rows:
        assert row["cleanup_status"] == "completed"
        assert not row["extraction_errors"]
        assert sum(f["score_contribution"] for f in row["families"]) == pytest.approx(
            row["overall_score"]
        )
        assert all(a["raw_metrics"] is not None for a in row["analyzers"])
    video = [r for r in rows if r["media_type"] == "video"]
    assert all(benign._analyzer(r, benign.VRC)["raw_metrics"]["eligible_pairs"] > 0 for r in video)
    for filename in (
        "source-provenance.csv",
        "sample-manifest.csv",
        "score-by-sample.csv",
        "family-responses.csv",
        "analyzer-responses.csv",
        "source-family-summary.csv",
        "audio-elevated.csv",
        "video-vrc-baseline.csv",
        "video-quality-vrc-correlation.csv",
    ):
        with (root / "tables" / filename).open(encoding="utf-8-sig", newline="") as stream:
            assert csv.DictReader(stream).fieldnames
    with pytest.raises(FileExistsError):
        benign.evaluate(root)
    with pytest.raises(FileExistsError):
        benign.prepare(root)
    saved = root / "results/audio-01-reference.json"
    saved.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Result hash"):
        benign.report(root)


def test_manifest_split_and_media_tampering(local_workspace):
    root = local_workspace
    manifest = benign.prepare(root)
    sample = root / manifest["samples"][0]["filename"]
    sample.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        benign.load_manifest(root)
    manifest["samples"][0]["split"] = "holdout_benign"
    (root / "manifest.json").write_bytes(benign.demo._json_bytes(manifest))
    (root / "manifest.json.sha256").write_text(
        benign._hash_file(root / "manifest.json"), encoding="ascii"
    )
    with pytest.raises(ValueError, match="split"):
        benign.load_manifest(root)


def test_no_default_destination(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["benign", "declare"])
    with pytest.raises(SystemExit) as error:
        benign.main()
    assert error.value.code == 2
