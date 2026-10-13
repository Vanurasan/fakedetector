"""Frozen component-level VRC diagnostics, never a production policy.

Run ``prepare --workspace ABS_EXTERNAL --benign ABS_EXTERNAL --demo ABS_EXTERNAL``,
then ``evaluate --workspace ABS_EXTERNAL``. Preparation verifies the old file-level
evidence before any alternative outcomes, freezes the matrix, and creates matched
probes twice. Evaluation uses the production dense decoder and descriptor; only
candidate enumeration, retention and descriptive statistics are research code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import statistics
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
from numpy.typing import NDArray

from fakedetector._generated_artifact_budget import _GeneratedArtifactBudget
from fakedetector.analyzers._experimental_common import _ExperimentalSettings
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._video_experimental import (
    VideoRepeatedContentCorrespondenceAnalyzer,
    _block_descriptor,
    _dense_inputs,
)
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.domain import MediaType
from fakedetector.lifecycle._assessment import _video_repetition_response
from fakedetector.preprocessing._media_tools import (
    decode_dense_window,
    probe_timing_stream,
    select_timing_regions,
)
from fakedetector.preprocessing._models import (
    ForensicManifest,
    ForensicRepresentation,
    RepresentationProvenance,
)
from scripts import diploma_benign_validation as benign
from scripts import diploma_demo_evaluation as demo

VERSION = "vrc-targeted-research-1.0.0"
BASELINE = "c32de18326f020b3bc362dc5eff47042376616cb"
GATES = ("T0_CURRENT", "T1_GAP_0_5S", "T2_GAP_1S", "T3_GAP_2S", "T4_CROSS_REGION")
POOLS = (
    "strongest",
    "second",
    "third",
    "fifth",
    "top3_mean",
    "top5_mean",
    "p99",
    "p95",
    "median",
    "greedy_disjoint_top3_mean",
)
QUANTILES = {"min": 0, "p01": 0.01, "p05": 0.05, "p25": 0.25, "median": 0.5, "p75": 0.75, "max": 1}


def research_matrix() -> dict[str, Any]:
    return {
        "version": VERSION,
        "evidence_level": "COMPONENT_LEVEL_RESEARCH",
        "gates": [
            {"id": GATES[0], "rule": "production admissibility"},
            {"id": GATES[1], "rule": "T0 and B.first-A.last >= 1/2 second"},
            {"id": GATES[2], "rule": "T0 and B.first-A.last >= 1 second"},
            {"id": GATES[3], "rule": "T0 and B.first-A.last >= 2 seconds"},
            {"id": GATES[4], "rule": "T0 and different dense regions"},
        ],
        "variants": [
            {"id": f"{gate}__{pool}", "gate": gate, "pool": pool}
            for gate in GATES
            for pool in POOLS
        ],
        "quantile": "linear interpolation at (n-1)*p",
        "top_k": "undefined unless at least k eligible pairs; exact k mean",
        "greedy": (
            "stable joint-distance order; no identical group reused; overlapping frames allowed"
        ),
        "ties": "first in production window/start/combinations order",
        "pair_output": "complete integer pair ledger; <=3741 pairs/sample",
        "extreme_value": {
            "sizes": [1, 4, 16, 64, 256, 1024],
            "replicates": 16,
            "seed": "sha256(sample_id|gate|replicate), first 16 hex digits",
            "order": "PCG64 permutation; nested subsets; full set appended",
        },
        "paired_recipe": {
            "source_frames": [6, 24],
            "destination_frames": [246, 264],
            "input_frames": 288,
            "input_rate": [24, 1],
            "length_seconds": 0.75,
            "separation_seconds": 10,
        },
        "ranking": [
            "measurable_families descending",
            "supported_samples descending",
            "benign_median ascending",
            "benign_ge095 ascending",
            "positive descending",
            "family_reduction_count descending",
            "simplicity ascending",
            "id",
        ],
        "research_readiness_only": {
            "measurable_families": 8,
            "supported_benign_samples": 16,
            "positive_pairs_min": 7,
            "median_reduction_min": 0.05,
            "benign_median_below": 0.95,
            "family_reduction_count": 8,
            "greedy_supported_pairs": 3,
            "meaning": "predeclared research screen, NOT production thresholds/calibration",
        },
        "production_change": False,
    }


def verify_matrix(root: Path) -> dict[str, Any]:
    value: dict[str, Any] = benign._sealed(root, "research-matrix.json")
    if value != research_matrix():
        raise ValueError("Frozen research matrix changed")
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    demo._external_directory(path.parent)
    demo._external_directory(path)
    # Validate recursively before creating output, including cells with nested lists.
    demo._json_bytes(rows)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: "null"
                    if v is None
                    else demo._json_bytes(v).decode().strip()
                    if isinstance(v, (dict, list))
                    else v
                    for k, v in row.items()
                }
            )


@dataclass(frozen=True)
class Group:
    stream: int
    region: int
    start: int
    ticks: tuple[int, ...]
    base: Fraction
    geometry: tuple[int, ...]
    values: NDArray[np.int64]

    @property
    def first(self) -> Fraction:
        return self.ticks[0] * self.base

    @property
    def last(self) -> Fraction:
        return self.ticks[-1] * self.base

    @property
    def key(self) -> tuple[int, int, int]:
        return self.stream, self.region, self.start

    def location(self) -> dict[str, Any]:
        return {"region": self.region, "start_ordinal": self.start, "pts_ticks": list(self.ticks)}


@dataclass(frozen=True)
class Pair:
    a: Group
    b: Group
    color: int
    delta: int
    temporal_a: int
    temporal_b: int

    @property
    def distance(self) -> float:
        return max(self.color / 440640, self.delta / 660960)

    @property
    def similarity(self) -> float:
        return 1 - self.distance

    @property
    def gap(self) -> Fraction:
        return self.b.first - self.a.last

    def production_record(self) -> dict[str, Any]:
        return {
            "stream_index": self.a.stream,
            "a": self.a.location(),
            "b": self.b.location(),
            "color_numerator": self.color,
            "delta_numerator": self.delta,
            "temporal_a_numerator": self.temporal_a,
            "temporal_b_numerator": self.temporal_b,
        }

    def row(self) -> dict[str, Any]:
        same = self.a.region == self.b.region
        return {
            **self.production_record(),
            "time_base_a": [self.a.base.numerator, self.a.base.denominator],
            "time_base_b": [self.b.base.numerator, self.b.base.denominator],
            "gap_fraction": str(self.gap),
            "gap_seconds": float(self.gap),
            "start_separation_seconds": float(self.b.first - self.a.first),
            "same_region": same,
            "ordinal_separation": abs(self.a.start - self.b.start) if same else None,
            "color_distance": self.color / 440640,
            "delta_distance": self.delta / 660960,
            "joint_distance": self.distance,
            "joint_similarity": self.similarity,
        }


def groups_from_request(request: AnalyzerRequest) -> list[Group]:
    groups = []
    for window in _dense_inputs(request):
        if window.pixels.pixels.shape[1] < 9 or window.pixels.pixels.shape[2] < 16:
            continue
        pixels = np.asarray(request.read_numeric(window.pixels.pixels), dtype=np.uint8)
        descriptors = np.stack([_block_descriptor(frame) for frame in pixels])
        assert window.timing.data is not None
        timing = np.asarray(request.read_numeric(window.timing.data), dtype=np.int64)
        for start in range(max(0, len(descriptors) - 3)):
            selected = timing[start : start + 4]
            ticks = tuple(int(row[0]) for row in selected)
            if not np.all(selected[:, 4] & 1) or any(
                a >= b for a, b in zip(ticks, ticks[1:], strict=False)
            ):
                continue
            groups.append(
                Group(
                    window.stream.stream_index,
                    window.timing.region,
                    start,
                    ticks,
                    Fraction(
                        window.stream.time_base.numerator, window.stream.time_base.denominator
                    ),
                    (
                        window.pixels.native_width,
                        window.pixels.native_height,
                        *window.pixels.pixels.shape[1:],
                    ),
                    descriptors[start : start + 4],
                )
            )
    return groups


def enumerate_pairs(groups: list[Group]) -> list[Pair]:
    """Independent admissibility/arithmetic, preserving production traversal ties."""
    pairs = []
    for first, second in combinations(groups, 2):
        if first.stream != second.stream or first.geometry != second.geometry:
            continue
        if first.region == second.region and abs(first.start - second.start) < 5:
            continue
        if first.last < second.first:
            a, b = first, second
        elif second.last < first.first:
            a, b = second, first
        else:
            continue
        da, db = np.diff(a.values, axis=0), np.diff(b.values, axis=0)
        pairs.append(
            Pair(
                a,
                b,
                int(np.abs(a.values - b.values).sum()),
                int(np.abs(da - db).sum()),
                int(np.abs(da).sum()),
                int(np.abs(db).sum()),
            )
        )
    return pairs


def retained_response(pairs: list[Pair]) -> tuple[float | None, dict[str, Any]]:
    minima = {
        "minimum_color_pair": min(pairs, key=lambda p: p.color) if pairs else None,
        "minimum_delta_pair": min(pairs, key=lambda p: p.delta) if pairs else None,
    }
    return (
        max(p.similarity for p in minima.values() if p is not None) if pairs else None,
        {k: p.production_record() if p else None for k, p in minima.items()},
    )


def eligible(pair: Pair, gate: str) -> bool:
    if gate == GATES[0]:
        return True
    if gate == GATES[4]:
        return pair.a.region != pair.b.region
    gaps = {GATES[1]: Fraction(1, 2), GATES[2]: Fraction(1), GATES[3]: Fraction(2)}
    return pair.gap >= gaps[gate]


def quantile(values: list[float], p: float) -> float | None:
    benign._finite(values + [p])
    if not 0 <= p <= 1:
        raise ValueError("Quantile probability outside unit interval")
    if not values:
        return None
    ordered = sorted(values)
    at = (len(ordered) - 1) * p
    left, right = math.floor(at), math.ceil(at)
    return ordered[left] + (at - left) * (ordered[right] - ordered[left])


def greedy_disjoint(pairs: list[Pair]) -> list[Pair]:
    used: set[tuple[int, int, int]] = set()
    selected = []
    for pair in sorted(pairs, key=lambda p: p.distance):
        if pair.a.key in used or pair.b.key in used:
            continue
        selected.append(pair)
        used.update((pair.a.key, pair.b.key))
        if len(selected) == 3:
            break
    return selected


def pooling(pairs: list[Pair]) -> dict[str, Any]:
    values = sorted((p.similarity for p in pairs), reverse=True)
    disjoint = greedy_disjoint(pairs)
    return {
        "eligible_pairs": len(pairs),
        **{
            key: values[k - 1] if len(values) >= k else None
            for key, k in (("strongest", 1), ("second", 2), ("third", 3), ("fifth", 5))
        },
        **{
            f"top{k}_mean": statistics.fmean(values[:k]) if len(values) >= k else None
            for k in (3, 5)
        },
        **{key: quantile(values, q) for key, q in (("p99", 0.99), ("p95", 0.95), ("median", 0.5))},
        "greedy_disjoint_top3_mean": statistics.fmean(p.similarity for p in disjoint)
        if disjoint
        else None,
        "disjoint_support": len(disjoint),
    }


def verify_reproduction(pairs: list[Pair], metrics: dict[str, Any]) -> float:
    response, minima = retained_response(pairs)
    if (
        any(minima[key] != metrics[key] for key in minima)
        or len(pairs) != metrics["eligible_pairs"]
    ):
        raise ValueError("STOP: independent VRC pair reproduction mismatch")
    production = _video_repetition_response(metrics)
    if response != production:
        raise ValueError("STOP: independent VRC response reproduction mismatch")
    return 0.0


def decode_request(source: Path, target: Path, facts: dict[str, Any]) -> AnalyzerRequest:
    """Exact existing producer functions; a component path, not intake/lifecycle E2E."""
    demo._external_directory(target)
    target.mkdir(parents=True)
    stream = probe_timing_stream(source, "video", frames=True, timeout=15)
    if stream is None:
        raise ValueError("Missing video stream")
    config = demo._config(target)
    budget = _GeneratedArtifactBudget(_ConfigSnapshot.capture(config), MediaType.VIDEO)
    provenance = RepresentationProvenance(
        producer="ffprobe_timing",
        producer_version="1",
        profile="bounded_packets_frames",
        profile_version="1",
    )
    dense_provenance = RepresentationProvenance(
        producer="ffmpeg_dense",
        producer_version="1",
        profile="rgb24_bilinear",
        profile_version="1",
    )
    representations = [ForensicRepresentation(provenance=provenance, facts=stream)]
    artifacts = []
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise ValueError("Existing FFmpeg required")
    for region, interval in enumerate(select_timing_regions(stream)):
        pixels_path = target / f"pixels-{region}.raw"
        dense, records, values = decode_dense_window(
            source,
            pixels_path,
            stream,
            interval,
            region,
            executable=executable,
            artifact_budget=budget,
            timeout=30,
        )
        assert records.data is not None
        records_path = target / f"timing-{region}.raw"
        with budget.open_output(records_path) as output:
            output.write(values.tobytes())
        for descriptor, path in ((dense.pixels, pixels_path), (records.data, records_path)):
            artifacts.append(
                AnalyzerArtifactInput(
                    artifact_id=descriptor.artifact_id,
                    artifact_type="numeric",
                    format="forensic_raw",
                    content=_ReadOnlyAnalyzerInput(path),
                )
            )
        representations.extend(
            ForensicRepresentation(provenance=dense_provenance, facts=item)
            for item in (records, dense)
        )
    file_facts = _AnalyzerFileFacts.model_validate(
        {k: v for k, v in facts.items() if k != "original_name"}
    )
    manifest = ForensicManifest(
        source_sha256=file_facts.sha256,
        media_type=MediaType.VIDEO,
        representations=tuple(representations),
    )
    return AnalyzerRequest(
        analysis_id="vrc-component-research",
        media_type=MediaType.VIDEO,
        file_facts=file_facts,
        source=_ReadOnlyAnalyzerInput(source),
        settings=_ExperimentalSettings(),
        timeout_seconds=120,
        artifacts=tuple(artifacts),
        metadata={"forensic": manifest.to_metadata()},
    )


def sample_pairs(sample: dict[str, Any], root: Path) -> tuple[list[Pair], dict[str, Any]]:
    source = Path(sample["path"])
    if benign._hash_file(source) != sample["sha256"]:
        raise ValueError("Input media hash mismatch")
    with TemporaryDirectory(prefix="vrc-decode-", dir=root / "artifacts") as temporary:
        request = decode_request(source, Path(temporary) / "decode", sample["facts"])
        pairs = enumerate_pairs(groups_from_request(request))
        metrics = VideoRepeatedContentCorrespondenceAnalyzer().analyze(request).raw_metrics
        verify_reproduction(pairs, metrics)
    if benign._hash_file(source) != sample["sha256"]:
        raise ValueError("Input media changed during decode")
    return pairs, metrics


def inventory(benign_root: Path, demo_root: Path) -> list[dict[str, Any]]:
    result = []
    for dataset, root, manifest in (
        ("benign", benign_root, benign.load_manifest(benign_root)),
        ("demo", demo_root, demo.load_manifest(demo_root)),
    ):
        for row in manifest["samples"]:
            if row["media_type"] != "video":
                continue
            prior_path = demo._owned_path(root, f"results/{row['sample_id']}.json")
            prior = demo._read_json(prior_path)
            metrics = next(
                a["raw_metrics"] for a in prior["analyzers"] if a["analyzer_id"] == benign.VRC
            )
            result.append(
                {
                    **row,
                    "dataset": dataset,
                    "source_family": row.get("source_family", row.get("pair_id")),
                    "path": str(demo._owned_path(root, row["filename"])),
                    "facts": prior["file"],
                    "prior_metrics": metrics,
                    "prior_result_path": str(prior_path),
                    "prior_result_sha256": benign._hash_file(prior_path),
                    "prior_evidence_level": "FILE_LEVEL_E2E",
                    "evidence_level": "COMPONENT_LEVEL_RESEARCH",
                }
            )
    return result


def paired_sources(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    references = [
        s for s in samples if s["dataset"] == "benign" and s["role"] == "BENIGN_REFERENCE"
    ]
    families = [s["source_family"] for s in references]
    if len(families) != len(set(families)) or not families:
        raise ValueError("Exactly one benign reference per source family required")
    return sorted(references, key=lambda s: s["source_family"])


def paired_command(source: str, output: str, *, repeat: bool) -> list[str]:
    middle = "6:end_frame=24" if repeat else "246:end_frame=264"
    graph = (
        "[0:v:0]split=3[a][b][c];"
        "[a]trim=end_frame=246,setpts=PTS-STARTPTS[pre];"
        f"[b]trim=start_frame={middle},setpts=PTS-STARTPTS[mid];"
        "[c]trim=start_frame=264:end_frame=288,setpts=PTS-STARTPTS[post];"
        "[pre][mid][post]concat=n=3:v=1:a=0[out]"
    )
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-n",
        "-threads",
        "1",
        "-i",
        source,
        "-filter_complex_threads",
        "1",
        "-filter_complex",
        graph,
        "-map",
        "[out]",
        "-map_metadata",
        "-1",
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
        "-fps_mode",
        "passthrough",
        "-video_track_timescale",
        "24000",
        "-fflags",
        "+bitexact",
        output,
    ]


def probe_pts(path: Path) -> list[int]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=pts",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return [int(line) for line in completed.stdout.splitlines()]


def verify_control_pixels(
    reference: dict[str, Any], repeat: dict[str, Any], root: Path
) -> dict[str, Any]:
    with TemporaryDirectory(prefix="vrc-pair-qa-", dir=root / "artifacts") as temporary:
        requests = [
            decode_request(Path(s["path"]), Path(temporary) / role, s["facts"])
            for role, s in (("reference", reference), ("repeat", repeat))
        ]
        pixels = [[r.read_numeric(w.pixels.pixels) for w in _dense_inputs(r)] for r in requests]
        windows = [_dense_inputs(r) for r in requests]
        if [w.timing.first_tick for w in windows[0]] != [0, 120000, 240000]:
            raise ValueError("Unexpected retained windows for controlled probe")
        for window_a, window_b in zip(windows[0], windows[1], strict=True):
            if (
                window_a.timing.data is None
                or window_b.timing.data is None
                or not np.array_equal(
                    requests[0].read_numeric(window_a.timing.data),
                    requests[1].read_numeric(window_b.timing.data),
                )
            ):
                raise ValueError("Matched probe PTS differ")
        a, b = pixels
        checks = [
            np.array_equal(a[0], b[0]),
            np.array_equal(a[1], b[1]),
            np.array_equal(a[2][:6], b[2][:6]),
            np.array_equal(a[2][24:], b[2][24:]),
            np.array_equal(b[0][6:24], b[2][6:24]),
        ]
        distinct = len({hashlib.sha256(frame.tobytes()).hexdigest() for frame in b[0][6:24]})
        if not all(checks) or distinct <= 1:
            raise ValueError("Controlled repeat not isolated, dynamic or exactly retained")
        return {
            "retained_copy_frames": 18,
            "distinct_source_frames": distinct,
            "unchanged_observed_outside_destination": True,
            "copy_pixels_exact": True,
            "source_region": 0,
            "destination_region": 2,
            "start_ordinal": 6,
            "source_pts": [6000, 23000],
            "destination_pts": [246000, 263000],
            "time_base": [1, 24000],
            "gap_seconds": 223000 / 24000,
        }


def prepare(workspace: Path, benign_root: Path, demo_root: Path) -> None:
    root = demo._external_directory(workspace)
    for source_root in (benign_root, demo_root):
        demo._external_directory(source_root)
        if root.is_relative_to(source_root) or source_root.is_relative_to(root):
            raise ValueError("Research output overlaps a frozen source workspace")
    root.mkdir(parents=True, exist_ok=True)
    for directory in ("artifacts", "paired", "tables", "logs", "input"):
        demo._owned_path(root, directory).mkdir()
    samples = inventory(benign_root, demo_root)
    references = paired_sources(samples)
    if len(references) != 8 or sum(s["dataset"] == "benign" for s in samples) != 16:
        raise ValueError("STOP: frozen 16-video / 8-family benign inventory required")
    benign._seal(root, "research-matrix.json", research_matrix())
    benign._seal(
        root,
        "freeze.json",
        {
            "baseline": BASELINE,
            "version": VERSION,
            "policy": demo._policy(),
            "environment": demo._environment(),
            "matrix_sha256": benign._hash_file(root / "research-matrix.json"),
            "prepared_at": benign._now(),
            "tool_sha256_lf": demo._digest(Path(__file__).read_text().encode()),
            "source_manifests": {
                str(p / "manifest.json"): benign._hash_file(p / "manifest.json")
                for p in (benign_root, demo_root)
            },
        },
    )
    # No candidate gate/pooling outcomes are evaluated until ALL old baselines match.
    reproductions = []
    for sample in samples:
        pairs, metrics = sample_pairs(sample, root)
        error = verify_reproduction(pairs, sample["prior_metrics"])
        if metrics != sample["prior_metrics"]:
            raise ValueError("STOP: full production raw metrics differ from retained E2E")
        reproductions.append(
            {
                "dataset": sample["dataset"],
                "sample_id": sample["sample_id"],
                "error": error,
                "response": retained_response(pairs)[0],
                "full_raw_metrics_equal": True,
            }
        )
        print(f"baseline exact: {sample['dataset']}/{sample['sample_id']}", flush=True)
    benign._seal(root, "baseline-reproduction.json", reproductions)
    design = []
    for source in references:
        if source["facts"]["technical_parameters"]["fps"] != 24 or probe_pts(
            Path(source["path"])
        ) != list(range(0, 288000, 1000)):
            raise ValueError("Frozen reference is not the declared 288-frame CFR input")
        for role in ("reference", "repeat"):
            filename = f"paired/{source['source_family']}-{role}.mp4"
            design.append(
                {
                    "sample_id": f"paired-{source['source_family']}-{role}",
                    "source_family": source["source_family"],
                    "role": role,
                    "source_sample_id": source["sample_id"],
                    "source_sha256": source["sha256"],
                    "source_path": source["path"],
                    "split": source["split"],
                    "filename": filename,
                    "ffmpeg_command": paired_command(
                        source["path"], filename, repeat=role == "repeat"
                    ),
                }
            )
    benign._seal(root, "paired-design.json", design)
    controlled = []
    for row in design:
        target = demo._owned_path(root, row["filename"])
        subprocess.run(
            row["ffmpeg_command"], cwd=root, capture_output=True, check=True, timeout=120
        )
        with TemporaryDirectory(prefix="vrc-encode-", dir=root / "artifacts") as temporary:
            replica = Path(temporary) / "replica.mp4"
            subprocess.run(
                [*row["ffmpeg_command"][:-1], str(replica)],
                cwd=root,
                capture_output=True,
                check=True,
                timeout=120,
            )
            if benign._hash_file(target) != benign._hash_file(replica):
                raise ValueError("STOP: controlled encoding is not deterministic")
        if probe_pts(target) != list(range(0, 288000, 1000)):
            raise ValueError("Controlled probe changed PTS")
        source = next(s for s in references if s["sample_id"] == row["source_sample_id"])
        digest, size = benign._hash_file(target), target.stat().st_size
        controlled.append(
            {
                **row,
                "dataset": "paired",
                "path": str(target),
                "sha256": digest,
                "size_bytes": size,
                "byte_reproduction_equal": True,
                "evidence_level": "COMPONENT_LEVEL_RESEARCH",
                "facts": {
                    **source["facts"],
                    "sha256": digest,
                    "size_bytes": size,
                    "original_name": target.name,
                },
            }
        )
        print(f"paired bytes/PTS verified: {row['sample_id']}", flush=True)
    qa = []
    for family in sorted({s["source_family"] for s in controlled}):
        selected = {s["role"]: s for s in controlled if s["source_family"] == family}
        qa.append(
            {
                "source_family": family,
                **verify_control_pixels(selected["reference"], selected["repeat"], root),
            }
        )
    benign._seal(root, "paired-qa.json", qa)
    benign._seal(root, "input/inventory.json", samples + controlled)
    write_csv(
        root / "tables/sample-inventory.csv",
        [
            {
                k: s.get(k)
                for k in (
                    "dataset",
                    "sample_id",
                    "source_family",
                    "role",
                    "split",
                    "path",
                    "sha256",
                    "size_bytes",
                    "evidence_level",
                )
            }
            for s in samples + controlled
        ],
    )
    write_csv(
        root / "tables/paired-manifest.csv",
        [{k: v for k, v in s.items() if k != "facts"} for s in controlled],
    )
    verify_freeze(root)
    benign._seal(
        root,
        "prepared.json",
        {
            "completed_at": benign._now(),
            "inventory_sha256": benign._hash_file(root / "input/inventory.json"),
            "matrix_sha256": benign._hash_file(root / "research-matrix.json"),
            "baseline_reproduction_sha256": benign._hash_file(root / "baseline-reproduction.json"),
            "paired_design_sha256": benign._hash_file(root / "paired-design.json"),
            "paired_qa_sha256": benign._hash_file(root / "paired-qa.json"),
        },
    )


def verify_freeze(root: Path) -> dict[str, Any]:
    verify_matrix(root)
    freeze: dict[str, Any] = benign._sealed(root, "freeze.json")
    if freeze["policy"] != demo._policy() or freeze["environment"] != demo._environment():
        raise ValueError("Production/model/environment freeze changed")
    if freeze["matrix_sha256"] != benign._hash_file(root / "research-matrix.json"):
        raise ValueError("Matrix binding changed")
    for path, digest in freeze["source_manifests"].items():
        if benign._hash_file(Path(path)) != digest:
            raise ValueError("Source manifest changed")
    return freeze


def subset_diagnostics(sample_id: str, gate: str, pairs: list[Pair]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not pairs:
        return rows
    sizes = sorted(
        {n for n in research_matrix()["extreme_value"]["sizes"] if n < len(pairs)} | {len(pairs)}
    )
    values = np.asarray([p.similarity for p in pairs])
    for replicate in range(16):
        seed = int(hashlib.sha256(f"{sample_id}|{gate}|{replicate}".encode()).hexdigest()[:16], 16)
        ordered = np.random.Generator(np.random.PCG64(seed)).permutation(values)
        for n in sizes:
            rows.append(
                {
                    "sample_id": sample_id,
                    "gate": gate,
                    "replicate": replicate,
                    "subset_pairs": n,
                    "total_pairs": len(pairs),
                    "strongest": float(ordered[:n].max()),
                }
            )
    return rows


def paired_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    paired = [r for r in rows if r["dataset"] == "paired"]
    for gate in GATES:
        for family in sorted({r["source_family"] for r in paired}):
            matches = [r for r in paired if r["gate"] == gate and r["source_family"] == family]
            if len(matches) != 2 or {r["role"] for r in matches} != {"reference", "repeat"}:
                raise ValueError("Matched reference/repeat isolation violated")
            reference = next(r for r in matches if r["role"] == "reference")
            repeat = next(r for r in matches if r["role"] == "repeat")
            if reference["split"] != repeat["split"]:
                raise ValueError("Source-family split changed")
            for pool in POOLS:
                a, b = reference[pool], repeat[pool]
                result.append(
                    {
                        "variant": f"{gate}__{pool}",
                        "gate": gate,
                        "pool": pool,
                        "source_family": family,
                        "split": reference["split"],
                        "reference_id": reference["sample_id"],
                        "repeat_id": repeat["sample_id"],
                        "reference": a,
                        "repeat": b,
                        "delta": b - a if a is not None and b is not None else None,
                        "supported": a is not None
                        and b is not None
                        and (
                            pool != "greedy_disjoint_top3_mean"
                            or min(reference["disjoint_support"], repeat["disjoint_support"]) == 3
                        ),
                    }
                )
    return result


def variant_summaries(
    rows: list[dict[str, Any]], deltas: list[dict[str, Any]], baselines: dict[str, float]
) -> list[dict[str, Any]]:
    output = []
    baseline_median = statistics.median(baselines.values())
    for variant in research_matrix()["variants"]:
        gate, pool = variant["gate"], variant["pool"]
        selected = [r for r in rows if r["dataset"] == "benign" and r["gate"] == gate]
        defined = [r for r in selected if r[pool] is not None]
        supported = [
            r for r in defined if pool != "greedy_disjoint_top3_mean" or r["disjoint_support"] == 3
        ]
        values = [r[pool] for r in defined]
        pairs = [d for d in deltas if d["variant"] == variant["id"]]
        differences = [d["delta"] for d in pairs if d["delta"] is not None]
        families = {r["source_family"] for r in supported} & {
            d["source_family"] for d in pairs if d["supported"]
        }
        reductions = sum(
            statistics.fmean(r[pool] for r in supported if r["source_family"] == family)
            < statistics.fmean(
                baselines[r["sample_id"]] for r in supported if r["source_family"] == family
            )
            for family in families
        )
        median = quantile(values, 0.5)
        row = {
            "variant": variant["id"],
            "gate": gate,
            "pool": pool,
            "n": len(values),
            "supported_samples": len(supported),
            "measurable_families": len(families),
            **{
                name: quantile(values, q)
                for name, q in (
                    ("min", 0),
                    ("p25", 0.25),
                    ("median", 0.5),
                    ("p75", 0.75),
                    ("max", 1),
                )
            },
            "ge095": sum(v >= 0.95 for v in values),
            "ge090": sum(v >= 0.90 for v in values),
            "ge075": sum(v >= 0.75 for v in values),
            "lt075": sum(v < 0.75 for v in values),
            "paired_n": len(differences),
            "positive": sum(d > 0 for d in differences),
            "zero": sum(d == 0 for d in differences),
            "negative": sum(d < 0 for d in differences),
            "paired_median_delta": quantile(differences, 0.5),
            "paired_min_delta": quantile(differences, 0),
            "paired_max_delta": quantile(differences, 1),
            "family_reduction_count": reductions,
            "median_reduction": baseline_median - median if median is not None else None,
            "simplicity": GATES.index(gate) + POOLS.index(pool),
        }
        row["ready_for_prototype"] = (
            len(families) == 8
            and len(supported) == 16
            and row["positive"] >= 7
            and median is not None
            and median < 0.95
            and baseline_median - median >= 0.05
            and reductions == 8
        )
        output.append(row)
    return output


def evaluate(workspace: Path) -> dict[str, Any]:
    root = demo._external_directory(workspace)
    verify_freeze(root)
    prepared = benign._sealed(root, "prepared.json")
    for key, name in (
        ("inventory_sha256", "input/inventory.json"),
        ("matrix_sha256", "research-matrix.json"),
        ("baseline_reproduction_sha256", "baseline-reproduction.json"),
        ("paired_design_sha256", "paired-design.json"),
        ("paired_qa_sha256", "paired-qa.json"),
    ):
        if prepared[key] != benign._hash_file(root / name):
            raise ValueError("Prepared evidence binding changed")
    samples = benign._sealed(root, "input/inventory.json")
    benign._seal(
        root,
        "run.json",
        {
            "started_at": benign._now(),
            "prepared_sha256": benign._hash_file(root / "prepared.json"),
            "tool_sha256_lf": demo._digest(Path(__file__).read_text().encode()),
            "matrix_sha256": prepared["matrix_sha256"],
            "policy": demo._policy(),
        },
    )
    pool_rows, distances, temporal, retention, extreme = [], [], [], [], []
    pair_directory = demo._owned_path(root, "artifacts/pairs")
    pair_directory.mkdir()
    for sample in samples:
        pairs, metrics = sample_pairs(sample, root)
        if "prior_metrics" in sample:
            if (
                benign._hash_file(Path(sample["prior_result_path"]))
                != sample["prior_result_sha256"]
            ):
                raise ValueError("Prior FILE_LEVEL_E2E evidence changed")
            verify_reproduction(pairs, sample["prior_metrics"])
        current, minima = retained_response(pairs)
        identity = {
            k: sample[k] for k in ("dataset", "sample_id", "source_family", "role", "split")
        }
        strongest = max((p.similarity for p in pairs), default=None)
        retention.append(
            {
                **identity,
                "current_response": current,
                "joint_strongest": strongest,
                "absolute_difference": abs(current - strongest)
                if current is not None and strongest is not None
                else None,
                "baseline_repro_error": 0.0,
                **minima,
            }
        )
        write_csv(
            pair_directory / f"{sample['dataset']}-{sample['sample_id']}.csv",
            [p.row() for p in pairs],
        )
        for gate in GATES:
            selected = [p for p in pairs if eligible(p, gate)]
            pooled = pooling(selected)
            pool_rows.append(
                {
                    **identity,
                    "gate": gate,
                    **pooled,
                    "strongest_minus_p99": pooled["strongest"] - pooled["p99"]
                    if selected
                    else None,
                    "strongest_minus_p95": pooled["strongest"] - pooled["p95"]
                    if selected
                    else None,
                }
            )
            for kind, values in (
                ("color", [p.color / 440640 for p in selected]),
                ("delta", [p.delta / 660960 for p in selected]),
                ("joint", [p.distance for p in selected]),
            ):
                distances.append(
                    {
                        **identity,
                        "gate": gate,
                        "distance": kind,
                        "n": len(values),
                        **{key: quantile(values, q) for key, q in QUANTILES.items()},
                    }
                )
            for rank, pair in enumerate(sorted(selected, key=lambda p: p.distance)[:5], 1):
                temporal.append({**identity, "gate": gate, "rank": rank, **pair.row()})
            if sample["dataset"] == "benign":
                extreme.extend(subset_diagnostics(sample["sample_id"], gate, selected))
        demo._write_json(
            root / "artifacts" / f"{sample['dataset']}-{sample['sample_id']}-production.json",
            metrics,
        )
        print(f"measured {sample['dataset']}/{sample['sample_id']}: {len(pairs)} pairs", flush=True)
    deltas = paired_deltas(pool_rows)
    baselines = {
        r["sample_id"]: r["current_response"] for r in retention if r["dataset"] == "benign"
    }
    variants = variant_summaries(pool_rows, deltas, baselines)
    ranked = sorted(
        variants,
        key=lambda r: (
            -r["measurable_families"],
            -r["supported_samples"],
            r["median"] if r["median"] is not None else 2,
            r["ge095"],
            -r["positive"],
            -r["family_reduction_count"],
            r["simplicity"],
            r["variant"],
        ),
    )
    correlations = []
    for gate in GATES:
        correlation_rows = [
            r
            for r in pool_rows
            if r["dataset"] == "benign" and r["gate"] == gate and r["eligible_pairs"]
        ]
        x = [math.log(r["eligible_pairs"]) for r in correlation_rows]
        y = [r["strongest"] for r in correlation_rows]
        correlations.append(
            {
                "gate": gate,
                "n": len(x),
                "pearson": benign.pearson(x, y),
                "spearman": benign.spearman(x, y),
            }
        )
    t0 = [
        r for r in temporal if r["dataset"] == "benign" and r["gate"] == GATES[0] and r["rank"] == 1
    ]
    current_locations = []
    for row in retention:
        if row["dataset"] != "benign":
            continue
        best = max(
            (row[k] for k in ("minimum_color_pair", "minimum_delta_pair")),
            key=lambda p: 1 - max(p["color_numerator"] / 440640, p["delta_numerator"] / 660960),
        )
        base = next(r["time_base_a"] for r in t0 if r["sample_id"] == row["sample_id"])
        scale = Fraction(*base)
        current_locations.append(
            {
                "sample_id": row["sample_id"],
                "same_region": best["a"]["region"] == best["b"]["region"],
                "start_separation_seconds": float(
                    (best["b"]["pts_ticks"][0] - best["a"]["pts_ticks"][0]) * scale
                ),
                "gap_seconds": float(
                    (best["b"]["pts_ticks"][0] - best["a"]["pts_ticks"][-1]) * scale
                ),
                "ordinal_separation": abs(best["a"]["start_ordinal"] - best["b"]["start_ordinal"]),
            }
        )
    ready = [r for r in ranked if r["ready_for_prototype"]]
    summary = {
        "version": VERSION,
        "evidence_level": "COMPONENT_LEVEL_RESEARCH",
        "baseline": BASELINE,
        "matrix_sha256": prepared["matrix_sha256"],
        "production_changed": False,
        "samples": {
            dataset: sum(s["dataset"] == dataset for s in samples)
            for dataset in ("benign", "paired", "demo")
        },
        "benign_families": len({s["source_family"] for s in samples if s["dataset"] == "benign"}),
        "baseline_reproduction_error": max(r["baseline_repro_error"] for r in retention),
        "current_baseline": benign.distribution(list(baselines.values())),
        "gate_strongest": [v for v in variants if v["pool"] == "strongest"],
        "correlations": correlations,
        "current_retention_max_difference": max(r["absolute_difference"] for r in retention),
        "current_retention_benign_max_difference": max(
            r["absolute_difference"] for r in retention if r["dataset"] == "benign"
        ),
        "temporal_t0": {
            "same_region": sum(r["same_region"] for r in t0),
            "cross_region": sum(not r["same_region"] for r in t0),
            "gap_le_0_5": sum(r["gap_seconds"] <= 0.5 for r in t0),
            "gap_0_5_to_1": sum(0.5 < r["gap_seconds"] < 1 for r in t0),
            "gap_1_to_2": sum(1 <= r["gap_seconds"] < 2 for r in t0),
            "gap_ge_2": sum(r["gap_seconds"] >= 2 for r in t0),
        },
        "current_retained_locations": current_locations,
        "eligible_pair_range_t0_benign": [
            min(
                r["eligible_pairs"]
                for r in pool_rows
                if r["dataset"] == "benign" and r["gate"] == GATES[0]
            ),
            max(
                r["eligible_pairs"]
                for r in pool_rows
                if r["dataset"] == "benign" and r["gate"] == GATES[0]
            ),
        ],
        "best_ranked_variant": ranked[0],
        "ready_variants": ready,
        "disposition": "VRC_POLICY_CANDIDATE_READY_FOR_PROTOTYPE"
        if ready
        else "VRC_REDESIGN_REQUIRED",
        "limitation": (
            "Descriptive frozen-corpus research, not FPR/TPR, deepfake probability or calibration."
        ),
    }
    for name, rows in (
        ("pair-summary-by-sample.csv", retention),
        ("temporal-location-summary.csv", temporal),
        ("distance-distributions.csv", distances),
        ("pooling-comparison.csv", pool_rows),
        ("benign-variant-summary.csv", variants),
        ("paired-repeat-deltas.csv", deltas),
        ("demo-diagnostic-summary.csv", [r for r in pool_rows if r["dataset"] == "demo"]),
        ("variant-ranking.csv", [{"rank": i, **r} for i, r in enumerate(ranked, 1)]),
        ("extreme-value-pooling.csv", extreme),
        ("extreme-value-correlations.csv", correlations),
    ):
        write_csv(root / "tables" / name, rows)
    verify_freeze(root)
    benign._seal(root, "tables/summary.json", summary)
    shutil.copyfile(root / "research-matrix.json", root / "tables/research-matrix.json")
    benign._seal(
        root,
        "complete.json",
        {
            "completed_at": benign._now(),
            "artifacts": {
                p.relative_to(root).as_posix(): {
                    "sha256": benign._hash_file(p),
                    "size": p.stat().st_size,
                }
                for directory in (root / "tables", root / "artifacts")
                for p in sorted(directory.rglob("*"))
                if p.is_file()
            },
        },
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "evaluate"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--benign", type=Path)
    parser.add_argument("--demo", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.benign is None or args.demo is None:
            parser.error("prepare requires --benign and --demo")
        prepare(args.workspace, args.benign, args.demo)
    else:
        evaluate(args.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
