"""Research-only R3C rule, split guards and source-level statistical reporting."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .jpeg_measurements import MODES, DQMeasurement
from .jpeg_pilot import Asset, Digest, Identifier, StrictModel, external


class CalibrationSource(StrictModel):
    source_group: Identifier
    scene_group: Identifier
    partition: Literal["calibration", "validation"]
    pilot: bool = Field(strict=True)
    source_url: str
    device: str
    content: str
    original: Asset
    master: Asset
    terms: Asset
    license_url: Literal["https://creativecommons.org/publicdomain/zero/1.0/"]
    rights_reviewed: Literal[True]


class Split(StrictModel):
    sources: tuple[CalibrationSource, ...] = Field(max_length=300)
    pilot_groups: tuple[Identifier, ...]

    @model_validator(mode="after")
    def no_leakage(self) -> Split:
        seen: dict[tuple[str, str], str] = {}
        groups: set[str] = set()
        for source in self.sources:
            if source.source_group in groups:
                raise ValueError("duplicate source group")
            groups.add(source.source_group)
            if source.partition == "validation" and (
                source.pilot or source.source_group in self.pilot_groups
            ):
                raise ValueError("pilot cannot enter validation")
            for kind, identity in (
                ("scene", source.scene_group),
                ("url", source.source_url),
                ("original", source.original.sha256),
                ("master", source.master.sha256),
            ):
                # A duplicate within a split also cannot increase independent n.
                if (kind, identity) in seen:
                    raise ValueError("duplicate/leaking source identity")
                seen[kind, identity] = source.partition
        for partition, limit in (("calibration", 200), ("validation", 100)):
            if sum(s.partition == partition for s in self.sources) > limit:
                raise ValueError("partition ceiling")
        return self


class Rule(StrictModel):
    version: Literal["DQ-R3C-1"] = "DQ-R3C-1"
    metric: Literal["empty_fraction", "amplitude"]
    threshold: float = Field(ge=0, le=1, allow_inf_nan=False)
    component: Literal["first_SOF"] = "first_SOF"
    modes: tuple[tuple[int, int], ...] = MODES
    minimum_blocks: Literal[1024] = 1024
    minimum_nonzero: Literal[256] = 256
    minimum_occupied: Literal[8] = 8
    minimum_span: Literal[16] = 16
    minimum_modes: Literal[5] = 5
    aggregation: Literal["median; even count arithmetic mean"] = (
        "median; even count arithmetic mean"
    )
    boundary: Literal["score > threshold; equality negative"] = (
        "score > threshold; equality negative"
    )
    insufficient: Literal["fewer than minimum_modes; never negative"] = (
        "fewer than minimum_modes; never negative"
    )
    metric_definition: Literal[
        "empty_fraction=(span-occupied)/span; amplitude=max(abs(rFFT(H/N,L))[1:]); "
        "L=next_power_of_two(span); signed full histogram including zero; DQ-HIST-1"
    ] = (
        "empty_fraction=(span-occupied)/span; amplitude=max(abs(rFFT(H/N,L))[1:]); "
        "L=next_power_of_two(span); signed full histogram including zero; DQ-HIST-1"
    )
    calibration_manifest_sha256: Digest
    implementation_sha256: Digest
    repo_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    created_at: datetime
    validation_protocol: Literal["R3C-source-endpoint-1"] = "R3C-source-endpoint-1"

    @model_validator(mode="after")
    def fixed_modes(self) -> Rule:
        if self.modes != MODES or self.created_at.tzinfo is None:
            raise ValueError("fixed modes and timezone-aware timestamp required")
        return self


def score(measurements: tuple[DQMeasurement, ...], metric: str) -> float | None:
    """First component in SOF order; support gates are predeclared, not fitted."""
    if metric not in ("empty_fraction", "amplitude"):
        raise ValueError("unknown metric")
    if not measurements:
        return None
    first = measurements[0].component
    modes: set[tuple[int, int]] = set()
    values = []
    for measurement in measurements:
        if measurement.component != first:
            continue
        mode = (measurement.u, measurement.v)
        if mode not in MODES or mode in modes:
            raise ValueError("unexpected/duplicate mode")
        modes.add(mode)
        h = measurement.histogram
        if h.state != "measured":
            continue
        if h.zero_fraction is None or h.occupied is None or h.span is None:
            raise ValueError("incomplete measured histogram")
        # Recover the integer count encoded by the existing exact count/N diagnostic.
        nonzero = h.n - round(h.n * h.zero_fraction)
        if h.n < 1024 or nonzero < 256 or h.occupied < 8 or h.span < 16:
            continue
        value = getattr(h, metric)
        if value is None or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("invalid measured metric")
        values.append(value)
    return statistics.median(values) if len(values) >= 5 else None


def classify(measurements: tuple[DQMeasurement, ...], rule: Rule) -> bool | None:
    value = score(measurements, rule.metric)
    return None if value is None else value > rule.threshold


def canonical_bytes(rule: Rule) -> bytes:
    return (
        json.dumps(rule.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def freeze(rule: Rule, path: Path) -> str:
    """Exclusive creation: never overwrite a rule after validation starts."""
    data = canonical_bytes(rule)
    with external(path).open("xb") as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def load_frozen(path: Path, expected_sha256: str) -> Rule:
    data = external(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("frozen rule hash mismatch")
    rule = Rule.model_validate_json(data)
    if canonical_bytes(rule) != data:
        raise ValueError("noncanonical frozen rule")
    return rule


def exact_upper(errors: int, n: int) -> float | None:
    """One-sided 95% Clopper-Pearson upper, solving P_p[X<=errors]=0.05."""
    if type(n) is not int or type(errors) is not int or not 0 <= errors <= n:
        raise ValueError("invalid binomial counts")
    if n == 0:
        return None
    if errors == n:
        return 1.0
    if errors == 0:
        return -math.expm1(math.log(0.05) / n)
    low, high = 0.0, 1.0
    for _ in range(80):
        p = (low + high) / 2
        terms = [
            math.lgamma(n + 1)
            - math.lgamma(k + 1)
            - math.lgamma(n - k + 1)
            + k * math.log(p)
            + (n - k) * math.log1p(-p)
            for k in range(errors + 1)
        ]
        maximum = max(terms)
        log_cdf = maximum + math.log(math.fsum(math.exp(t - maximum) for t in terms))
        if log_cdf > math.log(0.05):
            low = p
        else:
            high = p
    return high


def endpoint_report(outcomes: Iterable[tuple[str, bool | None]]) -> dict[str, int | float | None]:
    """Exactly one designated image endpoint per independent source, per report."""
    rows = dict[str, bool | None]()
    for group, decision in outcomes:
        if group in rows:
            raise ValueError("derivatives are not independent source endpoints")
        if decision is not None and type(decision) is not bool:
            raise ValueError("boolean or insufficient required")
        rows[group] = decision
    total = len(rows)
    applicable = sum(v is not None for v in rows.values())
    positives = sum(v is True for v in rows.values())
    return {
        "source_groups": total,
        "applicable": applicable,
        "positive": positives,
        "rate": positives / applicable if applicable else None,
        "unconditional_rate": positives / total if total else None,
        "upper_95": exact_upper(positives, applicable),
        "abstentions": total - applicable,
        "abstention_rate": (total - applicable) / total if total else None,
    }


def select_candidate(
    rows: Iterable[tuple[str, str, str, tuple[DQMeasurement, ...]]],
) -> tuple[str, float, dict[str, object]]:
    """Two predeclared families; max primary-negative threshold, strict positive."""
    scores: dict[str, dict[str, dict[str, float | None]]] = {
        metric: {"single": {}, "aligned40to90": {}} for metric in ("empty_fraction", "amplitude")
    }
    seen: set[tuple[str, str]] = set()
    for partition, group, workflow, measurements in rows:
        if partition != "calibration":
            raise ValueError("selection cannot inspect validation")
        if (group, workflow) in seen:
            raise ValueError("duplicate source workflow")
        seen.add((group, workflow))
        if workflow not in ("single", "aligned40to90"):
            continue
        for metric, workflows in scores.items():
            workflows[workflow][group] = score(measurements, metric)
    candidates: dict[str, object] = {}
    best: tuple[str, float] | None = None
    best_sensitivity = -1.0
    for metric, workflows in scores.items():
        negatives, positives = workflows["single"], workflows["aligned40to90"]
        if negatives.keys() != positives.keys() or not negatives:
            raise ValueError("paired source endpoints required")
        supported = [s for s in negatives.values() if s is not None]
        if not supported:
            raise ValueError("no applicable calibration negatives")
        threshold = max(supported)
        sensitivity = sum(s is not None and s > threshold for s in positives.values()) / len(
            positives
        )
        candidates[metric] = {
            "threshold": threshold,
            "negative_applicable": len(supported),
            "negative_source_groups": len(negatives),
            "aligned_unconditional_sensitivity": sensitivity,
        }
        if sensitivity > best_sensitivity:
            best, best_sensitivity = (metric, threshold), sensitivity
    assert best is not None
    return *best, candidates
