"""Bounded external-corpus research runner; all pilot partitions are exploration.

Run with --manifest and --output, both outside the repository. SQLite commits one
complete record at a time; resume binds inputs, configuration and implementation.
No production decision rules are introduced here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from fakedetector.config.models import AppConfig
from fakedetector.intake.temporary_input import FileTooLargeError
from fakedetector.preprocessing._errors import PreprocessingError

from .jpeg_calibration import AdmissionError, measure, write_json
from .jpeg_corpus import Case

REPO = Path(__file__).resolve().parents[2]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")]


def external(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == REPO or resolved.is_relative_to(REPO):
        raise ValueError("pilot files must remain outside repository")
    return resolved


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Asset(StrictModel):
    path: Path
    sha256: Digest

    def verify(self) -> None:
        if sha256(external(self.path)) != self.sha256:
            raise AdmissionError("asset_hash_mismatch")


class Source(StrictModel):
    source_id: Identifier
    source_group: Identifier
    dataset: Literal["rawpixls", "vision"]
    partition: Literal["pilot_exploration", "pilot_external_stress"]
    source_url: str
    retrieved: date
    license_url: str
    rights_reviewed: bool = Field(strict=True)
    attribution: str
    device: str
    format: str
    original: Asset
    terms: Asset
    master: Asset | None = None
    development: dict[str, JsonValue] = Field(default_factory=dict)
    qa_rejection: str | None = None

    @model_validator(mode="after")
    def partition_contract(self) -> Source:
        expected = "pilot_exploration" if self.dataset == "rawpixls" else "pilot_external_stress"
        if self.partition != expected:
            raise ValueError("pilot partition cannot enter final holdout or primary VISION pool")
        if not self.source_url.startswith("https://") or not self.attribution.strip():
            raise ValueError("source URL and attribution required")
        return self

    def verify(self) -> None:
        if self.qa_rejection:
            raise AdmissionError(self.qa_rejection)
        license_url = {
            "rawpixls": "https://creativecommons.org/publicdomain/zero/1.0/",
            "vision": "https://creativecommons.org/licenses/by-sa/4.0/",
        }[self.dataset]
        if not self.rights_reviewed or self.license_url != license_url:
            raise AdmissionError("rights_not_admitted")
        self.terms.verify()
        self.original.verify()
        if self.dataset == "rawpixls":
            if self.master is None or not self.development:
                raise AdmissionError("raw_master_provenance_missing")
            self.master.verify()


class Transform(StrictModel):
    operation: str
    input_sha256: Digest
    output_sha256: Digest
    settings: dict[str, JsonValue]


class Record(StrictModel):
    source_id: Identifier
    path: Path
    case: Case
    transforms: tuple[Transform, ...]


class Manifest(StrictModel):
    sources: tuple[Source, ...] = Field(max_length=500)
    records: tuple[Record, ...] = Field(max_length=1000)

    @model_validator(mode="after")
    def identities(self) -> Manifest:
        sources = {s.source_id: s for s in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("duplicate source ID")
        groups: dict[str, tuple[str, str]] = {}
        source_records: dict[tuple[str, str], str] = {}
        for source in self.sources:
            record_key = (source.dataset, source.source_url)
            if source_records.setdefault(record_key, source.source_group) != source.source_group:
                raise ValueError("source record assigned to multiple groups")
            binding = (source.dataset, source.partition)
            if groups.setdefault(source.source_group, binding) != binding:
                raise ValueError("source-group partition/dataset leakage")
        for dataset, maximum in (("rawpixls", 200), ("vision", 100)):
            if sum(d == dataset for d, _ in groups.values()) > maximum:
                raise ValueError("pilot source-group owner bound exceeded")
        ids: set[str] = set()
        for record in self.records:
            c = record.case
            if c.case_id in ids or not c.case_id or len(c.case_id) > 160:
                raise ValueError("duplicate/invalid case ID")
            ids.add(c.case_id)
            if record.source_id not in sources:
                raise ValueError("record references unknown source")
            source = sources[record.source_id]
            if (c.source_group, c.partition) != (source.source_group, source.partition):
                raise ValueError("record source-group/partition mismatch")
            parent = source.master.sha256 if source.master else source.original.sha256
            for transform in record.transforms:
                if transform.input_sha256 != parent:
                    raise ValueError("broken transform chain")
                parent = transform.output_sha256
            if c.sha256 != parent:
                raise ValueError("derivative identity missing from transform chain")
            external(record.path)
        return self


def load_manifest(path: Path) -> Manifest:
    path = external(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("manifest size ceiling")
    return Manifest.model_validate_json(path.read_bytes())


class Moments:
    """Constant-space scalar distributions with fixed descriptive amplitude bins."""

    def __init__(self) -> None:
        self.n = 0
        self.mean = self.m2 = 0.0
        self.low = float("inf")
        self.high = float("-inf")
        self.bins = [0] * 20

    def add(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.low, self.high = min(self.low, value), max(self.high, value)
        self.bins[min(19, max(0, int(value * 20)))] += 1

    def result(self) -> dict[str, object]:
        return {
            "n": self.n,
            "mean": self.mean,
            "variance": self.m2 / self.n,
            "minimum": self.low,
            "maximum": self.high,
            "amplitude_bins_0_1": self.bins,
        }


def summarize(connection: sqlite3.Connection) -> dict[str, object]:
    counts: Counter[str] = Counter()
    groups: dict[str, set[str]] = defaultdict(set)
    distributions: dict[str, Moments] = defaultdict(Moments)
    grids: dict[str, Counter[str]] = defaultdict(Counter)
    times: Counter[str] = Counter()
    largest_pixels = largest_numeric = 0
    # Only one serialized measurement is resident. Group identities are bounded by manifest.
    for (payload,) in connection.execute("SELECT payload FROM results ORDER BY case_id"):
        row = json.loads(payload)
        dataset = row["dataset"]
        status = row["status"]
        counts[f"{dataset}/{status}"] += 1
        if status != "measured":
            continue
        result = row["measurement"]
        c = result["case"]
        groups[dataset].add(c["source_group"])
        largest_pixels = max(largest_pixels, c["width"] * c["height"])
        largest_numeric = max(largest_numeric, result["numeric_bytes"])
        flags = [w for w in result["grid"] if w["flag"]]
        phases = {(w["x"]["block_phase"], w["y"]["block_phase"]) for w in flags}
        shifted = bool(phases - {(0, 0)})
        strata = [
            f"{dataset}/variant={c['variant']}",
            f"{dataset}/device={row['device']}",
            f"{dataset}/quality={c['final_quality']}/sampling={c['subsampling']}",
        ]
        counts[f"{dataset}/grid/{result['grid_state']}"] += 1
        for stratum in strata:
            grids[stratum].update(
                cases=1,
                any_flag=int(bool(flags)),
                shifted=int(shifted),
                multiple_phases=int(len(phases) > 1),
            )
        for dq in result["dq"]:
            h = dq["histogram"]
            counts[f"{dataset}/dq/{h['state']}"] += 1
            if h["amplitude"] is not None:
                mode = f"c={dq['component']}/uv={dq['u']},{dq['v']}/q2={dq['q2']}"
                for stratum in [*strata, f"{dataset}/grid_shifted={shifted}"]:
                    distributions[f"{stratum}/{mode}"].add(h["amplitude"])
        for field in ("preprocess_seconds", "dq_seconds", "grid_seconds"):
            times[field] += result[field]
    return {
        "counts": dict(counts),
        "measured_groups": {k: len(v) for k, v in groups.items()},
        "grid_by_stratum": dict(grids),
        "amplitude_distributions": {k: v.result() for k, v in sorted(distributions.items())},
        "runtime_seconds": dict(times),
        "largest_pixels": largest_pixels,
        "largest_numeric_bytes": largest_numeric,
        "caveat": "Exploration only; no DQ classifier, population FPR or final holdout.",
    }


def run(manifest_path: Path, output: Path, config: AppConfig) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    output = external(output)
    output.mkdir(parents=True, exist_ok=True)
    binding = {
        "manifest_sha256": sha256(manifest_path),
        "config": config.model_dump(mode="json"),
        "implementations": {
            str(p.relative_to(REPO)): sha256(p)
            for folder in (REPO / "scripts/research", REPO / "src/fakedetector")
            for p in sorted(folder.rglob("*.py"))
        },
        "versions": {n: version(n) for n in ("pillow", "numpy", "pyjpegio", "pydantic")},
    }
    binding_text = json.dumps(binding, sort_keys=True)
    sources = {s.source_id: s for s in manifest.sources}
    source_errors: dict[str, str] = {}
    hash_groups: dict[str, set[str]] = defaultdict(set)
    for source in manifest.sources:
        hash_groups[source.original.sha256].add(source.source_group)
        if source.master:
            hash_groups[source.master.sha256].add(source.source_group)
    for source in manifest.sources:
        try:
            source.verify()
            if len(hash_groups[source.original.sha256]) > 1:
                raise AdmissionError("ambiguous_source_duplicate")
            if source.master and len(hash_groups[source.master.sha256]) > 1:
                raise AdmissionError("ambiguous_master_duplicate")
        except (AdmissionError, OSError) as error:
            source_errors[source.source_id] = (
                str(error) if isinstance(error, AdmissionError) else "source_missing"
            )
    with sqlite3.connect(output / "results.sqlite3") as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS binding (value TEXT NOT NULL)")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS results (case_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        previous = connection.execute("SELECT value FROM binding").fetchone()
        if previous is None:
            connection.execute("INSERT INTO binding VALUES (?)", (binding_text,))
            connection.commit()
        elif previous[0] != binding_text:
            raise ValueError("resume manifest/config/implementation changed; use a separate output")
        seen: set[str] = set()
        for ordinal, record in enumerate(manifest.records):
            c, source = record.case, sources[record.source_id]
            reason = source_errors.get(record.source_id)
            try:
                Asset(path=record.path, sha256=c.sha256).verify()
            except (AdmissionError, OSError):
                reason = "derivative_hash_or_file_mismatch"
            if c.sha256 in seen and reason is None:
                reason = "exact_derivative_duplicate"
            seen.add(c.sha256)
            old = connection.execute(
                "SELECT payload FROM results WHERE case_id=?", (c.case_id,)
            ).fetchone()
            if old is not None:
                old_status = json.loads(old[0])["status"]
                if reason is not None and old_status != reason:
                    raise ValueError("resume input admission changed")
                continue
            row = {
                "case_id": c.case_id,
                "source_id": source.source_id,
                "source_group": source.source_group,
                "dataset": source.dataset,
                "device": source.device,
                "status": reason or "pending",
            }
            started = time.perf_counter()
            if reason is None:
                try:
                    row["measurement"] = asdict(measure(c, output, config, input_path=record.path))
                    row["status"] = "measured"
                except AdmissionError as error:
                    row["status"] = str(error)
                except PreprocessingError as error:
                    row["status"] = f"preprocessing/{error.kind}/{error.phase}"
                except FileTooLargeError:
                    row["status"] = "intake_file_too_large"
                except TimeoutError:
                    row["status"] = "research_deadline"
            row["elapsed_seconds"] = time.perf_counter() - started
            connection.execute(
                "INSERT INTO results VALUES (?, ?)", (c.case_id, json.dumps(row, allow_nan=False))
            )
            connection.commit()
            print(f"{ordinal + 1}/{len(manifest.records)} {c.case_id} {row['status']}", flush=True)
        result = summarize(connection)
    write_json(output / "summary.json", result)
    write_json(output / "provenance.json", binding)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = AppConfig.model_validate(
        yaml.safe_load((REPO / "config/config.example.yaml").read_text(encoding="utf-8"))
    )
    run(args.manifest, args.output, config)


if __name__ == "__main__":
    main()
