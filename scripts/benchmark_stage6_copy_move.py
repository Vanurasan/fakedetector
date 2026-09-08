"""Reproducible Windows benchmark for the 12 MP copy-move analyzer bound."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from fakedetector.analyzers._image_copy_move import (
    ImageCopyMoveCorrespondenceAnalyzer,
    ImageCopyMoveCorrespondenceSettings,
)
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.domain import ImageTechnicalParameters, MediaType

_WIDTH = 4_000
_HEIGHT = 3_000
_PIXEL_COUNT = _WIDTH * _HEIGHT
_RUNS = 3
_SEED = 6_003
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


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _peak_working_set_mib() -> float:
    if os.name != "nt":
        raise RuntimeError("This benchmark records PeakWorkingSetSize on Windows only.")
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
    success = psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(),
        ctypes.byref(counters),
        counters.cb,
    )
    if not success:
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.PeakWorkingSetSize / _MIB


def _total_ram_mib() -> float:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MemoryStatusEx)]
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return status.ullTotalPhys / _MIB


def _cpu_model() -> str:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "ProcessorNameString")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except OSError:
        pass
    return platform.processor() or "unavailable"


def _fixture(path: Path) -> None:
    rng = np.random.default_rng(_SEED)
    low_resolution = rng.integers(0, 256, size=(_HEIGHT // 4, _WIDTH // 4), dtype=np.uint8)
    base = np.repeat(np.repeat(low_resolution, 4, axis=0), 4, axis=1)
    pixels = np.stack(
        (
            base,
            np.roll(base, 7, axis=1),
            np.roll(base, 11, axis=0),
        ),
        axis=2,
    )
    pixels[1_900:2_600, 2_900:3_600] = pixels[300:1_000, 400:1_100]
    with Image.fromarray(pixels, mode="RGB") as image:
        image.save(path, format="PNG", compress_level=6)


def _request(path: Path) -> AnalyzerRequest:
    settings = ImageCopyMoveCorrespondenceSettings()
    source = _ReadOnlyAnalyzerInput(path)
    return AnalyzerRequest(
        analysis_id="b" * 32,
        media_type=MediaType.IMAGE,
        file_facts=_AnalyzerFileFacts(
            extension="png",
            declared_mime_type="image/png",
            detected_mime_type="image/png",
            media_type=MediaType.IMAGE,
            size_bytes=path.stat().st_size,
            sha256="0" * 64,
            signature_match=True,
            safe_read=True,
            technical_parameters=ImageTechnicalParameters(
                width=_WIDTH,
                height=_HEIGHT,
                format="PNG",
                color_mode="RGB",
                frame_count=1,
                has_metadata=False,
            ),
        ),
        source=source,
        settings=settings,
        timeout_seconds=300.0,
        artifacts=(
            AnalyzerArtifactInput(
                artifact_id="benchmark_normalized_image",
                artifact_type="normalized_image",
                content=_ReadOnlyAnalyzerInput(path),
                format="png",
            ),
        ),
        metadata={
            "normalized": {
                "format": "png",
                "mode": "RGB",
                "width": _WIDTH,
                "height": _HEIGHT,
                "scope": "first_frame",
            }
        },
    )


def _child(path: Path) -> int:
    analyzer = ImageCopyMoveCorrespondenceAnalyzer()
    request = _request(path)
    if not analyzer.check_applicability(request).applicable:
        raise RuntimeError("The canonical 12 MP fixture is unexpectedly not applicable.")
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    result = analyzer.analyze(request)
    cpu_seconds = time.process_time() - cpu_started
    wall_seconds = time.perf_counter() - wall_started
    metrics = result.raw_metrics
    print(
        json.dumps(
            {
                "wall_seconds": wall_seconds,
                "cpu_seconds": cpu_seconds,
                "peak_working_set_mib": _peak_working_set_mib(),
                "keypoint_count": metrics["keypoint_count"],
                "descriptor_count": metrics["descriptor_count"],
                "match_count": metrics["spatially_separated_match_count"],
                "accepted_cluster_count": metrics["accepted_cluster_count"],
                "candidate_count": len(result.candidate_findings),
            },
            sort_keys=True,
        )
    )
    return 0


def _run_child(path: Path) -> dict[str, int | float]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", str(path)],
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300.0,
        check=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Benchmark child returned an invalid result.")
    return value


def _environment() -> dict[str, object]:
    settings = ImageCopyMoveCorrespondenceSettings()
    return {
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu_model": _cpu_model(),
        "logical_cpu_count": os.cpu_count(),
        "total_ram_mib": _total_ram_mib(),
        "python_version": platform.python_version(),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "analyzer_id": ImageCopyMoveCorrespondenceAnalyzer.analyzer_id,
        "analyzer_version": ImageCopyMoveCorrespondenceAnalyzer.analyzer_version,
        "settings": settings.model_dump(mode="json"),
    }


def _parent() -> int:
    with tempfile.TemporaryDirectory(prefix="fakedetector-stage6-benchmark-") as directory:
        fixture_path = Path(directory) / "copy-move-4000x3000.png"
        _fixture(fixture_path)
        _run_child(fixture_path)
        runs = [_run_child(fixture_path) for _ in range(_RUNS)]
        wall_values = [float(run["wall_seconds"]) for run in runs]
        report = {
            "environment": _environment(),
            "fixture": {
                "generator": "seeded 4x block texture with one copied 700x700 region",
                "rng_seed": _SEED,
                "width": _WIDTH,
                "height": _HEIGHT,
                "pixel_count": _PIXEL_COUNT,
                "png_size_bytes": fixture_path.stat().st_size,
            },
            "measurement": {
                "process_isolation": "one fresh child process per analyzer run",
                "ram_metric": "Win32 GetProcessMemoryInfo PeakWorkingSetSize",
                "warmup_runs_excluded": 1,
                "measured_runs": _RUNS,
            },
            "runs": [{"run": index, **run} for index, run in enumerate(runs, start=1)],
            "summary": {
                "median_wall_seconds": statistics.median(wall_values),
                "max_wall_seconds": max(wall_values),
                "max_peak_working_set_mib": max(float(run["peak_working_set_mib"]) for run in runs),
            },
        }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark image_copy_move_correspondence at its 12 MP bound."
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("image", nargs="?", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        if args.image is None:
            parser.error("benchmark child requires an image")
        return _child(args.image)
    if args.image is not None:
        parser.error("image is reserved for the benchmark child")
    return _parent()


if __name__ == "__main__":
    raise SystemExit(main())
