"""Verification report initialization and secret-redacted serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import common

_REPORT_NAME = "verification-report.json"


def _initial_report(*, output: Path, development: bool) -> dict[str, Any]:
    return {
        "tool_version": common._TOOL_VERSION,
        "certification_mode": "development" if development else "strict",
        "certified": False,
        "source_sha": None,
        "source_sha_at_end": None,
        "source_sha_stable": None,
        "source_tree_clean": False,
        "package_version": None,
        "output_directory": str(output),
        "overall_status": "running",
    }


def _write_report(
    report: dict[str, Any],
    *,
    output: Path,
    secret_values: tuple[str, ...],
) -> None:
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    rendered = common._redact(rendered, secret_values)
    (output / _REPORT_NAME).write_text(rendered, encoding="utf-8")
