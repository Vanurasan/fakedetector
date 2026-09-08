"""Small shared helpers for the Stage 6 real technical analyzers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import JsonValue

from fakedetector.analyzers._candidates import _candidate_transport, _TypedCandidate
from fakedetector.analyzers._models import AnalyzerArtifactInput, AnalyzerRequest
from fakedetector.domain import AnalyzerResult, AnalyzerStatus

_MAX_REAL_ANALYZER_CANDIDATES = 16


def _artifacts(request: AnalyzerRequest, artifact_type: str) -> tuple[AnalyzerArtifactInput, ...]:
    return tuple(
        artifact for artifact in request.artifacts if artifact.artifact_type == artifact_type
    )


def _completed_real_result(
    *,
    analyzer_id: str,
    analyzer_version: str,
    group: str,
    request: AnalyzerRequest,
    summary: str,
    raw_metrics: Mapping[str, JsonValue],
    candidates: tuple[_TypedCandidate, ...] = (),
) -> AnalyzerResult:
    if len(candidates) > _MAX_REAL_ANALYZER_CANDIDATES:
        raise ValueError("real analyzer candidate limit exceeded")
    return AnalyzerResult(
        analyzer_id=analyzer_id,
        analyzer_version=analyzer_version,
        media_type=request.media_type,
        group=group,
        status=AnalyzerStatus.COMPLETED,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=0,
        score=None,
        score_name=None,
        summary=summary,
        raw_metrics=cast(dict[str, JsonValue], dict(raw_metrics)),
        candidate_findings=[_candidate_transport(candidate) for candidate in candidates],
        warnings=[],
        errors=[],
    )
