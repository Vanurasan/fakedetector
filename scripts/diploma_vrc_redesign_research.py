"""Frozen VRC2 component research: prepare -> observation -> holdout -> demo.

Only accepted external inputs are read. Production dense decoding/rounded block
means are reused; redesigned scores never enter the application or its ensemble.
Each phase creates exclusive, hash-bound evidence. Holdout can evaluate only the
single observation-selected candidate and the unchanged production control.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
from numpy.typing import NDArray

from fakedetector.analyzers._video_experimental import VideoRepeatedContentCorrespondenceAnalyzer
from scripts import diploma_benign_validation as benign
from scripts import diploma_demo_evaluation as demo
from scripts import diploma_vrc_targeted_research as prior

BASELINE = "178434843521382fa905bb4d15b95ceb702fb693"
VERSION = "vrc-redesign-research-1.0.0"
EPSILON = 1e-12
PRODUCTION = "CONTROL_CURRENT_PRODUCTION"
RAW = "CONTROL_RAW_RELATIVE_R10"
IDENTITY = ("dataset", "sample_id", "source_family", "role", "split")
FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Candidate:
    id: str
    descriptor: str
    information: str
    k: int
    relative: str


def candidates() -> tuple[Candidate, ...]:
    return tuple(
        Candidate(f"{d}__{i}__K{k}__{r}", d, i, k, r)
        for d, i, k, r in product(
            ("D1", "D2", "D3", "D4"), ("I0", "I25"), (3, 5, 9), ("R10", "R50")
        )
    ) + (
        Candidate(PRODUCTION, "production", "I0", 1, "absolute"),
        Candidate(RAW, "raw", "I0", 1, "R10"),
    )


def research_matrix() -> dict[str, Any]:
    return {
        "version": VERSION,
        "evidence_level": "COMPONENT_LEVEL_RESEARCH",
        "variants": [asdict(c) for c in candidates()],
        "grid": "production integer-half-up RGB block means, 9 rows x 16 columns, all pixels",
        "groups": "4 consecutive retained frames with known strictly increasing PTS",
        "descriptors": {
            "D1": "per-frame/channel grid minus mean of its 144 blocks; flatten 4 frames",
            "D2": (
                "concat(flatten signed horizontal grid differences, "
                "flatten signed vertical differences), 4 frames"
            ),
            "D3": "flatten three consecutive temporal differences of D1 centered grids",
            "D4": "concat(D2,D3), equal per-component contribution, no manual weights",
        },
        "distance": "float64 mean(abs(descriptor_A-descriptor_B)); no theoretical normalization",
        "temporal_energy": "mean(abs(D3)) for every valid group",
        "information": {
            "I0": "all valid groups",
            "I25": "energy > sample p25(all valid group energies), strict",
        },
        "gap": "B.first*base_B - A.last*base_A >= 2 seconds, exact Fraction; no FPS assumption",
        "runs": (
            "K consecutive group STARTS in each fixed stream/region; every constituent pair "
            "passes gap/geometry/information; no stitching missing starts or regions"
        ),
        "lag": (
            "aligned ordinal lag; retain every actual PTS offset, "
            "no additional unrequested tolerance"
        ),
        "run_distance": "median of all K constituent distances",
        "population": "complete eligible run population, overlapping runs retained",
        "quantile": "linear interpolation at (n-1)*p, using prior research quantile",
        "relative": {
            "R10": "clip(1-min(run_distances)/p10(run_distances),0,1)",
            "R50": "clip(1-min(run_distances)/median(run_distances),0,1)",
        },
        "numerical_epsilon": EPSILON,
        "insufficiency": {
            "no_groups": "INSUFFICIENT_VALID_GROUPS",
            "no_informative_groups": "INSUFFICIENT_LOW_INFORMATION",
            "no_runs": "INSUFFICIENT_RUN_SUPPORT",
            "denominator_le_epsilon": "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION",
            "score": None,
        },
        "controls": {
            PRODUCTION: "exact production retained color/delta minima and existing normalizer",
            RAW: (
                "current joint distance max(color/440640,delta/660960), "
                ">=2s, K1, I0, R10; isolates absolute normalizer"
            ),
        },
        "ties": "first eligible pair in production group/combinations order; runs keep that order",
        "measurable_family": "all its benign samples AND matched reference/repeat are measurable",
        "benign_denominator": (
            "accepted benign derivatives only; paired reference excluded; null never zero"
        ),
        "observation_gates": {
            "all_families_measurable": True,
            "paired_positive_fraction_min": 0.80,
            "paired_median_delta_min": 0.10,
            "benign_median_max": 0.60,
            "benign_ge075_fraction_max": 0.25,
            "deterministic_finite": True,
            "distributed_improvement": "at least two families have strictly positive paired delta",
        },
        "ranking": [
            "ready desc",
            "paired_positive desc",
            "paired_median_delta desc",
            "benign_median asc",
            "benign_ge075 asc",
            "repeat_median desc",
            "D1/D2/D3/D4",
            "K asc",
            "candidate_id lexical",
        ],
        "ranking_nulls": (
            "missing medians rank after defined values; controls excluded from selection"
        ),
        "holdout_gates": {
            "observation_ready": True,
            "all_holdout_families_measurable": True,
            "all_holdout_deltas_positive": True,
            "combined_positive_min": 7,
            "combined_paired_median_delta_min": 0.15,
            "combined_benign_median_max": 0.50,
            "combined_benign_ge075_max": 4,
            "combined_repeat_median_min": 0.70,
            "deterministic_finite": True,
            "production_unchanged": True,
        },
        "negative_diagnostic": (
            "if no observation-ready candidate, freeze highest-ranked descriptive candidate; "
            "never promote after holdout"
        ),
        "disposition": (
            "READY only if every gate; otherwise PARTIAL if positive paired median and "
            "benign median reduction versus production; "
            "NEED_MORE_DATA if no measurable pairs/benign; else STILL_REQUIRED"
        ),
        "production_change": False,
    }


def fingerprint() -> dict[str, str]:
    paths = [Path(__file__), Path(prior.__file__), Path(benign.__file__), Path(demo.__file__)]
    return {p.name: demo._digest(p.read_text(encoding="utf-8").encode()) for p in paths}


def descriptor(values: NDArray[np.int64], kind: str) -> FloatArray:
    """Descriptor on the existing rounded grid, with signed float64 arithmetic."""
    if values.shape != (4, 432) or np.any(values < 0) or np.any(values > 255):
        raise ValueError("Expected four production RGB grids")
    grid = values.astype(np.float64).reshape(4, 9, 16, 3)
    centered = grid - grid.mean(axis=(1, 2), keepdims=True)
    if kind == "D1":
        return centered.ravel()
    if kind == "D3":
        return np.diff(centered, axis=0).ravel()
    spatial = np.concatenate((np.diff(grid, axis=2).ravel(), np.diff(grid, axis=1).ravel()))
    if kind == "D2":
        return spatial
    if kind == "D4":
        return np.concatenate((spatial, np.diff(centered, axis=0).ravel()))
    raise ValueError("Unknown descriptor")


def information(
    groups: list[prior.Group], policy: str
) -> tuple[FloatArray, NDArray[np.bool_], float | None]:
    energies = np.array(
        [np.abs(descriptor(g.values, "D3")).mean() for g in groups], dtype=np.float64
    )
    p25 = prior.quantile(energies.tolist(), 0.25)
    if policy not in {"I0", "I25"}:
        raise ValueError("Unknown information policy")
    keep = np.ones(len(groups), dtype=np.bool_) if policy == "I0" else energies > (p25 or 0)
    return energies, keep, p25


def distant_pairs(groups: list[prior.Group]) -> list[tuple[int, int]]:
    pairs = []
    for i, j in combinations(range(len(groups)), 2):
        a, b = groups[i], groups[j]
        if a.stream != b.stream or a.geometry != b.geometry:
            continue
        if b.first - a.last >= 2:
            pairs.append((i, j))
        elif a.first - b.last >= 2:
            pairs.append((j, i))
    return pairs


def aligned_runs(groups: list[prior.Group], keep: NDArray[np.bool_], k: int) -> NDArray[np.int64]:
    """Complete runs, (run, side A/B, constituent); never compress missing starts."""
    if k not in {1, 3, 5, 9} or len(keep) != len(groups):
        raise ValueError("Invalid run construction")
    lookup = {g.key: i for i, g in enumerate(groups)}
    if len(lookup) != len(groups):
        raise ValueError("Duplicate group identity")
    pairs = distant_pairs(groups)
    eligible = {(a, b) for a, b in pairs if keep[a] and keep[b]}
    runs = []
    for a, b in pairs:
        ga, gb = groups[a], groups[b]
        left = [lookup.get((ga.stream, ga.region, ga.start + n), -1) for n in range(k)]
        right = [lookup.get((gb.stream, gb.region, gb.start + n), -1) for n in range(k)]
        if all((i, j) in eligible for i, j in zip(left, right, strict=True)):
            runs.append((left, right))
    return np.asarray(runs, dtype=np.int64).reshape(-1, 2, k)


def distance_matrix(groups: list[prior.Group], kind: str) -> FloatArray:
    distances = np.zeros((len(groups), len(groups)), dtype=np.float64)
    if kind == "raw":
        for i, j in distant_pairs(groups):
            a, b = groups[i].values, groups[j].values
            distances[i, j] = max(
                float(np.abs(a - b).sum()) / 440640,
                float(np.abs(np.diff(a, axis=0) - np.diff(b, axis=0)).sum()) / 660960,
            )
    elif groups:
        vectors = np.stack([descriptor(g.values, kind) for g in groups])
        # One row at a time: no N*N*descriptor temporary allocation.
        for i, vector in enumerate(vectors):
            distances[i] = np.abs(vectors - vector).mean(axis=1)
    return distances


def relative_score(population: list[float], relative: str) -> tuple[float | None, str]:
    if relative not in {"R10", "R50"} or any(not math.isfinite(x) or x < 0 for x in population):
        raise ValueError("Invalid relative-score input")
    if not population:
        return None, "INSUFFICIENT_RUN_SUPPORT"
    denominator = prior.quantile(population, 0.1 if relative == "R10" else 0.5)
    assert denominator is not None
    if denominator <= EPSILON:
        return None, "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"
    return min(1.0, max(0.0, 1 - min(population) / denominator)), "MEASURED"


def run_details(
    groups: list[prior.Group],
    run: NDArray[np.int64],
    distances: FloatArray,
    energies: FloatArray,
    sample: dict[str, Any],
) -> dict[str, Any]:
    constituents = []
    for i, j in run.T:
        a, b = groups[i], groups[j]
        constituents.append(
            {
                "a": {**a.location(), "time_base": [a.base.numerator, a.base.denominator]},
                "b": {**b.location(), "time_base": [b.base.numerator, b.base.denominator]},
                "gap_fraction": str(b.first - a.last),
                "gap_seconds": float(b.first - a.last),
                "lag_fraction": str(b.first - a.first),
                "lag_seconds": float(b.first - a.first),
                "distance": float(distances[i, j]),
                "energy_a": float(energies[i]),
                "energy_b": float(energies[j]),
            }
        )
    known = None
    if sample["dataset"] == "paired" and sample["role"] == "repeat":
        known = all(
            groups[i].region == 0
            and groups[j].region == 2
            and groups[i].start == groups[j].start
            and 6 <= groups[i].start <= 20
            for i, j in run.T
        )
    return {"constituents": constituents, "known_inserted_episode_selected": known}


def measure(
    sample: dict[str, Any], groups: list[prior.Group], variants: tuple[Candidate, ...]
) -> tuple[list[dict[str, Any]], dict[str, FloatArray]]:
    """Only requested candidates are scored, crucially also in the holdout phase."""
    matrices: dict[str, FloatArray] = {}
    populations: dict[str, FloatArray] = {}
    shared: dict[tuple[str, str, int], dict[str, Any]] = {}
    rows = []
    for candidate in variants:
        row = {
            **{key: sample[key] for key in IDENTITY},
            "candidate_id": candidate.id,
            "descriptor": candidate.descriptor,
            "information": candidate.information,
            "k": candidate.k,
            "relative": candidate.relative,
            "evidence_level": "COMPONENT_LEVEL_RESEARCH",
        }
        if candidate.id == PRODUCTION:
            response, _ = prior.retained_response(prior.enumerate_pairs(groups))
            rows.append(
                {
                    **row,
                    "score": response,
                    "state": "MEASURED" if response is not None else "INSUFFICIENT_PRODUCTION",
                    "deterministic": True,
                }
            )
            continue
        key = candidate.descriptor, candidate.information, candidate.k
        if key not in shared:
            energies, keep, p25 = information(groups, candidate.information)
            runs = aligned_runs(groups, keep, candidate.k)
            if candidate.descriptor not in matrices:
                matrices[candidate.descriptor] = distance_matrix(groups, candidate.descriptor)
            distances = matrices[candidate.descriptor]
            population = (
                np.median(distances[runs[:, 0], runs[:, 1]], axis=1)
                if len(runs)
                else np.empty(0, dtype=np.float64)
            )
            populations["__".join(map(str, key))] = population
            best = int(np.argmin(population)) if len(population) else None
            shared[key] = {
                "valid_groups": len(groups),
                "eligible_groups": int(keep.sum()),
                "energy_p25": p25,
                "energy_min": float(energies.min()) if len(energies) else None,
                "energy_max": float(energies.max()) if len(energies) else None,
                "eligible_runs": len(runs),
                "d_best": float(population[best]) if best is not None else None,
                "p10_distance": prior.quantile(population.tolist(), 0.1),
                "median_distance": prior.quantile(population.tolist(), 0.5),
                "best_run": run_details(groups, runs[best], distances, energies, sample)
                if best is not None
                else None,
            }
        details = shared[key]
        score, state = relative_score(
            populations["__".join(map(str, key))].tolist(), candidate.relative
        )
        if not details["valid_groups"]:
            state = "INSUFFICIENT_VALID_GROUPS"
        elif not details["eligible_groups"]:
            state = "INSUFFICIENT_LOW_INFORMATION"
        rows.append({**row, **details, "score": score, "state": state, "deterministic": True})
    demo._json_bytes(rows)
    return rows, populations


def distribution(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        **{
            name: prior.quantile(values, q)
            for name, q in (("min", 0), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("max", 1))
        },
    }


def paired_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if row["dataset"] != "paired":
            continue
        group = grouped.setdefault((row["candidate_id"], row["source_family"]), {})
        if row["role"] not in {"reference", "repeat"} or row["role"] in group:
            raise ValueError("Matched pair isolation violated")
        group[row["role"]] = row
    result = []
    for (candidate, family), pair in sorted(grouped.items()):
        if (
            set(pair) != {"reference", "repeat"}
            or pair["reference"]["split"] != pair["repeat"]["split"]
        ):
            raise ValueError("Matched pair split or membership mismatch")
        a, b = pair["reference"]["score"], pair["repeat"]["score"]
        result.append(
            {
                "candidate_id": candidate,
                "source_family": family,
                "split": pair["reference"]["split"],
                "reference_sample_id": pair["reference"]["sample_id"],
                "repeat_sample_id": pair["repeat"]["sample_id"],
                "reference_score": a,
                "repeat_score": b,
                "delta": b - a if a is not None and b is not None else None,
            }
        )
    return result


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows or len({r["candidate_id"] for r in rows}) != 1:
        raise ValueError("Exactly one candidate summary required")
    benign_rows = [r for r in rows if r["dataset"] == "benign"]
    repeats = [r for r in rows if r["dataset"] == "paired" and r["role"] == "repeat"]
    families = sorted({r["source_family"] for r in benign_rows})
    measurable = [
        f for f in families if all(r["score"] is not None for r in rows if r["source_family"] == f)
    ]
    deltas = paired_deltas(rows)
    values = [r["delta"] for r in deltas if r["delta"] is not None]
    scores = [r["score"] for r in benign_rows if r["score"] is not None]
    repeat_scores = [r["score"] for r in repeats if r["score"] is not None]
    positive = sum(x > 0 for x in values)
    result = {
        "candidate_id": rows[0]["candidate_id"],
        "families": len(families),
        "measurable_families": len(measurable),
        "samples": len(rows),
        "measurable_samples": sum(r["score"] is not None for r in rows),
        "insufficient_reasons": dict(Counter(r["state"] for r in rows if r["score"] is None)),
        "benign_total": len(benign_rows),
        "benign": distribution(scores),
        "benign_ge075": sum(x >= 0.75 for x in scores),
        "benign_ge050": sum(x >= 0.50 for x in scores),
        "repeat": distribution(repeat_scores),
        "paired": distribution(values),
        "paired_total": len(deltas),
        "paired_positive": positive,
        "paired_zero": sum(x == 0 for x in values),
        "paired_negative": sum(x < 0 for x in values),
        "deterministic_finite": all(
            r["deterministic"] and (r["score"] is None or math.isfinite(r["score"])) for r in rows
        ),
        "by_role": {
            role: {
                "total": len(selected := [r for r in rows if r["role"] == role]),
                "families": len({r["source_family"] for r in selected}),
                "measurable_families": len(
                    {r["source_family"] for r in selected if r["score"] is not None}
                ),
                "insufficient_reasons": dict(
                    Counter(r["state"] for r in selected if r["score"] is None)
                ),
                **distribution([r["score"] for r in selected if r["score"] is not None]),
                "ge075": sum(r["score"] >= 0.75 for r in selected if r["score"] is not None),
                "ge050": sum(r["score"] >= 0.50 for r in selected if r["score"] is not None),
            }
            for role in sorted({r["role"] for r in rows})
        },
    }
    gates = {
        "all_families_measurable": bool(families) and len(measurable) == len(families),
        "paired_positive": positive >= math.ceil(0.8 * len(families))
        and len(deltas) == len(families),
        "paired_median": bool(values) and result["paired"]["median"] >= 0.10,
        "benign_median": bool(scores) and result["benign"]["median"] <= 0.60,
        "benign_high_fraction": bool(benign_rows)
        and result["benign_ge075"] <= 0.25 * len(benign_rows),
        "deterministic_finite": result["deterministic_finite"],
        "distributed_improvement": positive >= 2,
    }
    return {**result, "observation_gates": gates, "observation_ready": all(gates.values())}


def rank_key(summary: dict[str, Any]) -> tuple[Any, ...]:
    candidate = next(c for c in candidates() if c.id == summary["candidate_id"])
    if candidate.descriptor not in {"D1", "D2", "D3", "D4"}:
        raise ValueError("Controls are not selectable")
    delta, benign_median, repeat = (
        summary["paired"]["median"],
        summary["benign"]["median"],
        summary["repeat"]["median"],
    )
    return (
        not summary["observation_ready"],
        -summary["paired_positive"],
        -delta if delta is not None else 2,
        benign_median if benign_median is not None else 2,
        summary["benign_ge075"],
        -repeat if repeat is not None else 2,
        candidate.descriptor,
        candidate.k,
        candidate.id,
    )


def readiness(
    selected: dict[str, Any],
    holdout: dict[str, Any],
    combined: dict[str, Any],
    production: dict[str, Any],
    *,
    unchanged: bool,
) -> dict[str, Any]:
    gates = {
        "A_observation_ready": selected["observation_ready"],
        "B_holdout_measurable": holdout["families"] == holdout["measurable_families"] == 3,
        "C_holdout_all_positive": holdout["paired_positive"] == holdout["paired_total"] == 3,
        "D_combined_positive": combined["paired_total"] == 8 and combined["paired_positive"] >= 7,
        "E_combined_delta": combined["paired"]["median"] is not None
        and combined["paired"]["median"] >= 0.15,
        "F_combined_benign": combined["benign"]["median"] is not None
        and combined["benign"]["median"] <= 0.50,
        "G_combined_high": combined["benign_total"] == 16 and combined["benign_ge075"] <= 4,
        "H_combined_repeat": combined["repeat"]["median"] is not None
        and combined["repeat"]["median"] >= 0.70,
        "I_deterministic_finite": combined["deterministic_finite"],
        "J_production_unchanged": unchanged,
    }
    if all(gates.values()):
        disposition = "VRC2_METHOD_CANDIDATE_READY_FOR_PROTOTYPE"
    elif not combined["paired"]["n"] or not combined["benign"]["n"]:
        disposition = "NEED_MORE_DATA"
    elif (
        combined["paired"]["median"] > 0
        and combined["benign"]["median"] < production["benign"]["median"]
    ):
        disposition = "VRC2_FORMULATION_PARTIAL"
    else:
        disposition = "VRC_REDESIGN_STILL_REQUIRED"
    return {"gates": gates, "disposition": disposition}


def receipt(path: Path) -> dict[str, Any]:
    return {"sha256": benign._hash_file(path), "size": path.stat().st_size}


def check_receipt(path: Path, expected: dict[str, Any]) -> None:
    if receipt(path) != expected:
        raise ValueError(f"Evidence changed: {path.name}")


def validate_inventory(samples: list[dict[str, Any]]) -> None:
    keys = [(s["dataset"], s["sample_id"]) for s in samples]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate input sample")
    primary = [s for s in samples if s["dataset"] == "benign"]
    families = sorted({s["source_family"] for s in primary})
    if len(primary) != 16 or families != [f"video-{n:02}" for n in range(1, 9)]:
        raise ValueError("Accepted 16-video / 8-family inventory required")
    for family in families:
        split = "holdout_benign" if family[-2:] in {"03", "06", "08"} else "observation"
        members = [s for s in samples if s["source_family"] == family and s["dataset"] != "demo"]
        if len(members) != 4 or any(s["split"] != split for s in members):
            raise ValueError("Frozen source-family split/membership changed")
        if {s["role"] for s in members if s["dataset"] == "paired"} != {"reference", "repeat"}:
            raise ValueError("Accepted matched pairs required")
        if {s["sample_id"] for s in members if s["dataset"] == "benign"} != {
            f"{family}-reference",
            f"{family}-processed",
        }:
            raise ValueError("Accepted benign IDs changed")


def accepted_inputs(
    benign_root: Path, demo_root: Path, paired_root: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior.verify_freeze(paired_root)
    prepared = benign._sealed(paired_root, "prepared.json")
    for key, name in (
        ("inventory_sha256", "input/inventory.json"),
        ("matrix_sha256", "research-matrix.json"),
        ("baseline_reproduction_sha256", "baseline-reproduction.json"),
        ("paired_design_sha256", "paired-design.json"),
        ("paired_qa_sha256", "paired-qa.json"),
    ):
        benign._sealed(paired_root, name)
        if prepared[key] != benign._hash_file(paired_root / name):
            raise ValueError("Accepted PR74 prepared binding changed")
    complete = benign._sealed(paired_root, "complete.json")
    for name, expected in complete["artifacts"].items():
        check_receipt(demo._owned_path(paired_root, name), expected)
    old = benign._sealed(paired_root, "input/inventory.json")
    current = prior.inventory(benign_root, demo_root)
    for sample in current:
        matches = [
            s
            for s in old
            if (s["dataset"], s["sample_id"]) == (sample["dataset"], sample["sample_id"])
        ]
        if matches != [sample]:
            raise ValueError("Accepted benign/demo input differs from PR74")
    samples = current + [s for s in old if s["dataset"] == "paired"]
    validate_inventory(samples)
    for sample in samples:
        path = Path(sample["path"])
        demo._external_directory(path)
        check_receipt(path, {"sha256": sample["sha256"], "size": sample["size_bytes"]})
        if sample["dataset"] == "paired":
            source = next(
                s
                for s in current
                if s["dataset"] == "benign" and s["sample_id"] == sample["source_sample_id"]
            )
            if sample["source_sha256"] != source["sha256"] or sample["split"] != source["split"]:
                raise ValueError("Matched source binding changed")
        name = f"artifacts/{sample['dataset']}-{sample['sample_id']}-production.json"
        expected = complete["artifacts"][name]
        sample["accepted_production"] = demo._read_json(demo._owned_path(paired_root, name))
        sample["accepted_production_receipt"] = expected
    sources = {}
    for root, names in (
        (benign_root, ("manifest.json", "freeze.json", "source-plan.json", "source-manifest.json")),
        (demo_root, ("manifest.json", "freeze.json")),
        (
            paired_root,
            (
                "prepared.json",
                "complete.json",
                "input/inventory.json",
                "paired-design.json",
                "paired-qa.json",
                "freeze.json",
                "research-matrix.json",
            ),
        ),
    ):
        for name in names:
            sources[str(root / name)] = receipt(root / name)
    return samples, sources


def cache_name(sample: dict[str, Any]) -> str:
    return f"{sample['dataset']}-{sample['sample_id']}"


def decode_sample(sample: dict[str, Any], root: Path) -> tuple[list[prior.Group], dict[str, Any]]:
    path = Path(sample["path"])
    expected = {"sha256": sample["sha256"], "size": sample["size_bytes"]}
    check_receipt(path, expected)
    with TemporaryDirectory(
        prefix="vrc2-decode-", dir=demo._owned_path(root, "artifacts")
    ) as temporary:
        request = prior.decode_request(path, Path(temporary) / "dense", sample["facts"])
        groups = prior.groups_from_request(request)
        metrics = VideoRepeatedContentCorrespondenceAnalyzer().analyze(request).raw_metrics
        prior.verify_reproduction(prior.enumerate_pairs(groups), metrics)
    check_receipt(path, expected)
    return groups, metrics


def prepare(workspace: Path, benign_root: Path, demo_root: Path, paired_root: Path) -> None:
    root = demo._external_directory(workspace)
    for source in (benign_root, demo_root, paired_root):
        source = demo._external_directory(source)
        if root.is_relative_to(source) or source.is_relative_to(root):
            raise ValueError("Output overlaps accepted source workspace")
    samples, sources = accepted_inputs(benign_root, demo_root, paired_root)
    root.mkdir(parents=True, exist_ok=True)
    for directory in (
        "input",
        "input/groups",
        "freeze",
        "observation",
        "holdout",
        "demo",
        "tables",
        "logs",
        "artifacts",
        "review",
    ):
        demo._owned_path(root, directory).mkdir(exist_ok=directory == "input")
    benign._seal(root, "research-matrix.json", research_matrix())
    benign._seal(root, "input/inventory.json", samples)
    benign._seal(
        root,
        "freeze/design.json",
        {
            "baseline": BASELINE,
            "version": VERSION,
            "created_at": benign._now(),
            "policy": demo._policy(),
            "environment": demo._environment(),
            "code": fingerprint(),
            "matrix_sha256": benign._hash_file(root / "research-matrix.json"),
            "inventory_sha256": benign._hash_file(root / "input/inventory.json"),
            "source_receipts": sources,
        },
    )
    prior.write_csv(
        root / "tables/input-inventory.csv",
        [
            {
                k: s.get(k)
                for k in (
                    *IDENTITY,
                    "path",
                    "sha256",
                    "size_bytes",
                    "source_sample_id",
                    "source_sha256",
                    "evidence_level",
                )
            }
            for s in samples
        ],
    )
    records = []
    for sample in samples:
        groups, metrics = decode_sample(sample, root)
        if metrics != sample["accepted_production"] or (
            "prior_metrics" in sample and metrics != sample["prior_metrics"]
        ):
            raise ValueError("STOP: exact production-control reproduction differs")
        stem = f"input/groups/{cache_name(sample)}"
        path = demo._owned_path(root, stem + ".npz")
        with path.open("xb") as stream:
            np.savez_compressed(
                stream,
                grids=np.asarray([g.values for g in groups], dtype=np.int64).reshape(-1, 4, 432),
            )
        metadata = [
            {
                "stream": g.stream,
                "region": g.region,
                "start": g.start,
                "ticks": list(g.ticks),
                "base": [g.base.numerator, g.base.denominator],
                "geometry": list(g.geometry),
            }
            for g in groups
        ]
        benign._seal(
            root,
            stem + ".json",
            {
                "groups": metadata,
                "grid_receipt": receipt(path),
                "production_metrics": metrics,
                "source_sha256": sample["sha256"],
            },
        )
        records.append(
            {
                **{k: sample[k] for k in IDENTITY},
                "max_error": 0,
                "full_raw_metrics_equal": True,
                "response": prior.retained_response(prior.enumerate_pairs(groups))[0],
                "cache": stem + ".json",
                "cache_receipt": receipt(root / (stem + ".json")),
            }
        )
        print(f"baseline exact: {cache_name(sample)}", flush=True)
    qa = []
    for family in sorted({s["source_family"] for s in samples if s["dataset"] == "paired"}):
        pair = {
            s["role"]: s
            for s in samples
            if s["dataset"] == "paired" and s["source_family"] == family
        }
        qa.append(
            {
                "source_family": family,
                **prior.verify_control_pixels(pair["reference"], pair["repeat"], root),
            }
        )
    if qa != benign._sealed(paired_root, "paired-qa.json"):
        raise ValueError("STOP: accepted paired pixel QA differs")
    benign._seal(root, "baseline-reproduction.json", records)
    benign._seal(root, "input/paired-qa.json", qa)
    verify_freeze(root)
    benign._seal(
        root,
        "freeze/prepared.json",
        {
            "completed_at": benign._now(),
            "baseline_receipt": receipt(root / "baseline-reproduction.json"),
            "design_receipt": receipt(root / "freeze/design.json"),
            "paired_qa_receipt": receipt(root / "input/paired-qa.json"),
        },
    )


def verify_freeze(root: Path) -> dict[str, Any]:
    demo._external_directory(root)
    matrix = benign._sealed(root, "research-matrix.json")
    freeze: dict[str, Any] = benign._sealed(root, "freeze/design.json")
    if matrix != research_matrix() or freeze["matrix_sha256"] != benign._hash_file(
        root / "research-matrix.json"
    ):
        raise ValueError("Frozen matrix changed")
    if (
        freeze["policy"] != demo._policy()
        or freeze["environment"] != demo._environment()
        or freeze["code"] != fingerprint()
    ):
        raise ValueError("Production/environment/research code freeze changed")
    if freeze["inventory_sha256"] != benign._hash_file(root / "input/inventory.json"):
        raise ValueError("Frozen inventory binding changed")
    for path, expected in freeze["source_receipts"].items():
        check_receipt(Path(path), expected)
    return freeze


def load_groups(root: Path, sample: dict[str, Any]) -> list[prior.Group]:
    records = benign._sealed(root, "baseline-reproduction.json")
    record = next(
        r
        for r in records
        if (r["dataset"], r["sample_id"]) == (sample["dataset"], sample["sample_id"])
    )
    meta_path = demo._owned_path(root, record["cache"])
    check_receipt(meta_path, record["cache_receipt"])
    meta = benign._sealed(root, record["cache"])
    grid_path = meta_path.with_suffix(".npz")
    demo._external_directory(grid_path)
    check_receipt(grid_path, meta["grid_receipt"])
    check_receipt(Path(sample["path"]), {"sha256": sample["sha256"], "size": sample["size_bytes"]})
    with np.load(grid_path, allow_pickle=False) as archive:
        values = archive["grids"]
    if (
        values.dtype != np.dtype("int64")
        or values.shape != (len(meta["groups"]), 4, 432)
        or len(values) > 87
    ):
        raise ValueError("Invalid cached production grid")
    if meta["source_sha256"] != sample["sha256"]:
        raise ValueError("Cached source binding changed")
    return [
        prior.Group(
            g["stream"],
            g["region"],
            g["start"],
            tuple(g["ticks"]),
            Fraction(*g["base"]),
            tuple(g["geometry"]),
            v,
        )
        for g, v in zip(meta["groups"], values, strict=True)
    ]


def phase_samples(samples: list[dict[str, Any]], phase: str) -> list[dict[str, Any]]:
    if phase == "demo":
        return [s for s in samples if s["dataset"] == "demo"]
    if phase not in {"observation", "holdout"}:
        raise ValueError("Unknown phase")
    split = "observation" if phase == "observation" else "holdout_benign"
    return [s for s in samples if s["dataset"] in {"benign", "paired"} and s["split"] == split]


def selected_candidate(root: Path) -> tuple[Candidate, dict[str, Any]]:
    selected = benign._sealed(root, "selected-candidate.json")
    for key, name in (
        ("matrix_receipt", "research-matrix.json"),
        ("observation_receipt", "observation/results.json"),
        ("ranking_receipt", "observation/ranking.json"),
        ("freeze_receipt", "freeze/design.json"),
    ):
        check_receipt(root / name, selected[key])
    candidate = next(c for c in candidates() if c.id == selected["candidate"]["id"])
    ranked = benign._sealed(root, "observation/ranking.json")
    if (
        candidate.descriptor not in {"D1", "D2", "D3", "D4"}
        or asdict(candidate) != selected["candidate"]
        or ranked[0] != selected["observation_metrics"]
        or ranked[0]["candidate_id"] != candidate.id
        or selected["code"] != fingerprint()
        or selected["formula"] != research_matrix()
        or selected["observation_ready"] != ranked[0]["observation_ready"]
        or selected["holdout_consumed"] is not False
    ):
        raise ValueError("Selected candidate changed after observation")
    return candidate, selected


def evaluate_phase(workspace: Path, phase: str) -> list[dict[str, Any]]:
    root = demo._external_directory(workspace)
    verify_freeze(root)
    prepared = benign._sealed(root, "freeze/prepared.json")
    for key, name in (
        ("baseline_receipt", "baseline-reproduction.json"),
        ("design_receipt", "freeze/design.json"),
        ("paired_qa_receipt", "input/paired-qa.json"),
    ):
        check_receipt(root / name, prepared[key])
    if phase == "observation":
        if (root / "selected-candidate.json").exists() or (root / "holdout/run.json").exists():
            raise ValueError("Observation cannot run after selection/holdout")
        variants = candidates()
    else:
        candidate, _ = selected_candidate(root)  # Must succeed BEFORE reading any holdout cache.
        variants = (candidate, next(c for c in candidates() if c.id == PRODUCTION))
        if phase == "demo":
            decision = benign._sealed(root, "holdout/decision.json")
            check_receipt(root / "selected-candidate.json", decision["selection_receipt"])
            check_receipt(root / "holdout/results.json", decision["holdout_receipt"])
    samples = phase_samples(benign._sealed(root, "input/inventory.json"), phase)
    benign._seal(
        root,
        f"{phase}/run.json",
        {
            "started_at": benign._now(),
            "candidates": [c.id for c in variants],
            "samples": [cache_name(s) for s in samples],
            "selection_receipt": receipt(root / "selected-candidate.json")
            if phase != "observation"
            else None,
            "code": fingerprint(),
            "prepared_receipt": receipt(root / "freeze/prepared.json"),
        },
    )
    rows = []
    for sample in samples:
        groups = load_groups(root, sample)
        measured, populations = measure(sample, groups, variants)
        replay, replay_populations = measure(sample, groups, variants)
        if measured != replay or any(
            not np.array_equal(v, replay_populations[k]) for k, v in populations.items()
        ):
            raise ValueError("Non-deterministic redesigned research outcome")
        name = f"{phase}/{cache_name(sample)}"
        benign._seal(root, name + ".json", measured)
        with demo._owned_path(root, name + "-populations.npz").open("xb") as stream:
            np.savez_compressed(stream, allow_pickle=False, **populations)
        rows.extend(measured)
        print(
            f"{phase}: {cache_name(sample)}, {len(variants)} candidates, replay exact", flush=True
        )
    verify_freeze(root)
    benign._seal(root, f"{phase}/results.json", rows)
    return rows


def freeze_selection(root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if any(r["split"] != "observation" or r["dataset"] == "demo" for r in rows):
        raise ValueError("Holdout/demo outcomes cannot enter observation selection")
    if (root / "holdout/run.json").exists():
        raise ValueError("Holdout was consumed before candidate freeze")
    summaries = [summarize([r for r in rows if r["candidate_id"] == c.id]) for c in candidates()]
    ranked = sorted(
        [r for r in summaries if r["candidate_id"] not in {PRODUCTION, RAW}], key=rank_key
    )
    benign._seal(root, "observation/summaries.json", summaries)
    benign._seal(root, "observation/ranking.json", ranked)
    best = ranked[0]
    candidate = next(c for c in candidates() if c.id == best["candidate_id"])
    selected = {
        "frozen_at": benign._now(),
        "candidate": asdict(candidate),
        "observation_ready": best["observation_ready"],
        "observation_metrics": best,
        "formula": research_matrix(),
        "code": fingerprint(),
        "matrix_receipt": receipt(root / "research-matrix.json"),
        "observation_receipt": receipt(root / "observation/results.json"),
        "ranking_receipt": receipt(root / "observation/ranking.json"),
        "freeze_receipt": receipt(root / "freeze/design.json"),
        "holdout_consumed": False,
    }
    benign._seal(root, "selected-candidate.json", selected)
    return selected


def observation(root: Path) -> dict[str, Any]:
    rows = evaluate_phase(root, "observation")
    return freeze_selection(root, rows)


def holdout(root: Path) -> dict[str, Any]:
    rows = evaluate_phase(root, "holdout")
    candidate, selected = selected_candidate(root)
    observation_rows = benign._sealed(root, "observation/results.json")
    combined_rows = [
        r for r in observation_rows + rows if r["candidate_id"] in {candidate.id, PRODUCTION}
    ]
    combined = summarize([r for r in combined_rows if r["candidate_id"] == candidate.id])
    production = summarize([r for r in combined_rows if r["candidate_id"] == PRODUCTION])
    held = summarize([r for r in rows if r["candidate_id"] == candidate.id])
    verify_freeze(root)
    decision = {
        **readiness(selected, held, combined, production, unchanged=True),
        "selection_receipt": receipt(root / "selected-candidate.json"),
        "holdout_receipt": receipt(root / "holdout/results.json"),
        "frozen_at": benign._now(),
        "holdout": held,
        "combined": combined,
        "production": production,
    }
    benign._seal(root, "holdout/decision.json", decision)
    return decision


def flat_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        **{k: v for k, v in summary.items() if k not in {"benign", "repeat", "paired"}},
        **{
            f"{kind}_{key}": value
            for kind in ("benign", "repeat", "paired")
            for key, value in summary[kind].items()
        },
    }


def finish(root: Path) -> dict[str, Any]:
    demo_rows = evaluate_phase(root, "demo")
    candidate, selected = selected_candidate(root)
    decision = benign._sealed(root, "holdout/decision.json")
    obs = benign._sealed(root, "observation/results.json")
    held = benign._sealed(root, "holdout/results.json")
    summaries = benign._sealed(root, "observation/summaries.json")
    table = root / "tables"
    prior.write_csv(
        table / "observation-candidate-summary.csv", [flat_summary(s) for s in summaries]
    )
    prior.write_csv(table / "observation-paired-deltas.csv", paired_deltas(obs))
    prior.write_csv(table / "holdout-results.csv", held)
    prior.write_csv(table / "holdout-paired-deltas.csv", paired_deltas(held))
    combined = [r for r in obs + held if r["candidate_id"] == candidate.id]
    prior.write_csv(table / "combined-selected-candidate.csv", combined)
    prior.write_csv(table / "demo-diagnostics.csv", demo_rows)
    prior.write_csv(
        table / "selected-run-details.csv",
        [r for r in combined + demo_rows if r["candidate_id"] == candidate.id],
    )
    prior.write_csv(
        table / "observation-ranking.csv",
        [
            {"rank": i, **flat_summary(s)}
            for i, s in enumerate(benign._sealed(root, "observation/ranking.json"), 1)
        ],
    )
    family_rows = []
    for cid in [c.id for c in candidates()]:
        selected_rows = [r for r in obs if r["candidate_id"] == cid]
        for family in sorted({r["source_family"] for r in selected_rows}):
            family_rows.append(
                {
                    "source_family": family,
                    **flat_summary(
                        summarize([r for r in selected_rows if r["source_family"] == family])
                    ),
                }
            )
    prior.write_csv(table / "observation-source-family.csv", family_rows)
    for field, filename in (
        ("descriptor", "descriptor-comparison.csv"),
        ("information", "informativeness-comparison.csv"),
        ("k", "run-length-comparison.csv"),
        ("relative", "relative-score-comparison.csv"),
    ):
        # Full per-candidate rows preserve family denominators; no pseudo-replicated pooled N.
        prior.write_csv(
            table / filename,
            [
                {
                    "comparison_axis": field,
                    "axis_value": getattr(c, field),
                    **asdict(c),
                    **flat_summary(s),
                }
                for c in candidates()
                if c.descriptor in {"D1", "D2", "D3", "D4"}
                for s in summaries
                if s["candidate_id"] == c.id
            ],
        )
    summary = {
        "task": "STAGE12-DIPLOMA-VRC-REDESIGN-RESEARCH-SPRINT1",
        "baseline": BASELINE,
        "evidence_level": "COMPONENT_LEVEL_RESEARCH",
        "production_changed": False,
        "max_baseline_repro_error": 0,
        "baseline_samples": len(benign._sealed(root, "baseline-reproduction.json")),
        "matrix_variants": 50,
        "matrix_sha256": benign._hash_file(root / "research-matrix.json"),
        "candidate_freeze_sha256": benign._hash_file(root / "selected-candidate.json"),
        "selected_candidate": asdict(candidate),
        "observation": selected["observation_metrics"],
        "observation_ready_count": sum(
            s["observation_ready"] for s in summaries if s["candidate_id"] not in {PRODUCTION, RAW}
        ),
        **decision,
        "demo": demo_rows,
    }
    benign._seal(root, "tables/summary.json", summary)
    verify_freeze(root)
    artifacts = {
        p.relative_to(root).as_posix(): receipt(p)
        for folder in ("tables", "observation", "holdout", "demo")
        for p in sorted((root / folder).glob("*"))
        if p.is_file()
    }
    benign._seal(
        root,
        "complete.json",
        {
            "completed_at": benign._now(),
            "artifacts": artifacts,
            "selection_receipt": receipt(root / "selected-candidate.json"),
        },
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "observation", "holdout", "demo"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--benign", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--paired", type=Path)
    args = parser.parse_args()
    root = demo._external_directory(args.workspace)
    if args.command == "prepare":
        if args.benign is None or args.demo is None or args.paired is None:
            parser.error("prepare requires --benign, --demo, --paired")
        prepare(root, args.benign, args.demo, args.paired)
    elif args.command == "observation":
        chosen = observation(root)
        print(
            demo._json_bytes(
                {"candidate": chosen["candidate"], "observation_ready": chosen["observation_ready"]}
            ).decode()
        )
    elif args.command == "holdout":
        print(demo._json_bytes(holdout(root)).decode())
    else:
        print(demo._json_bytes({"disposition": finish(root)["disposition"]}).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
