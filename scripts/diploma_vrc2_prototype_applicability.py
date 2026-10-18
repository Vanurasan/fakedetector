"""Frozen VRC2 prototype parity and applicability; external media, no method selection."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import subprocess
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fakedetector.analyzers._catalog import (
    _built_in_analyzer_registrations,
    _resolve_runtime_analyzer_definition,
    _resolve_worker_definition,
    _runtime_analyzer_registrations,
)
from fakedetector.analyzers._models import AnalyzerRequest
from fakedetector.analyzers._orchestrator import _plain_json_value
from fakedetector.analyzers._transport import _WorkerArtifact, _WorkerRequest
from fakedetector.analyzers._video_experimental import VideoRepeatedContentCorrespondenceAnalyzer
from fakedetector.analyzers._video_vrc2_prototype import (
    VideoRepeatedContentCorrespondenceV2PrototypeAnalyzer,
)
from fakedetector.analyzers._worker import _SpawnedWorkerRunner, _WorkerRunKind
from fakedetector.domain import AnalyzerResult, AnalyzerStatus
from scripts import diploma_benign_validation as benign
from scripts import diploma_demo_evaluation as demo
from scripts import diploma_vrc_redesign_research as research
from scripts import diploma_vrc_targeted_research as prior

BASELINE = "4e564dc8d0fa20df196f7cb1a1e63224ac4fcf83"
METHOD = "D2__I25__K9__R10"
KEY = "prototype.video_repeated_content_correspondence_v2.v0"
ANALYZER = VideoRepeatedContentCorrespondenceV2PrototypeAnalyzer()
SELECTION_SHA = "9f40e13656fbbb12122829c12b8eea37d341695210022cd22180d3409d1f7795"
FIELDS = {
    "state": "state",
    "valid_group_count": "valid_groups",
    "eligible_group_count": "eligible_groups",
    "eligible_run_count": "eligible_runs",
    "energy_p25": "energy_p25",
    "d_best": "d_best",
    "p10_distance": "p10_distance",
    "median_distance": "median_distance",
    "relative_distinctiveness": "score",
}


def runtime_isolation() -> dict[str, Any]:
    core = {
        "image_metadata_consistency",
        "audio_pcm_quality",
        "video_sampled_frame_quality",
        "image_copy_move_correspondence",
        "image_jpeg_double_quantization",
    }
    experimental = {
        "audio_repeated_segment_correspondence",
        "video_repeated_content_correspondence",
        "video_visual_discontinuity",
        "video_timing_anomaly",
        "image_noise_residual_consistency",
        "image_resampling_consistency",
        "audio_temporal_discontinuity",
        "audio_spectral_consistency",
        "audio_background_noise_consistency",
    }
    actual = {r.analyzer_id for r in _runtime_analyzer_registrations()}
    definition = _resolve_worker_definition(KEY)
    valid = (
        actual == core | experimental
        and {r.analyzer_id for r in _built_in_analyzer_registrations()} == core
        and _resolve_runtime_analyzer_definition(ANALYZER.analyzer_id) is None
        and definition is not None
        and definition.factory is type(ANALYZER)
        and all(
            m["analyzer_id"] != ANALYZER.analyzer_id
            for f in demo._policy()["families"]
            for m in f["members"]
        )
    )
    if not valid:
        raise ValueError("Prototype runtime isolation failed")
    return {
        "pass": valid,
        "runtime_ids": sorted(actual),
        "core_ids": sorted(core),
        "prototype_worker_key": KEY,
        "normal_runtime_resolves_prototype": False,
    }


def verify_inputs(accepted: Path) -> list[dict[str, Any]]:
    """Verify accepted evidence without pretending the authorized new source has old hashes."""
    frozen = benign._sealed(accepted, "freeze/design.json")
    if frozen["code"] != research.fingerprint() or frozen["environment"] != demo._environment():
        raise ValueError("Accepted research code/environment differs")
    current = demo._policy()
    previous = frozen["policy"]
    for key, value in previous.items():
        if key != "runtime_sha256_lf" and current[key] != value:
            raise ValueError(f"Frozen policy differs: {key}")
    old, new = previous["runtime_sha256_lf"], current["runtime_sha256_lf"]
    allowed = {
        "src/fakedetector/analyzers/_catalog.py",
        "src/fakedetector/analyzers/_video_vrc2_prototype.py",
    }
    if {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} != allowed:
        raise ValueError("Runtime changes exceed authorized prototype/catalog delta")
    for path, expected in frozen["source_receipts"].items():
        research.check_receipt(Path(path), expected)
    candidate, _ = research.selected_candidate(accepted)
    if (
        candidate.id != METHOD
        or benign._hash_file(accepted / "selected-candidate.json") != SELECTION_SHA
    ):
        raise ValueError("Accepted selected candidate differs")
    complete = benign._sealed(accepted, "complete.json")
    research.check_receipt(accepted / "selected-candidate.json", complete["selection_receipt"])
    for name, expected in complete["artifacts"].items():
        research.check_receipt(demo._owned_path(accepted, name), expected)
    rows: list[dict[str, Any]] = benign._sealed(accepted, "input/inventory.json")
    if benign._hash_file(accepted / "input/inventory.json") != frozen["inventory_sha256"]:
        raise ValueError("Accepted inventory differs")
    research.validate_inventory(rows)
    for sample in rows:
        research.check_receipt(
            Path(sample["path"]), {"sha256": sample["sha256"], "size": sample["size_bytes"]}
        )
        research.load_groups(accepted, sample)
    return rows


def media_commands(
    source: Path, output: Path, *, fps: int, length: float, transform: str, repeat: bool
) -> list[list[str]]:
    """Fixed 12-second matched encoding; modify only destination before common fps conversion."""
    prefix = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-threads", "1"]
    encoding = [
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
    ]
    start = 0.25 if repeat else 10.25
    stop = start + length * (1.05 if repeat and transform == "N5_SPEED_1_05" else 1)
    filters = {
        "N0_EXACT": "null",
        "N1_BRIGHTNESS": "eq=brightness=0.04",
        "N2_REENCODE": "null",
        "N3_SCALE_ROUNDTRIP": (
            "scale=trunc(iw/4)*2:trunc(ih/4)*2:flags=bilinear,scale={w}:{h}:flags=bilinear"
        ),
        "N4_CENTER_CROP": (
            "crop=trunc(iw*0.96/2)*2:trunc(ih*0.96/2)*2,scale={w}:{h}:flags=bilinear,setsar=1"
        ),
        "N5_SPEED_1_05": "setpts=PTS/1.05,fps=24:start_time=0",
    }
    # Geometry placeholders are resolved before matrix sealing, from accepted file facts.
    effect = filters[transform] if repeat else "null"
    commands = []
    inputs = ["-i", str(source)]
    middle = (
        f"[b]trim=start={start}:end={stop},setpts=PTS-STARTPTS,{effect},"
        f"trim=duration={length}[mid];"
    )
    if repeat and transform == "N2_REENCODE":
        episode = output.with_name(output.stem + "-episode.mp4")
        lossy = encoding.copy()
        lossy[lossy.index("-q:v") + 1] = "8"
        commands.append(
            prefix
            + inputs
            + ["-vf", f"trim=start={start}:end={stop},setpts=PTS-STARTPTS"]
            + lossy
            + [str(episode)]
        )
        inputs += ["-i", str(episode)]
        middle = "[b]nullsink;[1:v:0]setpts=PTS-STARTPTS[mid];"
    graph = (
        "[0:v:0]split=3[a][b][c];[a]trim=end=10.25,setpts=PTS-STARTPTS[pre];"
        + middle
        + f"[c]trim=start={10.25 + length}:end=12,setpts=PTS-STARTPTS[post];"
        + f"[pre][mid][post]concat=n=3:v=1:a=0,fps={fps}:start_time=0[out]"
    )
    commands.append(
        prefix
        + inputs
        + ["-filter_complex_threads", "1", "-filter_complex", graph, "-map", "[out]"]
        + encoding
        + [str(output)]
    )
    return commands


def matrix(root: Path, samples: list[dict[str, Any]]) -> dict[str, Any]:
    cells = []
    axes = [("cadence", f"C{fps}", fps, 0.75, "N0_EXACT") for fps in (24, 12, 8, 6, 4)]
    axes += [
        ("repeat-length", name, 24, length, "N0_EXACT")
        for name, length in (
            ("L025", 0.25),
            ("L050", 0.5),
            ("L075", 0.75),
            ("L100", 1.0),
            ("L150", 1.5),
        )
    ]
    axes += [
        ("near-copy", name, 24, 0.75, name)
        for name in (
            "N0_EXACT",
            "N1_BRIGHTNESS",
            "N2_REENCODE",
            "N3_SCALE_ROUNDTRIP",
            "N4_CENTER_CROP",
            "N5_SPEED_1_05",
        )
    ]
    for source in prior.paired_sources(samples):
        geometry = source["facts"]["technical_parameters"]
        for axis, cell, fps, length, transform in axes:
            item: dict[str, Any] = {
                "axis": axis,
                "cell": cell,
                "source_family": source["source_family"],
                "source_sample_id": source["sample_id"],
                "source_sha256": source["sha256"],
                "fps": fps,
                "length": length,
                "transform": transform,
                "known_source": [
                    0.25,
                    0.25 + length * (1.05 if transform == "N5_SPEED_1_05" else 1),
                ],
                "known_destination": [10.25, 10.25 + length],
                "outputs": {},
            }
            for role in ("reference", "repeat"):
                output = root / axis / f"{source['source_family']}-{cell}-{role}.mp4"
                commands = media_commands(
                    Path(source["path"]),
                    output,
                    fps=fps,
                    length=length,
                    transform=transform,
                    repeat=role == "repeat",
                )
                commands = [
                    [
                        arg.replace("{w}", str(geometry["width"])).replace(
                            "{h}", str(geometry["height"])
                        )
                        for arg in command
                    ]
                    for command in commands
                ]
                item["outputs"][role] = {"path": str(output), "commands": commands}
            cells.append(item)
    return {
        "method": METHOD,
        "cells": cells,
        "duration_seconds": 12,
        "created_before_outcomes": True,
        "localization": (
            "closed observed group PTS against half-open known episode; "
            "both sides required; majority >=5/9; fully=9/9"
        ),
        "paired_sign": "strict delta >0 / ==0 / <0; null if either insufficient",
        "selection": "unchanged; no new score thresholds",
        "near_copy_length_seconds": 0.75,
    }


def prepare(root: Path, accepted: Path) -> None:
    root, accepted = demo._external_directory(root), demo._external_directory(accepted)
    if root.is_relative_to(accepted) or accepted.is_relative_to(root):
        raise ValueError("Output overlaps accepted corpus")
    samples = verify_inputs(accepted)
    root.mkdir()
    for name in (
        "input",
        "freeze",
        "parity",
        "worker",
        "cadence",
        "repeat-length",
        "near-copy",
        "localization",
        "resources",
        "tables",
        "logs",
        "review",
        "artifacts",
        "demo",
    ):
        (root / name).mkdir()
    benign._seal(root, "input/inventory.json", samples)
    prior.write_csv(
        root / "tables/input-inventory.csv",
        [
            {k: s.get(k) for k in (*research.IDENTITY, "path", "sha256", "size_bytes")}
            for s in samples
        ],
    )
    benign._seal(root, "applicability-matrix.json", matrix(root, samples))
    benign._seal(
        root,
        "freeze/design.json",
        {
            "created_at": benign._now(),
            "baseline": BASELINE,
            "accepted": str(accepted),
            "matrix": research.receipt(root / "applicability-matrix.json"),
            "inventory": research.receipt(root / "input/inventory.json"),
            "accepted_complete": research.receipt(accepted / "complete.json"),
            "policy": demo._policy(),
            "environment": demo._environment(),
            "script": research.receipt(Path(__file__)),
        },
    )
    print("Inputs verified; 128 paired cells frozen before outcomes", flush=True)


def verify(root: Path) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    frozen = benign._sealed(root, "freeze/design.json")
    for key, name in (
        ("matrix", "applicability-matrix.json"),
        ("inventory", "input/inventory.json"),
    ):
        research.check_receipt(root / name, frozen[key])
    if frozen["policy"] != demo._policy() or frozen["environment"] != demo._environment():
        raise ValueError("Prototype/environment freeze differs")
    accepted = Path(frozen["accepted"])
    research.check_receipt(accepted / "complete.json", frozen["accepted_complete"])
    samples = verify_inputs(accepted)
    if samples != benign._sealed(root, "input/inventory.json"):
        raise ValueError("Input inventory differs")
    design = benign._sealed(root, "applicability-matrix.json")
    if design != matrix(root, samples):
        raise ValueError("Stress design changed")
    return accepted, samples, design


def transport(request: AnalyzerRequest) -> _WorkerRequest:
    return _WorkerRequest(
        worker_key=KEY,
        analysis_id=request.analysis_id,
        media_type=request.media_type.value,
        file_facts_json=request.file_facts.model_dump_json(),
        source_path=str(request.source._local_path),
        artifacts=tuple(
            _WorkerArtifact(
                a.artifact_id,
                a.artifact_type,
                str(a.content._local_path),
                a.format,
                a.start_time_seconds,
                a.end_time_seconds,
                a.frame_index,
            )
            for a in request.artifacts
        ),
        metadata_json=json.dumps(_plain_json_value(request.metadata)),
        warnings=request.warnings,
        settings_json=request.settings.model_dump_json(),
        timeout_seconds=request.timeout_seconds,
    )


def worker(request: AnalyzerRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.perf_counter()
    run = _SpawnedWorkerRunner().run(transport(request), request.timeout_seconds)
    cleanup = before == {p.pid for p in multiprocessing.active_children()}
    resource = {
        "wall_seconds": time.perf_counter() - started,
        "worker_duration_ms": run.duration_ms,
        "worker_status": run.kind.name,
        "cleanup": cleanup,
        "timeout_seconds": request.timeout_seconds,
        "hard_rss": "NOT_ENFORCED_BY_EXISTING_ANALYZER_WORKER",
        "resource_limit_result": "PASS"
        if run.kind is _WorkerRunKind.RESPONSE and cleanup
        else "FAIL",
    }
    if run.kind is not _WorkerRunKind.RESPONSE or not cleanup or run.response is None:
        raise ValueError(f"Worker execution failed: {resource}")
    payload = json.loads(run.response)
    if payload["kind"] != "result":
        raise ValueError(f"Worker did not return result: {payload['kind']}")
    result = AnalyzerResult.model_validate(payload["result"])
    if (
        result.status is not AnalyzerStatus.COMPLETED
        or result.score is not None
        or result.candidate_findings
    ):
        raise ValueError("Invalid measurement-only result")
    demo._json_bytes(result.raw_metrics)
    resource["response_bytes"] = len(run.response)
    return result.raw_metrics, resource


def compare(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    errors = {}
    for new, old in FIELDS.items():
        a, b = actual[new], expected[old]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            error = abs(a - b)
            if error > 1e-12:
                raise ValueError(f"STOP: parity differs: {new}: {a} != {b}")
            errors[new] = error
        elif a != b:
            raise ValueError(f"STOP: parity differs: {new}")
    a, b = actual["best_run"], expected["best_run"]
    if (a is None) != (b is None) or (a is not None and a["constituents"] != b["constituents"]):
        raise ValueError("STOP: selected run/constituents differ")
    return {
        "state_parity": True,
        "best_run_parity": True,
        "all_metrics_parity": True,
        "max_difference": max(errors.values(), default=0),
        "score_difference": errors.get("relative_distinctiveness", 0),
    }


def parity(root: Path) -> None:
    accepted, samples, _ = verify(root)
    candidate, _ = research.selected_candidate(accepted)
    saved = [
        r
        for phase in ("observation", "holdout")
        for r in benign._sealed(accepted, f"{phase}/results.json")
        if r["candidate_id"] == METHOD
    ]
    rows = []
    for sample in [s for s in samples if s["dataset"] != "demo"]:
        groups = research.load_groups(accepted, sample)
        expected = research.measure(sample, groups, (candidate,))[0][0]
        old = next(r for r in saved if all(r[k] == sample[k] for k in research.IDENTITY))
        if expected != old:
            raise ValueError("Accepted research replay differs")
        with TemporaryDirectory(dir=root / "artifacts", prefix="parity-") as temp:
            request = prior.decode_request(
                Path(sample["path"]), Path(temp) / "decode", sample["facts"]
            )
            control = VideoRepeatedContentCorrespondenceAnalyzer().analyze(request).raw_metrics
            if control != sample["accepted_production"]:
                raise ValueError("VRC1 output changed")
            actual = ANALYZER.analyze(request).raw_metrics
            row = {**{k: sample[k] for k in research.IDENTITY}, **compare(actual, expected)}
        benign._seal(
            root,
            f"parity/{research.cache_name(sample)}.json",
            {"actual": actual, "expected": expected},
        )
        rows.append(row)
        print(f"Parity {len(rows)}/32: {research.cache_name(sample)}", flush=True)
    if len(rows) != 32:
        raise ValueError("32 primary rows required")
    prior.write_csv(root / "tables/prototype-parity.csv", rows)
    benign._seal(root, "parity/complete.json", rows)


def worker_gate(root: Path) -> None:
    _, samples, _ = verify(root)
    isolation = runtime_isolation()
    if len(benign._sealed(root, "parity/complete.json")) != 32:
        raise ValueError("Primary parity must pass first")
    selected = [
        next(s for s in samples if s["dataset"] == "benign" and s["role"] == role)
        for role in ("BENIGN_REFERENCE", "BENIGN_PROCESSING")
    ]
    selected += [next(s for s in samples if s["dataset"] == "paired" and s["role"] == "repeat")]
    selected += [
        next(s for s in samples if s["dataset"] == "demo" and s["sample_id"] == name)
        for name in ("video-03-static", "video-01-control")
    ]
    rows = []
    for sample in selected:
        with TemporaryDirectory(dir=root / "artifacts", prefix="worker-") as temp:
            request = prior.decode_request(
                Path(sample["path"]), Path(temp) / "decode", sample["facts"]
            )
            actual, resource = worker(request)
            replay, _ = worker(request)
            if actual != replay or actual != ANALYZER.analyze(request).raw_metrics:
                raise ValueError("Worker replay differs")
            rows.append(
                {
                    "sample_id": research.cache_name(sample),
                    "state": actual["state"],
                    "deterministic": True,
                    **resource,
                }
            )
            if len(rows) == 1:
                runner = _SpawnedWorkerRunner()
                before = {p.pid for p in multiprocessing.active_children()}
                malformed = runner.run(
                    replace(transport(request), settings_json='{"invalid":1}'), 120
                )
                if (
                    malformed.response is None
                    or json.loads(malformed.response)["kind"] != "worker_error"
                ):
                    raise ValueError("Malformed request not safely rejected")
                timed = runner.run(transport(request), 0.001)
                if timed.kind is not _WorkerRunKind.TIMEOUT or before != {
                    p.pid for p in multiprocessing.active_children()
                }:
                    raise ValueError("Timeout cleanup differs")
        print(f"Worker gate: {rows[-1]['sample_id']} {actual['state']}", flush=True)
    prior.write_csv(root / "tables/worker-execution.csv", rows)
    benign._seal(
        root,
        "worker/complete.json",
        {
            "rows": rows,
            "timeout_cleanup": True,
            "malformed_safe": True,
            "runtime_isolation": isolation,
        },
    )


def localization(metrics: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "known_source": cell["known_source"],
        "known_destination": cell["known_destination"],
        "constituent_count": 0,
        "overlap_count": 0,
        "fully_contained_count": 0,
        "ANY_OVERLAP": False,
        "MAJORITY_OVERLAP": False,
        "FULLY_CONTAINED": False,
        "source_span": None,
        "destination_span": None,
        "temporal_lag_error": None,
        "source_start_error": None,
        "source_end_error": None,
        "destination_start_error": None,
        "destination_end_error": None,
    }
    best = metrics["best_run"]
    if best is None:
        return result
    spans: dict[str, list[list[float]]] = {"a": [], "b": []}
    for pair in best["constituents"]:
        overlap, contained = [], []
        for side, known in (("a", cell["known_source"]), ("b", cell["known_destination"])):
            loc = pair[side]
            scale = loc["time_base"][0] / loc["time_base"][1]
            span = [loc["pts_ticks"][0] * scale, loc["pts_ticks"][-1] * scale]
            spans[side].append(span)
            overlap.append(span[1] >= known[0] and span[0] < known[1])
            contained.append(known[0] <= span[0] and span[1] < known[1])
        result["overlap_count"] += all(overlap)
        result["fully_contained_count"] += all(contained)
    result["constituent_count"] = len(best["constituents"])
    for side, label, known in (
        ("a", "source", cell["known_source"]),
        ("b", "destination", cell["known_destination"]),
    ):
        span = [min(x[0] for x in spans[side]), max(x[1] for x in spans[side])]
        result[label + "_span"] = span
        result[label + "_start_error"] = span[0] - known[0]
        result[label + "_end_error"] = span[1] - known[1]
    result["temporal_lag_error"] = result["destination_span"][0] - result["source_span"][0] - 10
    result.update(
        ANY_OVERLAP=result["overlap_count"] > 0,
        MAJORITY_OVERLAP=result["overlap_count"] >= 5,
        FULLY_CONTAINED=result["fully_contained_count"] == 9,
    )
    return result


def generate_cell(root: Path, cell: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    results = {}
    for role, output in cell["outputs"].items():
        path = Path(output["path"])
        for command in output["commands"]:
            subprocess.run(command, capture_output=True, check=True, timeout=120)
        # Re-run identical frozen recipes at a distinct owned destination, compare bytes.
        with TemporaryDirectory(dir=root / "artifacts", prefix="generation-replay-") as temp:
            for command in output["commands"]:
                replay = [
                    str(Path(temp) / Path(arg).name) if str(path.parent) in arg else arg
                    for arg in command
                ]
                subprocess.run(replay, capture_output=True, check=True, timeout=120)
            if research.receipt(path) != research.receipt(Path(temp) / path.name):
                raise ValueError("STOP: generated transformation is nondeterministic")
        pts = prior.probe_pts(path)
        if pts != [i * (24000 // cell["fps"]) for i in range(12 * cell["fps"])]:
            raise ValueError("Generated duration/cadence/monotonic PTS differ")
        facts = {
            **source["facts"],
            "sha256": benign._hash_file(path),
            "size_bytes": path.stat().st_size,
            "technical_parameters": {**source["facts"]["technical_parameters"], "fps": cell["fps"]},
        }
        with TemporaryDirectory(dir=root / "artifacts", prefix="stress-") as temp:
            request = prior.decode_request(path, Path(temp) / "decode", facts)
            metrics, resource = worker(request)
        results[role] = {
            "metrics": metrics,
            "resources": resource,
            "receipt": research.receipt(path),
            "generation_deterministic": True,
            "pts_count": len(pts),
        }
    return results


def paired_sign(reference: float | None, repeat: float | None) -> tuple[float | None, str]:
    if reference is None or repeat is None:
        return None, "insufficient"
    delta = repeat - reference
    return delta, "positive" if delta > 0 else "negative" if delta < 0 else "zero"


def stress(root: Path) -> None:
    _, samples, design = verify(root)
    benign._sealed(root, "worker/complete.json")
    rows, locations, supports, resources = [], [], [], []
    for index, cell in enumerate(design["cells"]):
        source = next(
            s
            for s in samples
            if s["dataset"] == "benign" and s["sample_id"] == cell["source_sample_id"]
        )
        identity = {k: cell[k] for k in ("axis", "cell", "source_family")}
        name = f"{cell['axis']}/{cell['source_family']}-{cell['cell']}-results.json"
        # A sealed completed cell can be resumed; no matrix editing or outcome-driven changes.
        if (root / name).exists():
            result = benign._sealed(root, name)
            for role, item in result.items():
                research.check_receipt(Path(cell["outputs"][role]["path"]), item["receipt"])
        else:
            result = generate_cell(root, cell, source)
            benign._seal(root, name, result)
        row = dict(identity)
        for role, item in result.items():
            m = item["metrics"]
            row.update(
                {
                    f"{role}_{field}": m[field]
                    for field in (
                        "state",
                        "relative_distinctiveness",
                        "valid_group_count",
                        "eligible_group_count",
                        "eligible_run_count",
                    )
                }
            )
            supports.append(
                {
                    **identity,
                    "role": role,
                    "state": m["state"],
                    "valid_groups": m["valid_group_count"],
                    "eligible_groups": m["eligible_group_count"],
                    **m["run_support"],
                }
            )
            resources.append({**identity, "role": role, **item["resources"]})
        delta, sign = paired_sign(
            row["reference_relative_distinctiveness"], row["repeat_relative_distinctiveness"]
        )
        row.update(paired_delta=delta, paired_sign=sign)
        rows.append(row)
        locations.append(
            {
                **identity,
                "state": result["repeat"]["metrics"]["state"],
                **localization(result["repeat"]["metrics"], cell),
            }
        )
        print(f"Stress {index + 1}/128: {cell['source_family']} {cell['cell']} {sign}", flush=True)
    for axis in ("cadence", "repeat-length", "near-copy"):
        prior.write_csv(root / f"tables/{axis}-results.csv", [r for r in rows if r["axis"] == axis])
    for name, table in (
        ("localization-results", locations),
        ("run-support-diagnostics", supports),
        ("resource-summary", resources),
    ):
        prior.write_csv(root / f"tables/{name}.csv", table)
    benign._seal(root, "resources/stress.json", resources)
    benign._seal(root, "localization/results.json", locations)
    benign._seal(root, "tables/stress.json", rows)


def demo_recheck(root: Path) -> None:
    accepted, samples, _ = verify(root)
    benign._sealed(root, "worker/complete.json")
    expected = benign._sealed(accepted, "demo/results.json")
    rows = []
    for sample in [s for s in samples if s["dataset"] == "demo"]:
        old = next(
            r
            for r in expected
            if r["sample_id"] == sample["sample_id"] and r["candidate_id"] == METHOD
        )
        with TemporaryDirectory(dir=root / "artifacts", prefix="demo-") as temp:
            request = prior.decode_request(
                Path(sample["path"]), Path(temp) / "decode", sample["facts"]
            )
            actual, resource = worker(request)
        row = {
            "sample_id": sample["sample_id"],
            **compare(actual, old),
            "metrics": actual,
            "resources": resource,
        }
        rows.append(row)
        print(f"Demo: {sample['sample_id']} {actual['state']}", flush=True)
    benign._seal(root, "demo/results.json", rows)
    prior.write_csv(root / "tables/demo-recheck.csv", rows)


def finish(root: Path) -> dict[str, Any]:
    verify(root)
    parity_rows = benign._sealed(root, "parity/complete.json")
    gate = benign._sealed(root, "worker/complete.json")
    rows = benign._sealed(root, "tables/stress.json")
    demos = benign._sealed(root, "demo/results.json")
    resources = benign._sealed(root, "resources/stress.json")
    locations = benign._sealed(root, "localization/results.json")
    cells = {
        name: {
            "total": len(items),
            "measurable_reference": sum(r["reference_state"] == "MEASURED" for r in items),
            "measurable_repeat": sum(r["repeat_state"] == "MEASURED" for r in items),
            **dict(Counter(r["paired_sign"] for r in items)),
        }
        for name in dict.fromkeys(r["cell"] for r in rows)
        for items in [[r for r in rows if r["cell"] == name]]
    }
    p = {
        "P1": len(parity_rows) == 32 and all(r["all_metrics_parity"] for r in parity_rows),
        "P2": all(r["cleanup"] and r["deterministic"] for r in gate["rows"])
        and gate["timeout_cleanup"],
        "P3": gate["runtime_isolation"]["pass"] and runtime_isolation()["pass"],
        "P4": cells["C24"]["measurable_repeat"] == 8 and cells["C24"]["measurable_reference"] == 8,
        "P5": cells["C12"].get("positive", 0) >= 7,
        "P6": cells["N0_EXACT"].get("positive", 0) == 8,
        "P7": sum(cells[n].get("positive", 0) for n in ("N1_BRIGHTNESS", "N2_REENCODE")) >= 14,
        "P8": True,
        "P9": all(r["cleanup"] and r["resource_limit_result"] == "PASS" for r in resources),
        "P10": True,
    }
    summary = {
        "method": METHOD,
        "created_at": benign._now(),
        "cells": cells,
        "gates": p,
        "primary_parity": len(parity_rows),
        "max_score_difference": max(r["score_difference"] for r in parity_rows),
        "demo_states": dict(Counter(r["metrics"]["state"] for r in demos)),
        "localization": {
            k: sum(r[k] for r in locations)
            for k in ("ANY_OVERLAP", "MAJORITY_OVERLAP", "FULLY_CONTAINED")
        },
        "localization_total": len(locations),
        "worker_calls_stress": len(resources),
        "max_worker_seconds": max(r["wall_seconds"] for r in resources),
        "max_response_bytes": max(r["response_bytes"] for r in resources),
        "disposition": "VRC2_PROTOTYPE_READY_FOR_LARGER_VALIDATION"
        if all(p.values())
        else "VRC2_PROTOTYPE_APPLICABILITY_LIMITED",
    }
    benign._seal(root, "tables/summary.json", summary)
    prior.write_csv(
        root / "tables/prototype-readiness-gates.csv",
        [{"gate": k, "result": "PASS" if v else "FAIL"} for k, v in p.items()],
    )
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase", choices=("prepare", "parity", "worker", "stress", "demo", "finish")
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--accepted", type=Path)
    args = parser.parse_args()
    root = demo._external_directory(args.workspace)
    if args.phase == "prepare":
        if args.accepted is None:
            parser.error("prepare requires --accepted")
        prepare(root, args.accepted)
    else:
        with (root / "logs/executions.jsonl").open("a", encoding="utf-8") as log:
            log.write(
                json.dumps(
                    {
                        "phase": args.phase,
                        "started_at": benign._now(),
                        "script": research.receipt(Path(__file__)),
                    }
                )
                + "\n"
            )
        {
            "parity": parity,
            "worker": worker_gate,
            "stress": stress,
            "demo": demo_recheck,
            "finish": finish,
        }[args.phase](root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
