"""Deterministic Stage 6 candidate validation and Finding formation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import groupby
from typing import cast

from pydantic import JsonValue, ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.analyzers._audio_pcm import AudioPcmQualityAnalyzer
from fakedetector.analyzers._candidates import (
    _canonical_candidate,
    _TypedCandidate,
    _validate_candidate_transport,
)
from fakedetector.analyzers._image_copy_move import ImageCopyMoveCorrespondenceAnalyzer
from fakedetector.analyzers._image_metadata import ImageMetadataConsistencyAnalyzer
from fakedetector.analyzers._real_common import _MAX_REAL_ANALYZER_CANDIDATES
from fakedetector.analyzers._video_frames import VideoSampledFrameQualityAnalyzer
from fakedetector.domain import (
    AnalyzerResult,
    AnalyzerStatus,
    Finding,
    FindingSeverity,
    MediaType,
)

_DESCRIPTION_BY_TYPE = {
    "image_metadata_dimension_mismatch": (
        "Embedded coded image dimensions differ from decoded source raster dimensions."
    ),
    "audio_full_scale_saturation": (
        "The fragment contains full-scale PCM samples at the deterministic v1 threshold."
    ),
    "video_sample_resolution_change": (
        "The prepared video sample sequence contains differing decoded frame dimensions."
    ),
    "repeated_sampled_video_frames": (
        "At least three consecutive prepared video samples have identical decoded pixels."
    ),
    "repeated_image_region_correspondence": (
        "This image region participates in a geometrically consistent repeated-region "
        "correspondence."
    ),
}


@dataclass(frozen=True, slots=True)
class _RealResultSpec:
    version: str
    media_type: MediaType
    group: str
    candidate_types: frozenset[str]
    max_candidates: int = _MAX_REAL_ANALYZER_CANDIDATES


_REAL_RESULT_SPECS = {
    ImageCopyMoveCorrespondenceAnalyzer.analyzer_id: _RealResultSpec(
        version=ImageCopyMoveCorrespondenceAnalyzer.analyzer_version,
        media_type=next(iter(ImageCopyMoveCorrespondenceAnalyzer.supported_media_types)),
        group=ImageCopyMoveCorrespondenceAnalyzer.group,
        candidate_types=frozenset({"repeated_image_region_correspondence"}),
        max_candidates=8,
    ),
    ImageMetadataConsistencyAnalyzer.analyzer_id: _RealResultSpec(
        version=ImageMetadataConsistencyAnalyzer.analyzer_version,
        media_type=next(iter(ImageMetadataConsistencyAnalyzer.supported_media_types)),
        group=ImageMetadataConsistencyAnalyzer.group,
        candidate_types=frozenset({"image_metadata_dimension_mismatch"}),
    ),
    AudioPcmQualityAnalyzer.analyzer_id: _RealResultSpec(
        version=AudioPcmQualityAnalyzer.analyzer_version,
        media_type=next(iter(AudioPcmQualityAnalyzer.supported_media_types)),
        group=AudioPcmQualityAnalyzer.group,
        candidate_types=frozenset({"audio_full_scale_saturation"}),
    ),
    VideoSampledFrameQualityAnalyzer.analyzer_id: _RealResultSpec(
        version=VideoSampledFrameQualityAnalyzer.analyzer_version,
        media_type=next(iter(VideoSampledFrameQualityAnalyzer.supported_media_types)),
        group=VideoSampledFrameQualityAnalyzer.group,
        candidate_types=frozenset(
            {"video_sample_resolution_change", "repeated_sampled_video_frames"}
        ),
    ),
}


class Stage6FindingFormationError(RuntimeError):
    """Safe internal failure without candidate payload or traceback details."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Stage 6 finding formation failed.")


@dataclass(frozen=True, slots=True)
class _NormalizedCandidate:
    result: AnalyzerResult
    candidate: _TypedCandidate
    base_identity: bytes
    full_candidate: bytes


class Stage6FindingService:
    """Convert authoritative real AnalyzerResult values into canonical findings."""

    def form_findings(self, results: Sequence[AnalyzerResult]) -> tuple[Finding, ...]:
        normalized: list[_NormalizedCandidate] = []
        try:
            for result_value in results:
                result = _validated_result(result_value)
                spec = _REAL_RESULT_SPECS.get(result.analyzer_id)
                if spec is None:
                    continue
                if result.status is not AnalyzerStatus.COMPLETED or not result.applicable:
                    continue
                _validate_real_result_identity(result, spec)
                if len(result.candidate_findings) > spec.max_candidates:
                    raise ValueError("candidate limit")
                validated_candidates: list[_TypedCandidate] = []
                for transport_candidate in result.candidate_findings:
                    candidate = _validate_candidate_transport(transport_candidate)
                    if candidate.type not in spec.candidate_types:
                        raise ValueError("candidate analyzer mismatch")
                    validated_candidates.append(candidate)
                if result.analyzer_id == ImageCopyMoveCorrespondenceAnalyzer.analyzer_id:
                    _validate_copy_move_candidate_pairs(validated_candidates)
                for candidate in validated_candidates:
                    normalized.append(
                        _NormalizedCandidate(
                            result=result,
                            candidate=candidate,
                            base_identity=_canonical_identity(result, candidate),
                            full_candidate=_canonical_candidate(candidate),
                        )
                    )
        except (
            AttributeError,
            PydanticSerializationError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise Stage6FindingFormationError("candidate_validation") from None

        normalized.sort(key=lambda item: (item.base_identity, item.full_candidate))
        findings: list[Finding] = []
        for _, duplicates in groupby(normalized, key=lambda item: item.base_identity):
            for duplicate_ordinal, item in enumerate(duplicates, start=1):
                findings.append(_finding(item, duplicate_ordinal))
        return tuple(sorted(findings, key=lambda finding: finding.finding_id))


def _validated_result(result: AnalyzerResult) -> AnalyzerResult:
    if not isinstance(result, AnalyzerResult):
        raise TypeError("AnalyzerResult is required")
    return AnalyzerResult.model_validate(result.model_dump(mode="python", warnings="error"))


def _validate_real_result_identity(result: AnalyzerResult, spec: _RealResultSpec) -> None:
    if (
        result.analyzer_version != spec.version
        or result.media_type is not spec.media_type
        or result.group != spec.group
        or result.score is not None
        or result.score_name is not None
    ):
        raise ValueError("real analyzer result identity")


def _validate_copy_move_candidate_pairs(candidates: Sequence[_TypedCandidate]) -> None:
    candidates_by_group: dict[str, list[_TypedCandidate]] = {}
    for candidate in candidates:
        candidates_by_group.setdefault(candidate.correlation_group, []).append(candidate)
    for grouped_candidates in candidates_by_group.values():
        if len(grouped_candidates) != 2:
            raise ValueError("copy-move candidate group size")
        first, second = grouped_candidates
        if first.localization == second.localization:
            raise ValueError("copy-move candidate localizations")


def _base_identity_projection(
    result: AnalyzerResult,
    candidate: _TypedCandidate,
) -> dict[str, JsonValue]:
    return {
        "source_analyzer_id": result.analyzer_id,
        "source_analyzer_version": result.analyzer_version,
        "group": result.group,
        "type": candidate.type,
        "localization": cast(
            dict[str, JsonValue],
            candidate.localization.model_dump(mode="json", warnings="error"),
        ),
        "correlation_group": candidate.correlation_group,
    }


def _canonical_identity(result: AnalyzerResult, candidate: _TypedCandidate) -> bytes:
    return _canonical_json(_base_identity_projection(result, candidate))


def _finding(item: _NormalizedCandidate, duplicate_ordinal: int) -> Finding:
    identity = _base_identity_projection(item.result, item.candidate)
    identity["duplicate_ordinal"] = duplicate_ordinal
    finding_id = "finding_" + hashlib.sha256(_canonical_json(identity)).hexdigest()
    return Finding(
        finding_id=finding_id,
        group=item.result.group,
        type=item.candidate.type,
        severity=FindingSeverity.WEAK,
        source_analyzer_id=item.result.analyzer_id,
        source_analyzer_version=item.result.analyzer_version,
        description=_DESCRIPTION_BY_TYPE[item.candidate.type],
        localization=item.candidate.localization.model_copy(deep=True),
        source_score=None,
        score_impact=None,
        critical_override_eligible=False,
        correlation_group=item.candidate.correlation_group,
        evidence_refs=list(item.candidate.evidence_refs),
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
