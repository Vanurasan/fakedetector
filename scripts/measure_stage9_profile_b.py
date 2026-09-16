"""Measure the full local Profile B workflow without defining a performance SLA."""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import wave
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import numpy as np
import yaml
from PIL import Image

from fakedetector.app import create_app
from fakedetector.application import AnalysisPendingError
from fakedetector.config.models import AppConfig
from fakedetector.domain import SourceChannel, SourceContext

_EXAMPLE_CONFIG = Path(__file__).resolve().parents[1] / "config" / "config.example.yaml"
_MEDIA = ("image", "audio", "video")
_POLL_INTERVAL_SECONDS = 0.01
_RESULT_TIMEOUT_SECONDS = 60.0
_MIB = 1024 * 1024


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _memory_snapshot() -> dict[str, int | str | None]:
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        ):
            return {
                "metric": "win32_working_set_bytes",
                "current_rss_bytes": None,
                "peak_rss_bytes": None,
            }
        return {
            "metric": "win32_working_set_bytes",
            "current_rss_bytes": int(counters.WorkingSetSize),
            "peak_rss_bytes": int(counters.PeakWorkingSetSize),
        }

    try:
        import resource

        maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (ImportError, OSError, ValueError):
        return {
            "metric": "unavailable",
            "current_rss_bytes": None,
            "peak_rss_bytes": None,
        }
    multiplier = 1 if sys.platform == "darwin" else 1024
    return {
        "metric": "posix_ru_maxrss_bytes",
        "current_rss_bytes": None,
        "peak_rss_bytes": maximum * multiplier,
    }


def _config(root: Path) -> AppConfig:
    raw = yaml.safe_load(_EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(root / "temp")
    raw["temporary_storage"]["cleanup_retries"] = 0
    raw["temporary_storage"]["quarantine_enabled"] = False
    raw["logging"]["jsonl_path"] = str(root / "logs" / "application.jsonl")
    raw["result"]["directory"] = str(root / "results")
    raw["limits"]["max_parallel_tasks"] = {"image": 1, "audio": 1, "video": 1}
    raw["limits"]["processing_timeout_seconds"] = 60
    raw["analyzers"]["defaults"]["timeout_seconds"] = 30
    raw["preprocessing"]["video"]["keyframe_interval_seconds"] = 1
    return AppConfig.model_validate(raw)


def _image_fixture() -> bytes:
    rng = np.random.default_rng(217)
    canvas = np.full((512, 512, 3), 24, dtype=np.uint8)
    patch = rng.integers(0, 256, size=(112, 112, 3), dtype=np.uint8)
    canvas[64:176, 48:160] = patch
    canvas[300:412, 320:432] = patch
    output = BytesIO()
    with Image.fromarray(canvas) as image:
        image.save(output, format="PNG")
    return output.getvalue()


def _audio_fixture() -> bytes:
    samples = np.full(8_000, 1_000, dtype="<i2")
    samples[::100] = 32_767
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(samples.tobytes())
    return output.getvalue()


def _video_fixture(root: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("FFmpeg is required for the Profile B measurement.")
    path = root / "profile-b-video.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:r=2",
            "-t",
            "3.2",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15.0,
        check=True,
    )
    return path.read_bytes()


def _fixture(
    media: Literal["image", "audio", "video"],
    root: Path,
) -> tuple[str, str, bytes]:
    if media == "image":
        return "profile-b.png", "image/png", _image_fixture()
    if media == "audio":
        return "profile-b.wav", "audio/wav", _audio_fixture()
    return "profile-b.mp4", "video/mp4", _video_fixture(root)


def _wait_for_result(app: Any, analysis_id: str):
    deadline = time.monotonic() + _RESULT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            return app.state.application_service.get_result(analysis_id)
        except AnalysisPendingError:
            time.sleep(_POLL_INTERVAL_SECONDS)
    raise RuntimeError("Profile B workflow did not finish within its correctness timeout.")


def _measure_one(media: Literal["image", "audio", "video"]) -> dict[str, object]:
    os.environ.setdefault("MEDIA_ANALYZER_API_TOKEN", "stage9-measurement-token")
    os.environ.setdefault(
        "MEDIA_ANALYZER_WEBUI_CREDENTIALS",
        "stage9-measurement:stage9-measurement",
    )
    with tempfile.TemporaryDirectory(prefix="fakedetector-stage9-measurement-") as directory:
        root = Path(directory)
        original_name, declared_type, payload = _fixture(media, root)
        config = _config(root)
        app = create_app(config)
        runtime = app.state.runtime
        before = _memory_snapshot()
        started = time.perf_counter()
        runtime.scheduler.start()
        try:
            submission = app.state.application_service.submit(
                BytesIO(payload),
                original_name=original_name,
                declared_content_type=declared_type,
                source=SourceContext(channel=SourceChannel.API),
            )
            result = _wait_for_result(app, submission.analysis_id)
        finally:
            runtime.scheduler.shutdown(drain=True)
        wall_seconds = time.perf_counter() - started
        after = _memory_snapshot()
        result_path = Path(config.result.directory) / f"{submission.analysis_id}.json"
        if result.status.value != "completed" or not result_path.is_file():
            raise RuntimeError("Profile B measurement did not produce a completed result.")
        workspace = Path(config.temporary_storage.root_path) / submission.analysis_id
        if workspace.exists():
            raise RuntimeError("Profile B measurement retained its analysis workspace.")
        return {
            "media": media,
            "fixture_bytes": len(payload),
            "result_bytes": result_path.stat().st_size,
            "wall_seconds": wall_seconds,
            "rss_metric": after["metric"],
            "baseline_current_rss_bytes": before["current_rss_bytes"],
            "baseline_peak_rss_bytes": before["peak_rss_bytes"],
            "peak_rss_bytes": after["peak_rss_bytes"],
            "analyzer_count": len(result.analyzers),
            "finding_count": len(result.findings),
            "status": result.status.value,
            "cleanup_status": None if result.cleanup is None else result.cleanup.status.value,
        }


def _run_child(media: str) -> int:
    if media not in _MEDIA:
        raise RuntimeError("Unsupported measurement media selector.")
    print(json.dumps(_measure_one(media), ensure_ascii=False, sort_keys=True))
    return 0


def _invoke_child(media: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", media],
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120.0,
        check=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Measurement child returned an invalid result.")
    return value


def _finite_nonnegative(value: object) -> bool:
    return isinstance(value, int | float) and math.isfinite(value) and value >= 0


def _parent(runs: int) -> int:
    started = time.perf_counter()
    raw_runs = [_invoke_child(media) for media in _MEDIA for _run_number in range(1, runs + 1)]
    total_wall_seconds = time.perf_counter() - started
    media_rows: list[dict[str, object]] = []
    for media in _MEDIA:
        selected = [item for item in raw_runs if item["media"] == media]
        wall_values = [float(item["wall_seconds"]) for item in selected]
        peaks = [
            int(item["peak_rss_bytes"]) for item in selected if item["peak_rss_bytes"] is not None
        ]
        media_rows.append(
            {
                "media": media,
                "fixture_bytes": selected[0]["fixture_bytes"],
                "runs": runs,
                "median_wall_seconds": statistics.median(wall_values),
                "max_wall_seconds": max(wall_values),
                "result_bytes": selected[0]["result_bytes"],
                "rss_metric": selected[0]["rss_metric"],
                "max_peak_rss_bytes": max(peaks) if peaks else None,
                "analyzer_count": selected[0]["analyzer_count"],
                "finding_count": selected[0]["finding_count"],
                "notes": (
                    "production application service; persisted completed result; cleanup completed"
                ),
            }
        )
    report = {
        "environment": {
            "os": platform.platform(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "cpu_model": platform.processor() or None,
            "logical_cpu_count": os.cpu_count(),
        },
        "measurement": {
            "analysis_runs_total": len(raw_runs),
            "runs_per_media": runs,
            "wallclock_scope": (
                "scheduler start through persisted result retrieval and graceful shutdown"
            ),
            "rss_scope": (
                "fresh workflow runner process only; spawned analyzer and FFmpeg "
                "process RSS excluded"
            ),
            "rss_limitation": (
                "Windows uses GetProcessMemoryInfo; POSIX uses ru_maxrss; "
                "unsupported platforms return null"
            ),
            "configured_worker_count": 3,
            "arbitrary_sla_enforced": False,
        },
        "wallclock_total_seconds": total_wall_seconds,
        "media": media_rows,
        "runs": raw_runs,
    }
    if not _finite_nonnegative(total_wall_seconds):
        raise RuntimeError("Measurement wallclock is invalid.")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the full Profile B workflow without pass/fail timing thresholds."
    )
    parser.add_argument("--runs", type=int, default=1, help="Measured runs per media type.")
    parser.add_argument("--child", choices=_MEDIA, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.runs <= 0:
        parser.error("--runs must be greater than zero")
    if args.child is not None:
        return _run_child(args.child)
    return _parent(args.runs)


if __name__ == "__main__":
    raise SystemExit(main())
