"""Bounded, licensed benign audio/video validation of the frozen diploma ensemble.

From the checkout: uv run python -m scripts.diploma_benign_validation
declare|acquire|prepare|evaluate|report --workspace ABSOLUTE_EXTERNAL_DIRECTORY.
Source selection and splits precede downloads and all score inspection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import secrets
import statistics
import subprocess
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fakedetector.application import AnalysisApplicationError
from fakedetector.domain import AnalysisResult, SourceChannel, SourceContext
from scripts import diploma_demo_evaluation as demo

VERSION = "diploma-benign-1.0.0"
BASELINE = "bc301888281fdc6954b70c267c33354c12c1b39f"
MAX_SOURCE_BYTES = 40_000_000
MAX_TOTAL_BYTES = 128_000_000
SPLITS = ("observation", "holdout_benign")
ROLES = ("BENIGN_REFERENCE", "BENIGN_PROCESSING", "BENIGN_CONFOUND")
LICENSES = {
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "Public domain": "https://creativecommons.org/publicdomain/mark/1.0/",
}
VRC = "video_repeated_content_correspondence"
VQUALITY = "video_sampled_frame_quality"
ATD = "audio_temporal_discontinuity"
ASC = "audio_spectral_consistency"


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    title: str
    content_category: str
    secondary_role: str = "BENIGN_PROCESSING"

    @property
    def split(self) -> str:
        return "holdout_benign" if int(self.source_id[-2:]) in {3, 6, 8} else "observation"


SOURCES = (
    SourceSpec("audio-01", "Ave Maria Italian.ogg", "speech"),
    SourceSpec(
        "audio-02",
        "Blue Danube (Exercise and variations-collections in piano) JMC, Han.ogg",
        "music",
    ),
    SourceSpec("audio-03", "Sound of rain.ogg", "ambient_rain"),
    SourceSpec("audio-04", "Birdsong Bourne Woods 2020-04-27 0722.mp3", "birds"),
    SourceSpec("audio-05", "Thunder.wav", "transient_thunder"),
    SourceSpec("audio-06", "Grandfather Clock Ticking.ogg", "periodic_clock", "BENIGN_CONFOUND"),
    SourceSpec(
        "audio-07",
        "Church bells playing in Astoria, Queens, New York City.ogg",
        "periodic_bells",
        "BENIGN_CONFOUND",
    ),
    SourceSpec(
        "audio-08",
        "Audio Hörbild Grillenzirpen - nachts um 3 im Föhrenwald Mödling.ogg",
        "night_ambient",
    ),
    SourceSpec("video-01", "Steam train at station.webm", "continuous_motion"),
    SourceSpec("video-02", "Small waterfall.webm", "natural_outdoor"),
    SourceSpec(
        "video-03", "Dog walking in the Mission in San Francisco.ogv", "person_camera_motion"
    ),
    SourceSpec(
        "video-04",
        "Windmill-1070685, Dingle Peninsula, Co. Kerry, Ireland.webm",
        "periodic_motion",
        "BENIGN_CONFOUND",
    ),
    SourceSpec("video-05", "Panorama from the Old Town Hall Tower, Prague (1).ogg", "camera_pan"),
    SourceSpec(
        "video-06", "The concept of a static identity is a huge mistake-HD.webm", "talking_person"
    ),
    SourceSpec(
        "video-07",
        "Old VHS tape ending black screen static.webm",
        "static_noise",
        "BENIGN_CONFOUND",
    ),
    SourceSpec("video-08", "Big Buck Bunny Trailer 400p.ogv", "animation_cuts"),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _seal(root: Path, name: str, value: Any) -> None:
    path = demo._owned_path(root, name)
    demo._write_json(path, value)
    with demo._owned_path(root, name + ".sha256").open("x", encoding="ascii") as stream:
        stream.write(_hash_file(path) + "\n")


def _sealed(root: Path, name: str) -> Any:
    path = demo._owned_path(root, name)
    if (
        _hash_file(path)
        != demo._owned_path(root, name + ".sha256").read_text(encoding="ascii").strip()
    ):
        raise ValueError(f"Seal mismatch: {name}")
    return demo._read_json(path)


def _url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"commons.wikimedia.org", "upload.wikimedia.org"}
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Acquisition permits only HTTPS Wikimedia source URLs")
    return url


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        return super().redirect_request(req, fp, code, msg, headers, _url(newurl))


def _download(url: str, target: Path, cap: int, expected_size: int | None = None) -> dict[str, Any]:
    """Exclusive bounded streaming; incomplete attempts remain evidence, never overwrite."""
    demo._external_directory(target)
    request = urllib.request.Request(
        _url(url),
        headers={"User-Agent": "FakeDetectorResearch/1.0 (bounded licensed academic validation)"},
    )
    opener = urllib.request.build_opener(_Redirect())
    with opener.open(request, timeout=45) as response:
        _url(response.geturl())
        announced = response.headers.get("Content-Length")
        if announced and (int(announced) > cap or int(announced) < 0):
            raise ValueError("Announced download exceeds cap")
        if expected_size is not None and announced and int(announced) != expected_size:
            raise ValueError("Download size changed from declared source")
        size = 0
        digest = hashlib.sha256()
        with target.open("xb") as output:
            while chunk := response.read(min(65536, cap - size + 1)):
                size += len(chunk)
                if size > cap:
                    raise ValueError("Streaming download exceeds cap")
                output.write(chunk)
                digest.update(chunk)
        if not size or (expected_size is not None and size != expected_size):
            raise ValueError("Incomplete source download")
    return {"sha256": digest.hexdigest(), "size_bytes": size, "retrieved_at": _now()}


def _plain(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", value)).strip()


def _license(name: str, url: str) -> str:
    canonical = LICENSES.get(name)
    normalized = url.replace("http://", "https://").removesuffix("deed.en").rstrip("/") + "/"
    if canonical is None or canonical != normalized:
        raise ValueError("Source does not have an explicitly allowed license")
    return canonical


def declare(workspace: Path) -> dict[str, Any]:
    root = demo._external_directory(workspace)
    root.mkdir(parents=True, exist_ok=True)
    proof = demo._owned_path(root, "licenses")
    proof.mkdir()
    policy = demo._policy()
    records = []
    for spec in SOURCES:
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "prop": "imageinfo|revisions",
                "rvprop": "ids",
                "iiprop": "url|size|extmetadata",
                "titles": "File:" + spec.title,
            }
        )
        api_url = "https://commons.wikimedia.org/w/api.php?" + query
        api_path = f"licenses/{spec.source_id}.json"
        api_receipt = _download(api_url, demo._owned_path(root, api_path), 2_000_000)
        page = next(iter(demo._read_json(root / api_path)["query"]["pages"].values()))
        info = page["imageinfo"][0]
        meta = info["extmetadata"]

        def value(key: str, metadata: dict[str, Any] = meta) -> str:
            return _plain(metadata.get(key, {}).get("value", ""))

        license_name = value("LicenseShortName")
        license_url = _license(license_name, value("LicenseUrl"))
        if info["duration"] < 12 or not 0 < info["size"] <= MAX_SOURCE_BYTES:
            raise ValueError(f"Source outside duration/size bounds: {spec.source_id}")
        page_url = info["descriptionurl"]
        html_path = f"licenses/{spec.source_id}.html"
        html_receipt = _download(page_url, demo._owned_path(root, html_path), 2_000_000)
        records.append(
            {
                **asdict(spec),
                "source_family": spec.source_id,
                "split": spec.split,
                "media_type": spec.source_id.split("-")[0],
                "source_page_url": page_url,
                "page_revision": page["revisions"][0]["revid"],
                "direct_media_url": _url(info["url"].split("?")[0]),
                "creator": value("Artist"),
                "license_name": license_name,
                "license_url": license_url,
                "source_description": value("ImageDescription"),
                "source_credit": value("Credit"),
                "original_size_bytes": info["size"],
                "source_duration_seconds": info["duration"],
                "original_filename": f"sources/{spec.source_id}{Path(spec.title).suffix}",
                "source_start_seconds": 0,
                "source_end_seconds": 12,
                "api_url": api_url,
                "license_snapshot": api_path,
                "license_sha256": api_receipt["sha256"],
                "page_snapshot": html_path,
                "page_sha256": html_receipt["sha256"],
                "license_checked_at": html_receipt["retrieved_at"],
            }
        )
        print(f"declared {spec.source_id}: {license_name}", flush=True)
    validate_sources(records)
    plan = {
        "version": VERSION,
        "baseline_head": BASELINE,
        "declared_at": _now(),
        "policy": policy,
        "environment": demo._environment(),
        "sources": records,
    }
    _seal(root, "source-plan.json", plan)
    return plan


def validate_sources(rows: list[dict[str, Any]], *, acquired: bool = False) -> None:
    specs = {s.source_id: s for s in SOURCES}
    if len(rows) != len(specs) or {r.get("source_id") for r in rows} != set(specs):
        raise ValueError("Declared source membership mismatch")
    if sum(r["original_size_bytes"] for r in rows) > MAX_TOTAL_BYTES:
        raise ValueError("Total declared acquisition exceeds cap")
    for row in rows:
        spec = specs[row["source_id"]]
        for key, value in asdict(spec).items():
            if row.get(key) != value:
                raise ValueError(f"Source schema mismatch: {key}")
        if (
            row["source_family"] != spec.source_id
            or row["split"] != spec.split
            or row["media_type"] != spec.source_id.split("-")[0]
            or row["original_filename"] != f"sources/{spec.source_id}{Path(spec.title).suffix}"
            or row["source_start_seconds"] != 0
            or row["source_end_seconds"] != 12
        ):
            raise ValueError("Source-family, split, interval or filename changed")
        if (
            not isinstance(row["original_size_bytes"], int)
            or isinstance(row["original_size_bytes"], bool)
            or not 0 < row["original_size_bytes"] <= MAX_SOURCE_BYTES
            or not isinstance(row["creator"], str)
            or not row["creator"].strip()
        ):
            raise ValueError("Invalid source size/attribution")
        _license(row["license_name"], row["license_url"])
        _url(row["source_page_url"])
        _url(row["direct_media_url"])
        if acquired:
            if not re.fullmatch(r"[0-9a-f]{64}", row["original_sha256"]):
                raise ValueError("Invalid original SHA-256")
            if datetime.fromisoformat(row["retrieved_at"]).tzinfo is None:
                raise ValueError("Acquisition timestamp must include timezone")
    demo._json_bytes(rows)  # Reject nonfinite values before persistence or CSV export.


def _check_file(root: Path, filename: str, size: int, digest: str) -> None:
    path = demo._owned_path(root, filename)
    if path.stat().st_size != size or _hash_file(path) != digest:
        raise ValueError(f"Artifact SHA-256/size mismatch: {filename}")


def _plan(root: Path) -> dict[str, Any]:
    plan = _sealed(root, "source-plan.json")
    validate_sources(plan["sources"])
    if plan["policy"] != demo._policy() or plan["environment"] != demo._environment():
        raise ValueError("Model/runtime/environment changed since declaration")
    for row in plan["sources"]:
        for path_key, hash_key in (
            ("license_snapshot", "license_sha256"),
            ("page_snapshot", "page_sha256"),
        ):
            if _hash_file(demo._owned_path(root, row[path_key])) != row[hash_key]:
                raise ValueError("License evidence changed")
    return plan


def acquire(workspace: Path) -> list[dict[str, Any]]:
    root = demo._external_directory(workspace)
    plan = _plan(root)
    if demo._owned_path(root, "source-manifest.json").exists():
        return _sources(root)
    demo._owned_path(root, "sources").mkdir(exist_ok=True)
    rows = []
    for row in plan["sources"]:
        receipt_name = f"sources/{row['source_id']}-receipt.json"
        receipt_path = demo._owned_path(root, receipt_name)
        if receipt_path.exists():
            receipt = _sealed(root, receipt_name)
            _check_file(root, row["original_filename"], receipt["size_bytes"], receipt["sha256"])
        else:
            receipt = _download(
                row["direct_media_url"],
                demo._owned_path(root, row["original_filename"]),
                MAX_SOURCE_BYTES,
                row["original_size_bytes"],
            )
            _seal(root, receipt_name, receipt)
        if receipt["size_bytes"] != row["original_size_bytes"]:
            raise ValueError("Acquired size differs from declaration")
        rows.append(
            {**row, "original_sha256": receipt["sha256"], "retrieved_at": receipt["retrieved_at"]}
        )
        print(f"acquired {row['source_id']}: {receipt['size_bytes']} bytes", flush=True)
    validate_sources(rows, acquired=True)
    _seal(
        root,
        "source-manifest.json",
        {
            "source_plan_sha256": _hash_file(root / "source-plan.json"),
            "sources": rows,
        },
    )
    return rows


def _sources(root: Path) -> list[dict[str, Any]]:
    plan = _plan(root)
    manifest = _sealed(root, "source-manifest.json")
    if manifest["source_plan_sha256"] != _hash_file(root / "source-plan.json"):
        raise ValueError("Source declaration binding mismatch")
    rows = manifest["sources"]
    validate_sources(rows, acquired=True)
    if [
        {k: v for k, v in r.items() if k not in {"original_sha256", "retrieved_at"}} for r in rows
    ] != plan["sources"]:
        raise ValueError("Source provenance differs from frozen declaration")
    for row in rows:
        _check_file(
            root, row["original_filename"], row["original_size_bytes"], row["original_sha256"]
        )
    return rows


def sample_design(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in sources:
        media = source["media_type"]
        ext = "wav" if media == "audio" else "mp4"
        for variant in ("reference", "processed"):
            sid = f"{source['source_id']}-{variant}"
            rows.append(
                {
                    "sample_id": sid,
                    "source_id": source["source_id"],
                    "source_family": source["source_family"],
                    "media_type": media,
                    "content_category": source["content_category"],
                    "split": source["split"],
                    "role": "BENIGN_REFERENCE"
                    if variant == "reference"
                    else source["secondary_role"],
                    "variant": variant,
                    "filename": f"corpus/{sid}.{ext}",
                    "file_format": ext,
                    "evaluation_level": "FILE_LEVEL_E2E",
                    "source_start_seconds": 0,
                    "source_end_seconds": 12,
                    "source_sha256": source["original_sha256"],
                    "license_name": source["license_name"],
                    "license_url": source["license_url"],
                    "creator": source["creator"],
                    "source_page_url": source["source_page_url"],
                    "input_filename": source["original_filename"]
                    if variant == "reference"
                    else f"corpus/{source['source_id']}-reference.{ext}",
                }
            )
    return rows


def ffmpeg_command(sample: dict[str, Any]) -> list[str]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-n",
        "-threads",
        "1",
        "-i",
        sample["input_filename"],
        "-ss",
        "0",
        "-t",
        "12",
        "-map_metadata",
        "-1",
    ]
    reference = sample["variant"] == "reference"
    if sample["media_type"] == "audio":
        command += [
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000" if reference else "8000",
            "-c:a",
            "pcm_s16le",
            "-flags:a",
            "+bitexact",
        ]
    else:
        size, fps = ("480:270", "24") if reference else ("320:180", "15")
        command += [
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            f"scale={size}:force_original_aspect_ratio=decrease:force_divisible_by=2,fps={fps}",
            "-c:v",
            "mpeg4",
            "-q:v",
            "2" if reference else "5",
            "-g",
            "1" if reference else "12",
            "-threads",
            "1",
            "-flags:v",
            "+bitexact",
            "-pix_fmt",
            "yuv420p",
            "-video_track_timescale",
            "24000",
        ]
    return command + ["-fflags", "+bitexact", sample["filename"]]


def prepare(workspace: Path) -> dict[str, Any]:
    root = demo._external_directory(workspace)
    sources = _sources(root)
    design = sample_design(sources)
    demo._owned_path(root, "corpus").mkdir()
    freeze = {
        "version": VERSION,
        "prepared_at": _now(),
        "policy": demo._policy(),
        "environment": demo._environment(),
        "source_manifest_sha256": _hash_file(root / "source-manifest.json"),
        "tool_sha256_lf": demo._digest(Path(__file__).read_text(encoding="utf-8").encode()),
        "design": [{**r, "ffmpeg_command": ffmpeg_command(r)} for r in design],
    }
    _seal(root, "freeze.json", freeze)
    rows = []
    for row in freeze["design"]:
        for key in ("input_filename", "filename"):
            demo._owned_path(root, row[key])
        subprocess.run(
            row["ffmpeg_command"], cwd=root, check=True, capture_output=True, timeout=120
        )
        path = root / row["filename"]
        rows.append({**row, "size_bytes": path.stat().st_size, "sha256": _hash_file(path)})
        print(f"prepared {row['sample_id']}", flush=True)
    _seal(
        root, "manifest.json", {"freeze_sha256": _hash_file(root / "freeze.json"), "samples": rows}
    )
    return load_manifest(root)


def load_manifest(workspace: Path) -> dict[str, Any]:
    root = demo._external_directory(workspace)
    sources = _sources(root)
    freeze = _sealed(root, "freeze.json")
    manifest = _sealed(root, "manifest.json")
    if (
        freeze["policy"] != demo._policy()
        or freeze["environment"] != demo._environment()
        or freeze["source_manifest_sha256"] != _hash_file(root / "source-manifest.json")
        or manifest["freeze_sha256"] != _hash_file(root / "freeze.json")
    ):
        raise ValueError("Model/environment/manifest binding changed")
    expected = [{**r, "ffmpeg_command": ffmpeg_command(r)} for r in sample_design(sources)]
    actual = [
        {k: v for k, v in r.items() if k not in {"sha256", "size_bytes"}}
        for r in manifest["samples"]
    ]
    if freeze["design"] != expected or actual != expected:
        raise ValueError("Frozen source-family split, recipe or sample membership changed")
    for row in manifest["samples"]:
        _check_file(root, row["filename"], row["size_bytes"], row["sha256"])
    return manifest


def evaluate(workspace: Path) -> None:
    root = demo._external_directory(workspace)
    manifest = load_manifest(root)
    for directory in ("results", "runtime", "logs"):
        demo._owned_path(root, directory).mkdir()
    _seal(
        root,
        "results/run.json",
        {
            "manifest_sha256": _hash_file(root / "manifest.json"),
            "started_at": _now(),
            "policy": demo._policy(),
            "tool_sha256_lf": demo._digest(Path(__file__).read_text(encoding="utf-8").encode()),
            "boundary": "AnalysisApplicationService.submit -> persisted get_result",
            "config_overrides": [
                "temporary_storage.root_path",
                "result.directory",
                "logging.jsonl_path",
            ],
        },
    )
    config = demo._config(root)
    temporary = {
        config.access_channels.api.token_env_var: secrets.token_urlsafe(32),
        config.access_channels.webui.credentials_env_var: "benign:" + secrets.token_urlsafe(32),
    }
    added = [key for key in temporary if key not in os.environ]
    for key in added:
        os.environ[key] = temporary[key]
    try:
        app = demo.create_app(config)
    finally:
        for key in added:
            del os.environ[key]
    runtime, service = app.state.runtime, app.state.application_service
    runtime.scheduler.start()
    journal = root / "results/index.jsonl"
    try:
        with journal.open("x", encoding="utf-8", newline="\n") as index:
            for sample in manifest["samples"]:
                started = time.monotonic()
                result = None
                entry = {
                    "sample_id": sample["sample_id"],
                    "analysis_id": None,
                    "result_file": None,
                    "failure": None,
                }
                try:
                    with demo._owned_path(root, sample["filename"]).open("rb") as stream:
                        submitted = service.submit(
                            stream,
                            original_name=Path(sample["filename"]).name,
                            declared_content_type=demo.MIME[sample["file_format"]],
                            source=SourceContext(channel=SourceChannel.API),
                        )
                    entry["analysis_id"] = submitted.analysis_id
                    result = demo._wait_result(
                        service,
                        submitted.analysis_id,
                        config.limits.processing_timeout_seconds + 180,
                    )
                except TimeoutError:
                    entry["failure"] = "harness_timeout"
                except (AnalysisApplicationError, OSError) as error:
                    entry["failure"] = type(error).__name__
                if result is not None:
                    relative = f"results/{sample['sample_id']}.json"
                    demo._write_json(
                        demo._owned_path(root, relative), result.model_dump(mode="json")
                    )
                    entry.update(result_file=relative, result_sha256=_hash_file(root / relative))
                entry["wall_seconds"] = time.monotonic() - started
                index.write(json.dumps(entry, allow_nan=False, sort_keys=True) + "\n")
                index.flush()
                os.fsync(index.fileno())
                status = result.status.value if result else entry["failure"]
                print(f"evaluated {sample['sample_id']}: {status}", flush=True)
    finally:
        runtime.scheduler.shutdown(drain=True)
    load_manifest(root)
    _seal(
        root,
        "results/complete.json",
        {
            "sample_count": len(manifest["samples"]),
            "index_sha256": _hash_file(journal),
            "completed_at": _now(),
        },
    )


def extract_result(
    sample: dict[str, Any], result: AnalysisResult | None, *, failure: str | None = None
) -> dict[str, Any]:
    row = demo.extract_result(sample, result, failure=failure)
    raw = {a.analyzer_id: a.raw_metrics for a in result.analyzers} if result else {}
    for analyzer in row["analyzers"]:
        analyzer["raw_metrics"] = raw.get(analyzer["analyzer_id"])
    ranked = sorted(row["families"], key=lambda f: (-f["response"], f["evidence_family"]))
    row["dominant_family"] = (
        ranked[0]["evidence_family"] if ranked and ranked[0]["response"] > 0 else None
    )
    return row


def _finite(values: list[float]) -> None:
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError("Finite numeric observations required")


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y):
        raise ValueError("Correlation vectors differ in length")
    _finite(x + y)
    if len(x) < 2:
        return None
    dx, dy = [v - statistics.fmean(x) for v in x], [v - statistics.fmean(y) for v in y]
    xx, yy = math.fsum(v * v for v in dx), math.fsum(v * v for v in dy)
    if xx == 0 or yy == 0:
        return None
    return max(
        -1.0, min(1.0, math.fsum(a * b for a, b in zip(dx, dy, strict=True)) / math.sqrt(xx * yy))
    )


def ranks(values: list[float]) -> list[float]:
    _finite(values)
    order = sorted(range(len(values)), key=values.__getitem__)
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        end = i + 1
        while end < len(order) and values[order[end]] == values[order[i]]:
            end += 1
        for index in order[i:end]:
            out[index] = (i + 1 + end) / 2
        i = end
    return out


def spearman(x: list[float], y: list[float]) -> float | None:
    return pearson(ranks(x), ranks(y))


def distribution(values: list[float]) -> dict[str, Any]:
    _finite(values)
    ordered = sorted(values)

    def quantile(p: float) -> float | None:
        if not ordered:
            return None
        at = (len(ordered) - 1) * p
        left, right = math.floor(at), math.ceil(at)
        return ordered[left] + (at - left) * (ordered[right] - ordered[left])

    return {
        "n": len(values),
        **{
            k: quantile(p)
            for k, p in (("min", 0), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("max", 1))
        },
    }


def vrc_distribution(values: list[float]) -> dict[str, Any]:
    summary = distribution(values)
    if any(not 0 <= v <= 1 for v in values):
        raise ValueError("VRC response outside unit interval")
    summary["buckets"] = {
        "zero": sum(v == 0 for v in values),
        "gt0_lt025": sum(0 < v < 0.25 for v in values),
        "ge025_lt050": sum(0.25 <= v < 0.5 for v in values),
        "ge050_lt075": sum(0.5 <= v < 0.75 for v in values),
        "ge075": sum(v >= 0.75 for v in values),
    }
    return summary


def _family(row: dict[str, Any], name: str) -> float | None:
    family = next((f for f in row["families"] if f["evidence_family"] == name), None)
    return family["response"] if family and family["usable_members"] else None


def _analyzer(row: dict[str, Any], name: str) -> dict[str, Any]:
    return next((a for a in row["analyzers"] if a["analyzer_id"] == name), {})


def _rate(n: int, total: int) -> dict[str, Any]:
    return {"numerator": n, "denominator": total, "rate": n / total if total else None}


def _score_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assessed = [r for r in rows if r["overall_score"] is not None]
    families = {r["source_family"] for r in rows}
    out = {
        "samples": len(rows),
        "source_families": len(families),
        "assessed": len(assessed),
        "unassessed": len(rows) - len(assessed),
        "risk_levels": dict(Counter(r["risk_level"] or "unassessed" for r in rows)),
        "score": distribution([r["overall_score"] for r in assessed]),
    }
    for threshold in (25, 55):
        elevated = [r for r in assessed if r["overall_score"] > threshold]
        out[f"gt{threshold}"] = {
            "sample": _rate(len(elevated), len(rows)),
            "assessed_sample": _rate(len(elevated), len(assessed)),
            "source_family_any": _rate(len({r["source_family"] for r in elevated}), len(families)),
            "sample_ids": [r["sample_id"] for r in elevated],
        }
    return out


def correlation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [(_family(r, "video_quality"), _family(r, "video_repetition")) for r in rows]
    valid = [(a, b) for a, b in pairs if a is not None and b is not None]
    x, y = [p[0] for p in valid], [p[1] for p in valid]
    return {
        "samples": len(rows),
        "defined_pairs": len(valid),
        "unavailable": len(rows) - len(valid),
        "joint_nonzero": sum(a > 0 and b > 0 for a, b in valid),
        "quality_only": sum(a > 0 and b == 0 for a, b in valid),
        "repetition_only": sum(a == 0 and b > 0 for a, b in valid),
        "both_zero": sum(a == 0 and b == 0 for a, b in valid),
        "pearson": pearson(x, y),
        "spearman": spearman(x, y),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "samples": len(rows),
        "roles": dict(Counter(r["role"] for r in rows)),
        "statuses": dict(Counter(r["analysis_status"] for r in rows)),
        "analyzer_states": dict(Counter(a["response_state"] for r in rows for a in r["analyzers"])),
        "analyzer_statuses": dict(Counter(a["status"] for r in rows for a in r["analyzers"])),
        "media": {},
    }
    for media in ("audio", "video"):
        group = [r for r in rows if r["media_type"] == media]
        summary = _score_summary(group)
        for key in ("content_category", "role", "source_family"):
            summary["by_" + key] = {
                value: _score_summary([r for r in group if r[key] == value])
                for value in sorted({r[key] for r in group})
            }
        result["media"][media] = summary
    video = [r for r in rows if r["media_type"] == "video"]
    values = [_analyzer(r, VRC).get("normalized_response") for r in video]
    result["vrc"] = vrc_distribution([v for v in values if v is not None])
    result["vrc"]["unavailable"] = sum(v is None for v in values)
    for label, predicate in (("nonzero", lambda x: x > 0), ("ge075", lambda x: x >= 0.75)):
        selected = [
            r
            for r in video
            if (v := _analyzer(r, VRC).get("normalized_response")) is not None and predicate(v)
        ]
        result["vrc"][label + "_sample"] = _rate(len(selected), len(video))
        result["vrc"][label + "_family_any"] = _rate(
            len({r["source_family"] for r in selected}), len({r["source_family"] for r in video})
        )
    result["vrc"]["by_content_category"] = {
        category: vrc_distribution(
            [
                v
                for r in video
                if r["content_category"] == category
                and (v := _analyzer(r, VRC).get("normalized_response")) is not None
            ]
        )
        for category in sorted({r["content_category"] for r in video})
    }
    result["video_correlation"] = correlation(video)
    joint_families = {
        r["source_family"]
        for r in video
        if (_family(r, "video_quality") or 0) > 0 and (_family(r, "video_repetition") or 0) > 0
    }
    result["video_correlation"]["joint_family_any"] = _rate(
        len(joint_families), len({r["source_family"] for r in video})
    )
    result["video_correlation"]["by_source_family"] = {
        family: correlation([r for r in video if r["source_family"] == family])
        for family in sorted({r["source_family"] for r in video})
    }
    family_means = []
    for family in sorted({r["source_family"] for r in video}):
        group = [r for r in video if r["source_family"] == family]
        observed = [(_family(r, "video_quality"), _family(r, "video_repetition")) for r in group]
        valid = [(a, b) for a, b in observed if a is not None and b is not None]
        if valid:
            family_means.append(
                (statistics.fmean(p[0] for p in valid), statistics.fmean(p[1] for p in valid))
            )
    result["video_correlation"]["source_family_means"] = {
        "n": len(family_means),
        "pearson": pearson([p[0] for p in family_means], [p[1] for p in family_means]),
        "spearman": spearman([p[0] for p in family_means], [p[1] for p in family_means]),
    }
    return result


def _csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    demo._json_bytes(rows)
    columns = fields or (list(rows[0]) if rows else ["sample_id"])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False, allow_nan=False)
                    if isinstance(v, (list, dict))
                    else v
                    for k, v in row.items()
                }
            )


def report(workspace: Path) -> dict[str, Any]:
    root = demo._external_directory(workspace)
    manifest = load_manifest(root)
    known = {r["sample_id"] for r in manifest["samples"]}
    entries = {}
    journal = demo._owned_path(root, "results/index.jsonl")
    if journal.exists():
        if _sealed(root, "results/run.json")["manifest_sha256"] != _hash_file(
            root / "manifest.json"
        ):
            raise ValueError("Evaluation manifest mismatch")
        if (root / "results/complete.json").exists() and _sealed(root, "results/complete.json")[
            "index_sha256"
        ] != _hash_file(journal):
            raise ValueError("Evaluation journal changed")
        for line in journal.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["sample_id"] not in known or entry["sample_id"] in entries:
                raise ValueError("Unknown/duplicate evaluated sample")
            entries[entry["sample_id"]] = entry
    rows = []
    for sample in manifest["samples"]:
        entry = entries.get(sample["sample_id"], {})
        result = None
        if entry.get("result_file"):
            path = demo._owned_path(root, entry["result_file"])
            if _hash_file(path) != entry["result_sha256"]:
                raise ValueError("Result hash changed")
            result = AnalysisResult.model_validate(demo._read_json(path))
            if result.analysis_id != entry["analysis_id"]:
                raise ValueError("Result identity mismatch")
        row = extract_result(sample, result, failure=entry.get("failure"))
        row["wall_seconds"] = entry.get("wall_seconds")
        rows.append(row)
    summary = {
        "version": VERSION,
        "model": "diploma_ensemble_v1@0.1.0",
        "manifest_sha256": _hash_file(root / "manifest.json"),
        "quantile_method": "linear interpolation at (n-1)*p; ranks use average ties",
        "all": aggregate(rows),
        "splits": {s: aggregate([r for r in rows if r["split"] == s]) for s in SPLITS},
    }
    tables = demo._owned_path(root, "tables")
    tables.mkdir(exist_ok=True)
    for filename, data in (("summary.json", summary), ("samples.json", rows)):
        demo._owned_path(root, "tables/" + filename).write_bytes(demo._json_bytes(data))

    def table(filename: str, data: list[dict[str, Any]], fields: list[str] | None = None) -> None:
        _csv(demo._owned_path(root, "tables/" + filename), data, fields)

    table("source-provenance.csv", _sources(root))
    table("sample-manifest.csv", manifest["samples"])
    flat = [{k: v for k, v in r.items() if k not in {"analyzers", "families"}} for r in rows]
    table("score-by-sample.csv", flat)
    keys = ("sample_id", "source_family", "media_type", "split", "role", "content_category")
    for key, name in (
        ("analyzers", "analyzer-responses.csv"),
        ("families", "family-responses.csv"),
    ):
        table(name, [{**{k: r[k] for k in keys}, **item} for r in rows for item in r[key]])
    family_rows = []
    for family in sorted({r["source_family"] for r in rows}):
        group = [r for r in rows if r["source_family"] == family]
        reference = next(r for r in group if r["variant"] == "reference")
        processed = next(r for r in group if r["variant"] == "processed")
        a, b = reference["overall_score"], processed["overall_score"]
        family_rows.append(
            {
                "source_family": family,
                "media_type": group[0]["media_type"],
                "split": group[0]["split"],
                "content_category": group[0]["content_category"],
                **_score_summary(group),
                "reference_score": a,
                "processed_score": b,
                "pair_delta": b - a if a is not None and b is not None else None,
                "video_quality_mean": statistics.fmean(v)
                if (
                    v := [
                        _family(r, "video_quality")
                        for r in group
                        if _family(r, "video_quality") is not None
                    ]
                )
                else None,
                "video_repetition_mean": statistics.fmean(v)
                if (
                    v := [
                        _family(r, "video_repetition")
                        for r in group
                        if _family(r, "video_repetition") is not None
                    ]
                )
                else None,
            }
        )
    table("source-family-summary.csv", family_rows)
    audio = []
    for row in rows:
        if row["media_type"] != "audio":
            continue
        audio.append(
            {
                **{k: row[k] for k in keys},
                "overall_score": row["overall_score"],
                "risk_level": row["risk_level"],
                "dominant_family": row["dominant_family"],
                **{
                    f["evidence_family"]: _family(row, f["evidence_family"])
                    for f in row["families"]
                },
                "atd_response": _analyzer(row, ATD).get("normalized_response"),
                "asc_response": _analyzer(row, ASC).get("normalized_response"),
                "atd_factor": _analyzer(row, ATD).get("family_factor"),
                "asc_factor": _analyzer(row, ASC).get("family_factor"),
            }
        )
    table("audio-responses.csv", audio)
    elevated = [r for r in audio if r["overall_score"] is not None and r["overall_score"] > 25]
    table("audio-elevated.csv", elevated, list(audio[0]) if audio else None)
    video = []
    for row in rows:
        if row["media_type"] != "video":
            continue
        analyzer = _analyzer(row, VRC)
        raw = analyzer.get("raw_metrics") or {}
        quality = _analyzer(row, VQUALITY).get("raw_metrics") or {}
        q, r = _family(row, "video_quality"), _family(row, "video_repetition")
        video.append(
            {
                **{k: row[k] for k in keys},
                "overall_score": row["overall_score"],
                "risk_level": row["risk_level"],
                "vrc_normalized": analyzer.get("normalized_response"),
                "vrc_effective": analyzer.get("effective_weighted_response"),
                "vrc_state": analyzer.get("response_state"),
                "eligible_pairs": raw.get("eligible_pairs"),
                "minimum_color_pair": raw.get("minimum_color_pair"),
                "minimum_delta_pair": raw.get("minimum_delta_pair"),
                "zero_descriptor_pairs": raw.get("zero_descriptor_pairs"),
                "video_quality": q,
                "video_repetition": r,
                "quality_plus_repetition": q + r if q is not None and r is not None else None,
                **{
                    k: quality.get(k)
                    for k in (
                        "sampled_frame_count",
                        "exact_duplicate_pair_count",
                        "longest_exact_duplicate_run_samples",
                        "longest_exact_duplicate_span_seconds",
                    )
                },
            }
        )
    table("video-vrc-baseline.csv", video)
    table(
        "video-quality-vrc-correlation.csv",
        sorted(
            video,
            key=lambda r: (
                r["quality_plus_repetition"] is None,
                -(r["quality_plus_repetition"] or 0),
                r["sample_id"],
            ),
        ),
    )
    markdown = [
        "# Описательная benign-валидация",
        "",
        "BENIGN_REFERENCE не означает forensic authenticity.",
        "",
    ]
    for label, data in (("all", summary["all"]), *summary["splits"].items()):
        markdown += [
            f"## {label}",
            "",
            "```json",
            json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
            "```",
            "",
        ]
    demo._owned_path(root, "tables/report.md").write_text("\n".join(markdown), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("declare", "acquire", "prepare", "evaluate", "report"))
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    {
        "declare": declare,
        "acquire": acquire,
        "prepare": prepare,
        "evaluate": evaluate,
        "report": report,
    }[args.command](args.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
