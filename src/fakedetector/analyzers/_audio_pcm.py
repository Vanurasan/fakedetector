"""Streaming factual quality metrics for canonical signed-16 PCM audio."""

from __future__ import annotations

import math
import sys
import wave
from array import array
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from fakedetector.analyzers._candidates import _AudioFullScaleSaturationCandidate
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
    AudioTechnicalParameters,
    MediaType,
    TimeIntervalLocalization,
)

_PCM_SCALE = 32768.0
_PCM_MIN = -32768
_PCM_MAX = 32767
_READ_FRAMES = 4096


class AudioPcmQualitySettings(BaseModel):
    """Versioned deterministic threshold for the v1 saturation observation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    full_scale_sample_ratio_threshold: float = Field(default=0.001, gt=0, le=1)


@dataclass(frozen=True, slots=True)
class _PcmStats:
    sample_rate_hz: int
    channels: int
    sample_count: int
    peak_abs_normalized: float
    rms_normalized: float
    dc_offset_abs_normalized: float
    digital_silence_ratio: float
    full_scale_sample_ratio: float


@dataclass(frozen=True, slots=True)
class _SaturatedFragment:
    artifact: AnalyzerArtifactInput
    full_scale_sample_ratio: float


class AudioPcmQualityAnalyzer:
    analyzer_id: ClassVar[str] = "audio_pcm_quality"
    analyzer_name: ClassVar[str] = "Audio PCM quality"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "signal_quality"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.AUDIO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        if request.media_type is not MediaType.AUDIO or not isinstance(
            request.file_facts.technical_parameters, AudioTechnicalParameters
        ):
            return ApplicabilityResult(False, "media_type")
        normalized = _artifacts(request, "normalized_audio")
        if len(normalized) != 1 or normalized[0].format.casefold() != "wav":
            return ApplicabilityResult(False, "normalized_audio_missing")
        return ApplicabilityResult(True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        settings = request.settings
        if not isinstance(settings, AudioPcmQualitySettings):
            raise TypeError("unexpected settings contract")
        normalized_artifacts = _artifacts(request, "normalized_audio")
        if len(normalized_artifacts) != 1:
            raise ValueError("one normalized audio artifact is required")
        normalized = _read_pcm_stats(normalized_artifacts[0])

        saturated: list[_SaturatedFragment] = []
        for artifact in _artifacts(request, "audio_fragment"):
            if artifact.start_time_seconds is None or artifact.end_time_seconds is None:
                raise ValueError("audio fragment timing is required")
            stats = _read_pcm_stats(artifact)
            if (
                stats.sample_rate_hz != normalized.sample_rate_hz
                or stats.channels != normalized.channels
            ):
                raise ValueError("audio fragment PCM parameters are inconsistent")
            if stats.full_scale_sample_ratio >= settings.full_scale_sample_ratio_threshold:
                saturated.append(_SaturatedFragment(artifact, stats.full_scale_sample_ratio))

        selected = sorted(
            saturated,
            key=lambda item: (
                -item.full_scale_sample_ratio,
                item.artifact.start_time_seconds,
                item.artifact.end_time_seconds,
                item.artifact.artifact_id,
            ),
        )[:_MAX_REAL_ANALYZER_CANDIDATES]
        candidates = tuple(
            _AudioFullScaleSaturationCandidate(
                type="audio_full_scale_saturation",
                localization=TimeIntervalLocalization(
                    type="time_interval",
                    start_seconds=_required_time(item.artifact.start_time_seconds),
                    end_seconds=_required_time(item.artifact.end_time_seconds),
                ),
                correlation_group="audio_signal_quality",
                evidence_refs=(item.artifact.artifact_id,),
            )
            for item in selected
        )

        decoded_duration_seconds = (
            normalized.sample_count / normalized.channels / normalized.sample_rate_hz
        )
        return _completed_real_result(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            group=self.group,
            request=request,
            summary="Canonical PCM audio was measured with deterministic sample-level metrics.",
            raw_metrics={
                "sample_rate_hz": normalized.sample_rate_hz,
                "channels": normalized.channels,
                "sample_count": normalized.sample_count,
                "decoded_duration_seconds": decoded_duration_seconds,
                "peak_abs_normalized": normalized.peak_abs_normalized,
                "rms_normalized": normalized.rms_normalized,
                "dc_offset_abs_normalized": normalized.dc_offset_abs_normalized,
                "digital_silence_ratio": normalized.digital_silence_ratio,
                "full_scale_sample_ratio": normalized.full_scale_sample_ratio,
                "saturated_fragment_count": len(saturated),
            },
            candidates=candidates,
        )


def _read_pcm_stats(artifact: AnalyzerArtifactInput) -> _PcmStats:
    sample_count = 0
    sum_samples = 0
    sum_squares = 0
    peak_abs = 0
    silent_samples = 0
    full_scale_samples = 0

    with artifact.content.open_for_read() as stream, wave.open(stream, "rb") as source:
        if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
            raise ValueError("audio artifact must be uncompressed signed-16 PCM")
        sample_rate_hz = source.getframerate()
        channels = source.getnchannels()
        if sample_rate_hz <= 0 or channels <= 0:
            raise ValueError("audio artifact parameters are invalid")
        while payload := source.readframes(_READ_FRAMES):
            if len(payload) % 2:
                raise ValueError("PCM payload has an incomplete sample")
            samples = array("h")
            samples.frombytes(payload)
            if sys.byteorder != "little":
                samples.byteswap()
            for sample in samples:
                magnitude = abs(sample)
                sample_count += 1
                sum_samples += sample
                sum_squares += sample * sample
                peak_abs = max(peak_abs, magnitude)
                silent_samples += int(sample == 0)
                full_scale_samples += int(sample in {_PCM_MIN, _PCM_MAX})

    if sample_count == 0:
        raise ValueError("PCM artifact contains no samples")
    return _PcmStats(
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        sample_count=sample_count,
        peak_abs_normalized=peak_abs / _PCM_SCALE,
        rms_normalized=math.sqrt(sum_squares / sample_count) / _PCM_SCALE,
        dc_offset_abs_normalized=abs(sum_samples / sample_count) / _PCM_SCALE,
        digital_silence_ratio=silent_samples / sample_count,
        full_scale_sample_ratio=full_scale_samples / sample_count,
    )


def _required_time(value: float | None) -> float:
    if value is None:
        raise ValueError("artifact time is required")
    return value
