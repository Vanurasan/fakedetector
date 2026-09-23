"""Real-input pilot protocol tests using only generated, rights-neutral fixtures."""

import json
import sqlite3
from dataclasses import asdict, replace
from pathlib import Path

import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from fakedetector.config.models import AppConfig

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts.research.jpeg_calibration import AdmissionError, measure
    from scripts.research.jpeg_corpus import Case, encode, source_image
    from scripts.research.jpeg_pilot import Manifest, Moments, load_manifest, run, sha256


@pytest.fixture
def pilot(tmp_path):
    data = encode(source_image("noise", 321, (99, 87)), 75, 2)
    image = tmp_path / "image.jpg"
    image.write_bytes(data)
    terms = tmp_path / "terms.txt"
    terms.write_text("Generated test source; no downloaded media.")
    digest = sha256(image)
    case = Case(
        "case1",
        "group1",
        "pilot_external_stress",
        "unknown",
        "unknown",
        "nat",
        99,
        87,
        "RGB",
        digest,
        len(data),
        None,
        None,
        None,
        False,
        1,
        (0, 0),
        {},
        {},
    )
    source = {
        "source_id": "source1",
        "source_group": "group1",
        "dataset": "vision",
        "partition": "pilot_external_stress",
        "source_url": "https://example.org/test.jpg",
        "retrieved": "2026-09-24",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "rights_reviewed": True,
        "attribution": "Generated fixture",
        "device": "test",
        "format": "JPEG",
        "original": {"path": str(image), "sha256": digest},
        "terms": {"path": str(terms), "sha256": sha256(terms)},
    }
    record = {"source_id": "source1", "path": str(image), "case": asdict(case), "transforms": []}
    manifest = {"sources": [source], "records": [record]}
    config = AppConfig.model_validate(
        yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    )
    return manifest, config


def save(tmp_path, manifest):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_real_validation_and_resume_without_double_count(tmp_path, pilot):
    manifest, config = pilot
    path = save(tmp_path, manifest)
    first = run(path, tmp_path / "out", config)
    second = run(path, tmp_path / "out", config)
    assert first == second
    assert first["counts"]["vision/measured"] == 1
    assert first["measured_groups"] == {"vision": 1}
    with sqlite3.connect(tmp_path / "out/results.sqlite3") as conn:
        assert conn.execute("SELECT count(*) FROM results").fetchone()[0] == 1
    assert not list((tmp_path / "out/workspace").glob("*"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("partition", "final_holdout"),
        ("partition", "pilot_exploration"),
        ("source_url", ""),
        ("attribution", ""),
        ("dataset", "unknown"),
    ],
)
def test_source_contract(tmp_path, pilot, field, value):
    manifest, _ = pilot
    manifest["sources"][0][field] = value
    with pytest.raises(ValidationError):
        load_manifest(save(tmp_path, manifest))


@pytest.mark.parametrize("kind", ["rights", "hash", "terms", "missing"])
def test_source_rejections_are_not_measurements(tmp_path, pilot, kind):
    manifest, config = pilot
    source = manifest["sources"][0]
    if kind == "rights":
        source["rights_reviewed"] = False
    elif kind == "hash":
        source["original"]["sha256"] = "0" * 64
        # Keep the chain internally consistent; actual bytes still fail admission.
        manifest["records"][0]["transforms"] = [
            {
                "operation": "test",
                "input_sha256": "0" * 64,
                "output_sha256": manifest["records"][0]["case"]["sha256"],
                "settings": {},
            }
        ]
    elif kind == "terms":
        source["terms"]["sha256"] = "0" * 64
    else:
        source["original"]["path"] = str(tmp_path / "absent.jpg")
    result = run(save(tmp_path, manifest), tmp_path / "out", config)
    assert result["measured_groups"] == {}
    assert sum(result["counts"].values()) == 1


def test_duplicate_and_group_accounting(tmp_path, pilot):
    manifest, config = pilot
    record = json.loads(json.dumps(manifest["records"][0]))
    record["case"]["case_id"] = "case2"
    manifest["records"].append(record)
    result = run(save(tmp_path, manifest), tmp_path / "out", config)
    assert result["counts"]["vision/measured"] == 1
    assert result["counts"]["vision/exact_derivative_duplicate"] == 1
    source = json.loads(json.dumps(manifest["sources"][0]))
    source.update(
        source_id="source2", source_group="group2", source_url="https://example.org/duplicate.jpg"
    )
    manifest["sources"].append(source)
    result = run(save(tmp_path, manifest), tmp_path / "other", config)
    assert result["measured_groups"] == {}
    assert result["counts"]["vision/ambiguous_source_duplicate"] == 2


def test_resume_rejects_changed_input_and_manifest(tmp_path, pilot):
    manifest, config = pilot
    path = save(tmp_path, manifest)
    run(path, tmp_path / "out", config)
    media = Path(manifest["records"][0]["path"])
    media.write_bytes(media.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="admission changed"):
        run(path, tmp_path / "out", config)
    manifest["sources"][0]["device"] = "changed"
    save(tmp_path, manifest)
    with pytest.raises(ValueError, match="implementation changed"):
        run(path, tmp_path / "out", config)


def test_transform_and_partition_binding(tmp_path, pilot):
    manifest, _ = pilot
    record = manifest["records"][0]
    record["transforms"] = [
        {
            "operation": "jpeg",
            "input_sha256": "0" * 64,
            "output_sha256": record["case"]["sha256"],
            "settings": {},
        }
    ]
    with pytest.raises(ValidationError, match="broken transform chain"):
        load_manifest(save(tmp_path, manifest))
    record["transforms"] = []
    record["case"]["source_group"] = "another"
    with pytest.raises(ValidationError, match="source-group/partition"):
        load_manifest(save(tmp_path, manifest))


def test_real_signature_rejection_and_cleanup(tmp_path, pilot):
    manifest, config = pilot
    path = Path(manifest["records"][0]["path"])
    Image.new("RGB", (99, 87)).save(path, format="PNG")
    case = Manifest.model_validate(manifest).records[0].case
    case = replace(case, sha256=sha256(path), size_bytes=path.stat().st_size)
    with pytest.raises(AdmissionError, match="file_signature_mismatch"):
        measure(case, tmp_path / "out", config, input_path=path)
    assert not list((tmp_path / "out/workspace").glob("*"))


def test_online_moments():
    values = Moments()
    for value in (0.1, 0.3, 0.5, 0.7):
        values.add(value)
    result = values.result()
    assert result["mean"] == pytest.approx(0.4)
    assert result["variance"] == pytest.approx(0.05)
    assert sum(result["amplitude_bins_0_1"]) == 4
    assert len(values.bins) == 20


def test_bounds_and_repository_paths(tmp_path, pilot):
    manifest, _ = pilot
    manifest["records"][0]["path"] = str(Path.cwd() / "forbidden.jpg")
    with pytest.raises(ValidationError, match="outside repository"):
        load_manifest(save(tmp_path, manifest))
    with pytest.raises(ValueError, match="outside repository"):
        load_manifest(Path.cwd() / "manifest.json")


def test_controlled_transform_generation(tmp_path, pilot):
    from scripts.research.jpeg_pilot import Source
    from scripts.research.jpeg_pilot_corpus import derivatives

    manifest, _ = pilot
    master = tmp_path / "master.png"
    source_image("noise", 322, (99, 87)).save(master)
    raw = manifest["sources"][0]
    raw.update(
        dataset="rawpixls",
        partition="pilot_exploration",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        master={"path": str(master), "sha256": sha256(master)},
        development={"converter": "generated fixture, not actual RAW"},
    )
    source = Source.model_validate(raw)
    records = derivatives(source, tmp_path / "corpus", extended=True, ordinal=1)
    assert len(records) == 8
    Manifest(sources=(source,), records=tuple(records))
    same = next(r for r in records if r.case.variant == "same_dqt")
    assert same.case.first_tables == same.case.final_tables
    shifted = next(r for r in records if r.case.variant == "shift")
    assert (shifted.case.width, shifted.case.height, shifted.case.shift) == (96, 82, (3, 5))
    assert any(t.operation == "shift" for t in shifted.transforms)
    patch = next(r for r in records if r.case.variant == "phase_patch")
    assert patch.case.source_group == source.source_group
    assert patch.case.width == 99 and patch.case.height == 87
    assert next(t for t in patch.transforms if t.operation == "phase_patch").settings == {
        "box": [49, 0, 99, 87],
        "offset": [3, 5],
        "wrap": True,
        "hash_kind": "RGB8_C_order_pixels",
    }
    again = derivatives(source, tmp_path / "corpus", extended=True, ordinal=1)
    assert [r.case.sha256 for r in records] == [r.case.sha256 for r in again]
    assert len(derivatives(source, tmp_path / "one", extended=False, ordinal=0)) == 1


def test_raw_missing_master_and_qa_rejection(tmp_path, pilot):
    from scripts.research.jpeg_pilot import Source

    manifest, _ = pilot
    raw = manifest["sources"][0]
    raw.update(
        dataset="rawpixls",
        partition="pilot_exploration",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
    )
    with pytest.raises(AdmissionError, match="raw_master_provenance_missing"):
        Source.model_validate(raw).verify()
    raw["qa_rejection"] = "ambiguous_visual_duplicate"
    with pytest.raises(AdmissionError, match="ambiguous_visual_duplicate"):
        Source.model_validate(raw).verify()


def test_interrupted_run_resumes_committed_record(tmp_path, pilot, monkeypatch):
    from scripts.research import jpeg_pilot

    manifest, config = pilot
    second = json.loads(json.dumps(manifest["records"][0]))
    second["case"]["case_id"] = "case2"
    image = tmp_path / "second.jpg"
    image.write_bytes(encode(source_image("noise", 777, (99, 87)), 75, 2))
    second["path"] = str(image)
    second["case"].update(sha256=sha256(image), size_bytes=image.stat().st_size)
    second["transforms"] = [
        {
            "operation": "test",
            "input_sha256": manifest["records"][0]["case"]["sha256"],
            "output_sha256": sha256(image),
            "settings": {},
        }
    ]
    manifest["records"].append(second)
    path = save(tmp_path, manifest)
    original = jpeg_pilot.measure
    calls = []

    def interrupted(case, *args, **kwargs):
        calls.append(case.case_id)
        if case.case_id == "case2":
            raise KeyboardInterrupt
        return original(case, *args, **kwargs)

    monkeypatch.setattr(jpeg_pilot, "measure", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(path, tmp_path / "out", config)
    assert calls == ["case1", "case2"]
    monkeypatch.setattr(jpeg_pilot, "measure", original)
    result = run(path, tmp_path / "out", config)
    assert result["counts"]["vision/measured"] == 2
    assert result["measured_groups"] == {"vision": 1}


def test_source_group_bound(tmp_path, pilot):
    manifest, _ = pilot
    original = manifest["sources"][0]
    manifest["sources"] = [
        dict(
            original,
            source_id=f"source{i}",
            source_group=f"group{i}",
            source_url=f"https://example.org/{i}.jpg",
        )
        for i in range(101)
    ]
    manifest["records"] = []
    with pytest.raises(ValidationError, match="owner bound"):
        load_manifest(save(tmp_path, manifest))
