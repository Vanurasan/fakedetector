"""Sanity checks for the informational Stage 9 Profile B measurement harness."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path


def test_profile_b_measurement_is_structured_complete_and_threshold_free() -> None:
    runtime_artifacts_before = _runtime_artifacts()
    completed = subprocess.run(
        [sys.executable, "scripts/measure_stage9_profile_b.py", "--runs", "1"],
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180.0,
        check=True,
    )
    report = json.loads(completed.stdout)

    assert report["measurement"]["analysis_runs_total"] == 3
    assert report["measurement"]["runs_per_media"] == 1
    assert report["measurement"]["arbitrary_sla_enforced"] is False
    assert math.isfinite(report["wallclock_total_seconds"])
    assert report["wallclock_total_seconds"] >= 0
    assert {row["media"] for row in report["media"]} == {"image", "audio", "video"}

    for row in report["media"]:
        assert row["runs"] == 1
        assert row["fixture_bytes"] > 0
        assert row["result_bytes"] > 0
        assert math.isfinite(row["median_wall_seconds"])
        assert row["median_wall_seconds"] >= 0
        assert row["max_wall_seconds"] >= row["median_wall_seconds"]
        assert row["analyzer_count"] >= 1
        assert row["finding_count"] >= 1
        peak = row["max_peak_rss_bytes"]
        assert peak is None or peak > 0

    assert _runtime_artifacts() == runtime_artifacts_before


def _runtime_artifacts() -> set[Path]:
    artifacts: set[Path] = set()
    for directory in ("runtime", "temp", "results", "logs", "quarantine"):
        root = Path(directory)
        if root.exists():
            artifacts.update(root.rglob("*"))
    return artifacts
