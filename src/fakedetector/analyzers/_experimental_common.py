"""Small shared contracts for bounded, measurement-only diploma analyzers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import median

from pydantic import BaseModel, ConfigDict, JsonValue

from fakedetector.analyzers._models import Analyzer, AnalyzerRequest
from fakedetector.analyzers._real_common import _completed_real_result
from fakedetector.domain import AnalyzerResult


class _ExperimentalSettings(BaseModel):
    """Frozen measurement profiles have no user-tunable parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _measurement_result(
    analyzer: Analyzer,
    request: AnalyzerRequest,
    profile: str,
    metrics: dict[str, JsonValue],
    limitation: str,
) -> AnalyzerResult:
    if not isinstance(request.settings, _ExperimentalSettings):
        raise TypeError("unexpected experimental settings")
    return _completed_real_result(
        analyzer_id=analyzer.analyzer_id,
        analyzer_version=analyzer.analyzer_version,
        group=analyzer.group,
        request=request,
        summary=f"Experimental descriptive measurement. {limitation}",
        raw_metrics={"profile": profile, **metrics},
    )


def _distribution(values: Sequence[float | None]) -> dict[str, JsonValue]:
    """Nearest-rank p95; first maximum wins ties; undefined is never zero."""
    valid = [v for v in values if v is not None]
    if any(not math.isfinite(v) for v in valid):
        raise ValueError("nonfinite measurement")
    ordered = sorted(valid)
    maximum = max(valid) if valid else None
    return {
        "count": len(valid),
        "undefined_count": len(values) - len(valid),
        "median": median(valid) if valid else None,
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else None,
        "max": maximum,
        "max_index": values.index(maximum) if maximum is not None else None,
    }
