"""Private typed candidate-finding transport boundary for real analyzers."""

from __future__ import annotations

import json
from typing import Annotated, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator

from fakedetector.domain import FileLocalization, TimeIntervalLocalization

_MAX_EVIDENCE_REFS = 4
_MAX_EVIDENCE_REF_CHARS = 128


class _CandidateBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_refs: tuple[str, ...] = Field(max_length=_MAX_EVIDENCE_REFS)

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > _MAX_EVIDENCE_REF_CHARS for item in value):
            raise ValueError("candidate evidence reference is invalid")
        return value


class _ImageMetadataDimensionMismatchCandidate(_CandidateBase):
    type: Literal["image_metadata_dimension_mismatch"]
    localization: FileLocalization
    correlation_group: Literal["image_metadata_consistency"]


class _AudioFullScaleSaturationCandidate(_CandidateBase):
    type: Literal["audio_full_scale_saturation"]
    localization: TimeIntervalLocalization
    correlation_group: Literal["audio_signal_quality"]


class _VideoSampleResolutionChangeCandidate(_CandidateBase):
    type: Literal["video_sample_resolution_change"]
    localization: TimeIntervalLocalization
    correlation_group: Literal["video_stream_consistency"]


class _RepeatedSampledVideoFramesCandidate(_CandidateBase):
    type: Literal["repeated_sampled_video_frames"]
    localization: TimeIntervalLocalization
    correlation_group: Literal["video_temporal_repetition"]


type _TypedCandidate = Annotated[
    _ImageMetadataDimensionMismatchCandidate
    | _AudioFullScaleSaturationCandidate
    | _VideoSampleResolutionChangeCandidate
    | _RepeatedSampledVideoFramesCandidate,
    Field(discriminator="type"),
]

_CANDIDATE_ADAPTER: TypeAdapter[_TypedCandidate] = TypeAdapter(_TypedCandidate)


def _candidate_transport(candidate: _TypedCandidate) -> dict[str, JsonValue]:
    """Return the bounded JSON-safe representation placed in AnalyzerResult."""
    return cast(
        dict[str, JsonValue],
        candidate.model_dump(mode="json", warnings="error"),
    )


def _validate_candidate_transport(candidate: object) -> _TypedCandidate:
    """Revalidate one untrusted transport value at the Stage 6 boundary."""
    return _CANDIDATE_ADAPTER.validate_python(candidate)


def _canonical_candidate(candidate: _TypedCandidate) -> bytes:
    """Canonical complete private representation used only for stable sorting."""
    return json.dumps(
        candidate.model_dump(mode="json", warnings="error"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
