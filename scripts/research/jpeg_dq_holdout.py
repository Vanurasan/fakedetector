"""Research-only R3D manifest lock and one-endpoint-per-source reporting."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from PIL import Image
from pydantic import Field, model_validator

from .jpeg_corpus import Case, decoded, encode
from .jpeg_dq_rule import Rule, exact_upper, load_frozen
from .jpeg_pilot import Asset, Digest, Identifier, StrictModel, external

RULE_SHA256: Final = "2b958bf4fb94926c7f7de0a9a7b74f3897667a22cb802fb85592bab4dd5fd5be"


class Identity(StrictModel):
    source_group: Identifier
    scene_group: Identifier
    source_url: str
    original_sha256: Digest
    master_sha256: Digest | None = None

    def keys(self) -> set[tuple[str, str]]:
        keys = {
            ("group", self.source_group),
            ("scene", self.scene_group),
            ("url", self.source_url),
            ("bytes", self.original_sha256),
        }
        if self.master_sha256 is not None:
            keys.add(("bytes", self.master_sha256))
        return keys


class HoldoutSource(StrictModel):
    identity: Identity
    split: Literal["final_holdout"]
    original: Asset
    master: Asset
    endpoint: Asset
    terms: Asset
    license_url: Literal["https://creativecommons.org/publicdomain/zero/1.0/"]
    rights_reviewed: Literal[True]
    format: str
    device: str
    content: str

    @model_validator(mode="after")
    def matching_assets(self) -> HoldoutSource:
        if (
            self.original.sha256 != self.identity.original_sha256
            or self.master.sha256 != self.identity.master_sha256
        ):
            raise ValueError("identity/asset hash mismatch")
        return self


class HoldoutManifest(StrictModel):
    version: Literal["DQ-R3D-1"] = "DQ-R3D-1"
    sources: tuple[HoldoutSource, ...] = Field(min_length=1)
    excluded: tuple[Identity, ...] = Field(min_length=1)
    acquisition_protocol: Asset
    exclusion_evidence: Asset
    implementation_evidence: Asset
    repo_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    rule_sha256: Literal["2b958bf4fb94926c7f7de0a9a7b74f3897667a22cb802fb85592bab4dd5fd5be"] = (
        RULE_SHA256
    )
    acceptance: Literal["one-sided exact 95% upper <= 0.01; actual applicable n"] = (
        "one-sided exact 95% upper <= 0.01; actual applicable n"
    )
    replacement: Literal["none after freeze"] = "none after freeze"

    @model_validator(mode="after")
    def no_overlap(self) -> HoldoutManifest:
        seen = set().union(*(row.keys() for row in self.excluded))
        endpoints: set[str] = set()
        for source in self.sources:
            keys = source.identity.keys()
            if seen.intersection(keys) or source.endpoint.sha256 in endpoints:
                raise ValueError("duplicate or prior pilot/calibration/validation/QA overlap")
            seen.update(keys)
            endpoints.add(source.endpoint.sha256)
        return self


def _canonical(model: StrictModel) -> bytes:
    return (
        json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def freeze_manifest(manifest: HoldoutManifest, path: Path) -> str:
    data = _canonical(manifest)
    with external(path).open("xb") as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def load_manifest(path: Path, expected_sha256: str) -> HoldoutManifest:
    data = external(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("holdout membership hash mismatch")
    manifest = HoldoutManifest.model_validate_json(data)
    if _canonical(manifest) != data:
        raise ValueError("noncanonical holdout manifest")
    return manifest


def open_once(
    manifest_path: Path, expected_sha256: str, rule_path: Path
) -> tuple[HoldoutManifest, Rule]:
    """Verify every input before creating the exclusive outcome-opening marker.

    Caller must not measure before this returns. An interrupted opening requires
    owner review; this function never resumes, replaces sources or removes a lock.
    """
    manifest = load_manifest(manifest_path, expected_sha256)
    rule = load_frozen(rule_path, RULE_SHA256)
    for asset in (
        manifest.acquisition_protocol,
        manifest.exclusion_evidence,
        manifest.implementation_evidence,
    ):
        asset.verify()
    for source in manifest.sources:
        for asset in (source.original, source.master, source.endpoint, source.terms):
            asset.verify()
    marker = {
        "manifest_sha256": expected_sha256,
        "rule_sha256": RULE_SHA256,
        "opened_at": datetime.now(UTC).isoformat(),
    }
    with external(manifest_path).with_suffix(".opened.json").open("x", encoding="utf-8") as out:
        json.dump(marker, out, sort_keys=True)
    return manifest, rule


class Outcome(StrictModel):
    source_group: Identifier
    status: Literal[
        "applicable_negative", "insufficient_evidence", "admission_failure", "protocol_invalid"
    ]
    positive: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def applicable_decision(self) -> Outcome:
        if (self.status == "applicable_negative") != (self.positive is not None):
            raise ValueError("only applicable endpoints have a boolean decision")
        return self


def generate_endpoint(
    master: Asset, source_group: str, content: str, ordinal: int, output: Path
) -> Case:
    """R3C single-history endpoint, with final_holdout identity and no challenges."""
    if ordinal < 0:
        raise ValueError("nonnegative frozen ordinal required")
    master.verify()
    with Image.open(master.path) as opened:
        if opened.format != "PNG" or opened.mode != "RGB":
            raise ValueError("bounded developed RGB PNG required")
        if max(opened.size) > 1280 or opened.width * opened.height > 1_000_000:
            raise ValueError("bounded master required")
        opened.load()
        raster = opened.convert("L") if ordinal % 10 == 0 else opened.copy()
        quality = (40, 75, 95)[ordinal % 3]
        sampling = (ordinal // 3) % 3
        progressive = ordinal % 5 == 0
        data = encode(raster, quality, sampling, progressive)
    image, tables = decoded(data)
    with external(output).open("xb") as stream:
        stream.write(data)
    return Case(
        source_group + "-single",
        source_group,
        "final_holdout",
        content,
        "single",
        "single",
        image.width,
        image.height,
        image.mode,
        hashlib.sha256(data).hexdigest(),
        len(data),
        None,
        quality,
        sampling,
        progressive,
        1,
        (0, 0),
        {},
        tables,
    )


def aggregate(manifest: HoldoutManifest, outcomes: Iterable[Outcome]) -> dict[str, object]:
    rows = list(outcomes)
    groups = [row.source_group for row in rows]
    if len(set(groups)) != len(groups) or set(groups) != {
        source.identity.source_group for source in manifest.sources
    }:
        raise ValueError("exact frozen membership required; no replacement or missing outcomes")
    applicable = sum(row.status == "applicable_negative" for row in rows)
    abstentions = sum(row.status == "insufficient_evidence" for row in rows)
    failures = sum(row.status == "admission_failure" for row in rows)
    invalid = sum(row.status == "protocol_invalid" for row in rows)
    positives = sum(row.positive is True for row in rows)
    upper = exact_upper(positives, applicable)
    result = (
        "FINAL_HOLDOUT_INVALID"
        if invalid
        else "FINAL_HOLDOUT_PASS"
        if upper is not None and upper <= 0.01
        else "FINAL_HOLDOUT_FAIL"
    )
    assigned = len(rows)
    return {
        "assigned": assigned,
        "admitted": applicable + abstentions,
        "applicable": applicable,
        "abstentions": abstentions,
        "admission_failures": failures,
        "protocol_invalid": invalid,
        "false_positives": positives,
        "fpr": positives / applicable if applicable else None,
        "upper_95": upper,
        "applicability_rate": applicable / assigned,
        "abstention_rate": abstentions / assigned,
        "admission_failure_rate": failures / assigned,
        "result": result,
    }
