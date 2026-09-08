"""Bounded quality observations over existing Stage 5 sampled video frames."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from PIL import Image
from pydantic import BaseModel, ConfigDict

from fakedetector.analyzers._candidates import (
    _RepeatedSampledVideoFramesCandidate,
    _TypedCandidate,
    _VideoSampleResolutionChangeCandidate,
)
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    ApplicabilityResult,
)
from fakedetector.analyzers._real_common import (
    _MAX_REAL_ANALYZER_CANDIDATES,
    _artifacts,
    _completed_real_result,
)
from fakedetector.domain import (
    AnalyzerResult,
    MediaType,
    TimeIntervalLocalization,
    VideoTechnicalParameters,
)


class VideoSampledFrameQualitySettings(BaseModel):
    """No configurable policy is needed for exact v1 comparisons."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class _DecodedFrame:
    width: int
    height: int
    mode: str
    pixels: bytes


@dataclass(frozen=True, slots=True)
class _DuplicateRun:
    start_index: int
    end_index: int

    @property
    def sample_count(self) -> int:
        return self.end_index - self.start_index + 1


class VideoSampledFrameQualityAnalyzer:
    analyzer_id: ClassVar[str] = "video_sampled_frame_quality"
    analyzer_name: ClassVar[str] = "Video sampled-frame quality"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "sampled_frame_quality"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.VIDEO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        if request.media_type is not MediaType.VIDEO or not isinstance(
            request.file_facts.technical_parameters, VideoTechnicalParameters
        ):
            return ApplicabilityResult(False, "media_type")
        if not _artifacts(request, "sampled_frame"):
            return ApplicabilityResult(False, "sampled_frames_missing")
        return ApplicabilityResult(True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        if not isinstance(request.settings, VideoSampledFrameQualitySettings):
            raise TypeError("unexpected settings contract")
        frames = tuple(sorted(_artifacts(request, "sampled_frame"), key=_frame_order))
        if not frames:
            raise ValueError("at least one sampled frame is required")
        if any(frame.start_time_seconds is None or frame.frame_index is None for frame in frames):
            raise ValueError("sampled frame timing and index are required")

        dimension_first_evidence: dict[tuple[int, int], str] = {}
        duplicate_runs: list[_DuplicateRun] = []
        exact_duplicate_pair_count = 0
        current_run_start = 0
        previous: _DecodedFrame | None = None

        for index, artifact in enumerate(frames):
            decoded = _decode_frame(artifact)
            dimension_first_evidence.setdefault(
                (decoded.width, decoded.height), artifact.artifact_id
            )
            if previous is not None and decoded == previous:
                exact_duplicate_pair_count += 1
            else:
                if index - current_run_start >= 2:
                    duplicate_runs.append(_DuplicateRun(current_run_start, index - 1))
                current_run_start = index
            previous = decoded
        if len(frames) - current_run_start >= 2:
            duplicate_runs.append(_DuplicateRun(current_run_start, len(frames) - 1))

        longest_run = max(
            duplicate_runs,
            key=lambda run: (
                run.sample_count,
                _run_span(run, frames),
                -_frame_time(frames[run.start_index]),
            ),
            default=None,
        )
        longest_run_samples = longest_run.sample_count if longest_run is not None else 1
        longest_run_span = _run_span(longest_run, frames) if longest_run is not None else 0.0

        candidates: list[_TypedCandidate] = []
        if len(dimension_first_evidence) > 1:
            candidates.append(
                _VideoSampleResolutionChangeCandidate(
                    type="video_sample_resolution_change",
                    localization=_sample_interval(frames),
                    correlation_group="video_stream_consistency",
                    evidence_refs=tuple(list(dimension_first_evidence.values())[:2]),
                )
            )

        repeated_runs = [run for run in duplicate_runs if run.sample_count >= 3]
        remaining = _MAX_REAL_ANALYZER_CANDIDATES - len(candidates)
        selected_runs = sorted(
            repeated_runs,
            key=lambda run: (
                -run.sample_count,
                -_run_span(run, frames),
                _frame_time(frames[run.start_index]),
                frames[run.start_index].artifact_id,
            ),
        )[:remaining]
        for run in sorted(selected_runs, key=lambda item: (item.start_index, item.end_index)):
            candidates.append(
                _RepeatedSampledVideoFramesCandidate(
                    type="repeated_sampled_video_frames",
                    localization=TimeIntervalLocalization(
                        type="time_interval",
                        start_seconds=_frame_time(frames[run.start_index]),
                        end_seconds=_frame_time(frames[run.end_index]),
                    ),
                    correlation_group="video_temporal_repetition",
                    evidence_refs=(
                        frames[run.start_index].artifact_id,
                        frames[run.end_index].artifact_id,
                    ),
                )
            )

        return _completed_real_result(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            group=self.group,
            request=request,
            summary="Existing sampled frames were compared using exact decoded pixel equality.",
            raw_metrics={
                "sampled_frame_count": len(frames),
                "compared_adjacent_pair_count": max(0, len(frames) - 1),
                "dimension_variant_count": len(dimension_first_evidence),
                "exact_duplicate_pair_count": exact_duplicate_pair_count,
                "longest_exact_duplicate_run_samples": longest_run_samples,
                "longest_exact_duplicate_span_seconds": longest_run_span,
                "first_target_timestamp_seconds": _frame_time(frames[0]),
                "last_target_timestamp_seconds": _frame_time(frames[-1]),
                "sampling_interval_seconds": _sampling_interval(request.metadata),
            },
            candidates=tuple(candidates),
        )


def _frame_order(artifact: AnalyzerArtifactInput) -> tuple[int, float, str]:
    frame_index = artifact.frame_index
    timestamp = artifact.start_time_seconds
    return (
        frame_index if frame_index is not None else 2**31,
        timestamp if timestamp is not None else math.inf,
        artifact.artifact_id,
    )


def _decode_frame(artifact: AnalyzerArtifactInput) -> _DecodedFrame:
    with artifact.content.open_for_read() as stream, Image.open(stream) as image:
        image.load()
        return _DecodedFrame(
            width=image.width,
            height=image.height,
            mode=image.mode,
            pixels=image.tobytes(),
        )


def _frame_time(artifact: AnalyzerArtifactInput) -> float:
    value = artifact.start_time_seconds
    if value is None:
        raise ValueError("sampled frame target timestamp is required")
    return value


def _run_span(
    run: _DuplicateRun,
    frames: tuple[AnalyzerArtifactInput, ...],
) -> float:
    return _frame_time(frames[run.end_index]) - _frame_time(frames[run.start_index])


def _sample_interval(
    frames: tuple[AnalyzerArtifactInput, ...],
) -> TimeIntervalLocalization:
    return TimeIntervalLocalization(
        type="time_interval",
        start_seconds=_frame_time(frames[0]),
        end_seconds=_frame_time(frames[-1]),
    )


def _sampling_interval(metadata: Mapping[str, object]) -> float | None:
    value = metadata.get("sampling_interval_seconds")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    ):
        return float(value)
    return None
