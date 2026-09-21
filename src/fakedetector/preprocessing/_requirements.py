"""Demand declarations shared by analyzer planning and preprocessing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fakedetector._generated_artifact_budget import (
    _MAX_GENERATED_ARTIFACTS,
    _GeneratedArtifactBudget,
    _GeneratedArtifactLimitError,
)
from fakedetector.domain import MediaType


class ForensicCapability(StrEnum):
    ORIGINAL_IMAGE = "original_image"
    JPEG_STRUCTURE = "jpeg_structure"
    JPEG_COEFFICIENTS = "jpeg_coefficients"
    IMAGE_COORDINATES = "image_coordinates"
    RESIDUAL_RASTER = "residual_raster"
    AUDIO_PRECISION = "audio_precision"
    AUDIO_SAMPLES = "audio_samples"
    AUDIO_SPECTRAL = "audio_spectral"
    STREAM_TIMING = "stream_timing"
    TIMING_RECORDS = "timing_records"
    DENSE_VIDEO = "dense_video"
    AV_TIMELINE = "av_timeline"


_IMAGE_CAPABILITIES = frozenset(
    {
        ForensicCapability.ORIGINAL_IMAGE,
        ForensicCapability.JPEG_STRUCTURE,
        ForensicCapability.JPEG_COEFFICIENTS,
        ForensicCapability.IMAGE_COORDINATES,
        ForensicCapability.RESIDUAL_RASTER,
    }
)
_AUDIO_CAPABILITIES = frozenset(
    {
        ForensicCapability.AUDIO_PRECISION,
        ForensicCapability.AUDIO_SAMPLES,
        ForensicCapability.AUDIO_SPECTRAL,
        ForensicCapability.STREAM_TIMING,
        ForensicCapability.TIMING_RECORDS,
    }
)
_VIDEO_CAPABILITIES = _AUDIO_CAPABILITIES | frozenset(
    {
        ForensicCapability.DENSE_VIDEO,
        ForensicCapability.AV_TIMELINE,
    }
)
_DEPENDENCIES = {
    ForensicCapability.JPEG_STRUCTURE: (ForensicCapability.ORIGINAL_IMAGE,),
    ForensicCapability.JPEG_COEFFICIENTS: (
        ForensicCapability.JPEG_STRUCTURE,
        ForensicCapability.IMAGE_COORDINATES,
    ),
    ForensicCapability.IMAGE_COORDINATES: (ForensicCapability.ORIGINAL_IMAGE,),
    ForensicCapability.RESIDUAL_RASTER: (ForensicCapability.IMAGE_COORDINATES,),
    ForensicCapability.AUDIO_SAMPLES: (ForensicCapability.AUDIO_PRECISION,),
    ForensicCapability.AUDIO_SPECTRAL: (ForensicCapability.AUDIO_SAMPLES,),
    ForensicCapability.TIMING_RECORDS: (ForensicCapability.STREAM_TIMING,),
    ForensicCapability.DENSE_VIDEO: (ForensicCapability.STREAM_TIMING,),
    ForensicCapability.AV_TIMELINE: (ForensicCapability.TIMING_RECORDS,),
}


@dataclass(frozen=True, slots=True)
class PreprocessingRequirements:
    """Representations required by the active analyzer plan."""

    audio_spectrogram: bool = False
    video_audio_track: bool = False
    forensic: frozenset[ForensicCapability] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.audio_spectrogram, bool) or not isinstance(
            self.video_audio_track, bool
        ):
            raise TypeError("preprocessing requirements must be booleans")
        if not isinstance(self.forensic, frozenset) or any(
            not isinstance(item, ForensicCapability) for item in self.forensic
        ):
            raise TypeError("forensic requirements must be a frozenset of capabilities")
        expanded = set(self.forensic)
        pending = list(expanded)
        while pending:
            for dependency in _DEPENDENCIES.get(pending.pop(), ()):
                if dependency not in expanded:
                    expanded.add(dependency)
                    pending.append(dependency)
        object.__setattr__(self, "forensic", frozenset(expanded))

    def validate_media(self, media_type: MediaType) -> None:
        """Check forensic applicability; legacy switches keep their existing semantics."""
        allowed = {
            MediaType.IMAGE: _IMAGE_CAPABILITIES,
            MediaType.AUDIO: _AUDIO_CAPABILITIES,
            MediaType.VIDEO: _VIDEO_CAPABILITIES,
        }[media_type]
        if not self.forensic <= allowed:
            raise ValueError("forensic demand does not match media route")

    @classmethod
    def aggregate(cls, requirements: Iterable[PreprocessingRequirements]) -> Self:
        declarations = tuple(requirements)
        return cls(
            audio_spectrogram=any(item.audio_spectrogram for item in declarations),
            video_audio_track=any(item.video_audio_track for item in declarations),
            forensic=frozenset(cap for item in declarations for cap in item.forensic),
        )


class _BoundedValue(BaseModel):
    """Closed immutable internal facts, using the existing Pydantic boundary stack."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


_MAX_INDEX = (1 << 63) - 1
_MAX_FORENSIC_MANIFEST_BYTES = 16_384
_MAX_FORENSIC_REPRESENTATIONS = 16
_MAX_NUMERIC_BYTES = 64 * 1_048_576
_PositiveIndex = Annotated[int, Field(gt=0, le=_MAX_INDEX)]
_NonnegativeIndex = Annotated[int, Field(ge=0, le=_MAX_INDEX)]


def _checked_product(*values: int, limit: int = _MAX_INDEX) -> int:
    """Reject invalid dimensions and overflow before native-size arithmetic/allocation."""
    result = 1
    for value in values:
        if type(value) is not int or value <= 0 or value > limit // result:
            raise ValueError("size product exceeds its bound")
        result *= value
    return result


class ForensicResourcePolicy(_BoundedValue):
    """Internal hard ceilings, not a sampling schedule or a new config schema.

    Counts are integers; suffixes identify bytes, pixels, samples, ticks or seconds.
    A caller may tighten ceilings, never exceed the initial safety envelope.
    """

    jpeg_input_bytes: int = Field(default=32 << 20, gt=0, le=32 << 20)
    jpeg_markers: int = Field(default=256, gt=0, le=256)
    jpeg_marker_bytes: int = Field(default=1 << 20, gt=0, le=1 << 20)
    jpeg_coefficients: int = Field(default=1 << 22, ge=64, le=1 << 22)
    raster_pixels: int = Field(default=1 << 22, gt=0, le=1 << 22)
    tile_side: int = Field(default=512, gt=0, le=512)
    tile_count: int = Field(default=16, gt=0, le=16)
    tile_halo: int = Field(default=2, ge=0, le=2)
    residual_workspace_bytes: int = Field(default=32 << 20, gt=0, le=32 << 20)
    audio_windows: int = Field(default=3, gt=0, le=3)
    audio_window_seconds: int = Field(default=10, gt=0, le=10)
    audio_window_samples: int = Field(default=1 << 20, gt=0, le=1 << 20)
    audio_rate: int = Field(default=192_000, gt=0, le=192_000)
    audio_channels: int = Field(default=8, gt=0, le=8)
    fft_size: int = Field(default=4096, ge=4, le=4096)
    spectral_frames: int = Field(default=8192, gt=0, le=8192)
    spectral_batch: int = Field(default=32, gt=0, le=32)
    timing_regions: int = Field(default=3, gt=0, le=3)
    timing_streams: int = Field(default=2, gt=0, le=2)
    timing_packets: int = Field(default=256, gt=0, le=256)
    timing_frames: int = Field(default=512, gt=0, le=512)
    timing_records: int = Field(default=4608, gt=0, le=4608)
    timing_probe_bytes: int = Field(default=256 << 10, gt=0, le=256 << 10)
    timing_artifact_bytes: int = Field(default=1 << 20, gt=0, le=1 << 20)
    dense_windows: int = Field(default=3, gt=0, le=3)
    dense_frames: int = Field(default=32, gt=0, le=32)
    dense_window_seconds: int = Field(default=2, gt=0, le=2)
    dense_width: int = Field(default=640, gt=0, le=640)
    dense_height: int = Field(default=360, gt=0, le=360)
    native_video_width: int = Field(default=3840, gt=0, le=3840)
    native_video_height: int = Field(default=2160, gt=0, le=2160)

    @model_validator(mode="after")
    def coherent_limits(self) -> Self:
        if (
            self.jpeg_marker_bytes > self.jpeg_input_bytes
            or self.tile_side**2 > self.raster_pixels
            or self.audio_channels > self.audio_window_samples
            or self.spectral_batch > self.spectral_frames
            or self.timing_records
            > self.timing_regions * self.timing_streams * (self.timing_packets + self.timing_frames)
            or self.timing_probe_bytes > self.timing_artifact_bytes
            or self.dense_width > self.native_video_width
            or self.dense_height > self.native_video_height
        ):
            raise ValueError("incoherent forensic resource limits")
        _checked_product(
            self.dense_windows,
            self.dense_frames,
            self.dense_width,
            self.dense_height,
            3,
            limit=_MAX_NUMERIC_BYTES,
        )
        return self

    def check_artifacts(
        self,
        budget: _GeneratedArtifactBudget,
        *,
        total_count: int,
        additional_bytes: int,
    ) -> None:
        """Compose with the task budget; count includes existing and planned files.

        This is preflight, not a reservation. Every write still uses open_output.
        """
        if type(total_count) is not int or not 0 <= total_count <= _MAX_GENERATED_ARTIFACTS:
            raise _GeneratedArtifactLimitError
        budget.ensure_feasible(additional_bytes)

    def check_raster(self, width: int, height: int, *, tiles: int = 1) -> None:
        _checked_product(width, height, limit=self.raster_pixels)
        _checked_product(tiles, limit=self.tile_count)

    def check_tile(self, width: int, height: int, halo: int, workspace_bytes: int) -> None:
        _checked_product(width, limit=self.tile_side)
        _checked_product(height, limit=self.tile_side)
        if type(halo) is not int or not 0 <= halo <= self.tile_halo:
            raise ValueError("tile halo exceeds policy")
        _checked_product(workspace_bytes, limit=self.residual_workspace_bytes)

    def check_audio(self, frames: int, channels: int, rate: int, *, windows: int = 1) -> None:
        _checked_product(windows, limit=self.audio_windows)
        _checked_product(channels, limit=self.audio_channels)
        _checked_product(rate, limit=self.audio_rate)
        _checked_product(frames, channels, limit=self.audio_window_samples)
        if frames > rate * self.audio_window_seconds:
            raise ValueError("audio window duration exceeds policy")

    def check_spectral(self, n_fft: int, hop: int, frames: int, batch: int) -> None:
        _checked_product(n_fft, limit=self.fft_size)
        _checked_product(hop, limit=n_fft)
        _checked_product(frames, limit=self.spectral_frames)
        _checked_product(batch, limit=min(frames, self.spectral_batch))
        if n_fft < 4 or hop * 4 < n_fft:
            raise ValueError("spectral hop is below the bounded work profile")


_FORENSIC_POLICY = ForensicResourcePolicy()
