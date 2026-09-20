"""Bounded media tools, image kernels, and JPEG preflight for trusted preprocessing."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import mmap
import os
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import BinaryIO, Literal, cast

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

from fakedetector._generated_artifact_budget import (
    _GeneratedArtifactBudget,
    _GeneratedArtifactLimitError,
    _GeneratedArtifactWriteError,
)
from fakedetector.core._bounded_process import (
    ProcessInfrastructureError,
    ProcessOutputLimitError,
    ProcessResult,
    ProcessTimeoutError,
    run_bounded_process,
)
from fakedetector.preprocessing._errors import PreprocessingError
from fakedetector.preprocessing._models import (
    AudioPrecisionFacts,
    IndexRange,
    JpegComponent,
    JpegHeader,
    JpegQuantizationTable,
)
from fakedetector.preprocessing._requirements import (
    _FORENSIC_POLICY,
    ForensicResourcePolicy,
)

_MAX_FLAC_PROGRESS_BYTES = 16 * 1024
_RIFF_UINT32_MAX = (1 << 32) - 1
_FLAC_TOTAL_SAMPLES_MASK = (1 << 36) - 1
_UINT8 = np.dtype("|u1")
_FLOAT64 = np.dtype("<f8")
_LUMINANCE_WEIGHTS = (0.299, 0.587, 0.114)
_SMOOTHING_VECTORS = {
    3: (0.25, 0.5, 0.25),
    5: (0.0625, 0.25, 0.375, 0.25, 0.0625),
}


@dataclass(frozen=True, slots=True)
class TileRegion:
    """Zero-based half-open core coverage in oriented raster coordinates."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if (
            type(self.x) is not int
            or type(self.y) is not int
            or type(self.width) is not int
            or type(self.height) is not int
            or self.x < 0
            or self.y < 0
            or self.width <= 0
            or self.height <= 0
        ):
            raise ValueError("tile region must contain nonnegative coordinates and positive size")


@dataclass(frozen=True, slots=True)
class ImageTile:
    """Immutable uint8 core plus a complete REFLECT_101 halo."""

    pixels: NDArray[np.uint8]
    region: TileRegion
    halo: int

    def __post_init__(self) -> None:
        _validate_halo(self.halo)
        expected = (self.region.height + 2 * self.halo, self.region.width + 2 * self.halo)
        if (
            not isinstance(self.pixels, np.ndarray)
            or self.pixels.dtype != _UINT8
            or self.pixels.ndim not in (2, 3)
            or self.pixels.shape[:2] != expected
            or self.pixels.ndim == 3
            and self.pixels.shape[2] not in (1, 3, 4)
            or not self.pixels.flags.c_contiguous
            or not _has_immutable_backing(self.pixels)
        ):
            raise ValueError("image tile does not satisfy the immutable uint8 layout")


@dataclass(frozen=True, slots=True)
class LuminanceTile:
    """Immutable float64 luminance window retaining the source tile halo."""

    values: NDArray[np.float64]
    region: TileRegion
    halo: int

    def __post_init__(self) -> None:
        _validate_halo(self.halo)
        expected = (self.region.height + 2 * self.halo, self.region.width + 2 * self.halo)
        _validate_float_plane(self.values, expected)
        if np.any(self.values < 0.0) or np.any(self.values > 255.0):
            raise ValueError("luminance values must be in the closed range [0, 255]")


@dataclass(frozen=True, slots=True)
class KernelPlane:
    """Immutable float64 observation covering exactly one tile core."""

    values: NDArray[np.float64]
    coverage: TileRegion
    halo_used: int

    def __post_init__(self) -> None:
        _validate_halo(self.halo_used)
        _validate_float_plane(self.values, (self.coverage.height, self.coverage.width))


@dataclass(frozen=True, slots=True)
class GradientPlanes:
    """Horizontal and vertical centered finite differences for equal coverage."""

    horizontal: KernelPlane
    vertical: KernelPlane

    def __post_init__(self) -> None:
        if (
            self.horizontal.coverage != self.vertical.coverage
            or self.horizontal.halo_used != 1
            or self.vertical.halo_used != 1
        ):
            raise ValueError("gradient planes must have equal coverage and one-pixel halo")


@dataclass(frozen=True, slots=True)
class RobustLocalStatistics:
    """Distribution observations without forensic labels or thresholds."""

    sample_count: int
    median: float
    median_absolute_deviation: float
    lower_quartile: float
    upper_quartile: float

    def __post_init__(self) -> None:
        numeric = (
            self.median,
            self.median_absolute_deviation,
            self.lower_quartile,
            self.upper_quartile,
        )
        if (
            type(self.sample_count) is not int
            or self.sample_count <= 0
            or not all(type(value) is float and np.isfinite(value) for value in numeric)
            or self.median_absolute_deviation < 0.0
            or self.lower_quartile > self.upper_quartile
        ):
            raise ValueError("robust local statistics are invalid")


def extract_image_tiles(
    raster: NDArray[np.generic],
    regions: tuple[TileRegion, ...],
    *,
    halo: int,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> tuple[ImageTile, ...]:
    """Copy bounded core windows with a fixed NumPy ``reflect``/REFLECT_101 halo.

    ``raster`` may be C-contiguous or strided. Accepted layouts are HxW,
    HxWx1, HxWx3 (RGB), and HxWx4 (RGBA), all uint8. Returned buffers are
    C-order and backed by immutable ``bytes``.
    """
    height, width, channels = _validate_raster(raster)
    if type(regions) is not tuple:
        raise TypeError("tile regions must be a tuple")
    policy.check_raster(width, height, tiles=len(regions))

    output_sizes: list[int] = []
    for region in regions:
        if not isinstance(region, TileRegion):
            raise TypeError("tile regions must contain TileRegion values")
        policy.check_tile(region.width, region.height, halo, 1)
        if region.x + region.width > width or region.y + region.height > height:
            raise ValueError("tile region exceeds raster coverage")
        output_sizes.append((region.width + 2 * halo) * (region.height + 2 * halo) * channels)

    total_output = sum(output_sizes)
    peak_workspace = total_output + max(output_sizes)
    first = regions[0]
    policy.check_tile(first.width, first.height, halo, peak_workspace)

    tiles: list[ImageTile] = []
    for region in regions:
        desired_left = region.x - halo
        desired_top = region.y - halo
        desired_right = region.x + region.width + halo
        desired_bottom = region.y + region.height + halo
        source_left = max(desired_left, 0)
        source_top = max(desired_top, 0)
        source_right = min(desired_right, width)
        source_bottom = min(desired_bottom, height)
        crop = raster[source_top:source_bottom, source_left:source_right]
        spatial_pad = (
            (source_top - desired_top, desired_bottom - source_bottom),
            (source_left - desired_left, desired_right - source_right),
        )
        if not halo:
            padded = crop
        elif raster.ndim == 3:
            padded = np.pad(crop, (*spatial_pad, (0, 0)), mode="reflect")
        else:
            padded = np.pad(crop, spatial_pad, mode="reflect")
        pixels = _immutable_uint8(padded)
        tiles.append(ImageTile(pixels=pixels, region=region, halo=halo))
    return tuple(tiles)


def to_luminance(
    tile: ImageTile,
    *,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> LuminanceTile:
    """Convert grayscale/RGB/RGBA uint8 to BT.601 float64 luminance.

    RGBA alpha is intentionally ignored; only the first three RGB channels
    contribute. The output retains the input halo and has range [0, 255].
    """
    _check_tile_instance(tile, policy)
    height, width = tile.pixels.shape[:2]
    plane_bytes = height * width * _FLOAT64.itemsize
    workspace_planes = 2 if tile.pixels.ndim == 2 or tile.pixels.shape[2] == 1 else 3
    policy.check_tile(
        tile.region.width,
        tile.region.height,
        tile.halo,
        workspace_planes * plane_bytes,
    )

    if tile.pixels.ndim == 2:
        values = tile.pixels.astype(_FLOAT64, copy=True)
    elif tile.pixels.shape[2] == 1:
        values = tile.pixels[..., 0].astype(_FLOAT64, copy=True)
    else:
        values = np.empty((height, width), dtype=_FLOAT64)
        temporary = np.empty_like(values)
        np.multiply(tile.pixels[..., 0], _LUMINANCE_WEIGHTS[0], out=values)
        np.multiply(tile.pixels[..., 1], _LUMINANCE_WEIGHTS[1], out=temporary)
        np.add(values, temporary, out=values)
        np.multiply(tile.pixels[..., 2], _LUMINANCE_WEIGHTS[2], out=temporary)
        np.add(values, temporary, out=values)
    return LuminanceTile(
        values=_immutable_float64(values),
        region=tile.region,
        halo=tile.halo,
    )


def smooth_luminance(
    tile: LuminanceTile,
    *,
    kernel_size: int = 3,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> KernelPlane:
    """Apply a normalized binomial 3x3 or 5x5 kernel to the tile core."""
    kernel, radius = _smoothing_kernel(kernel_size)
    _check_luminance_tile(tile, required_halo=radius, policy=policy, workspace_planes=2)
    values = _filter_core(tile, kernel)
    return KernelPlane(
        values=_immutable_float64(values),
        coverage=tile.region,
        halo_used=radius,
    )


def high_pass_residual(
    tile: LuminanceTile,
    *,
    kernel_size: int = 3,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> KernelPlane:
    """Subtract fixed binomial smoothing from luminance over the tile core."""
    kernel, radius = _smoothing_kernel(kernel_size)
    _check_luminance_tile(tile, required_halo=radius, policy=policy, workspace_planes=3)
    smoothed = _filter_core(tile, kernel)
    residual = np.subtract(_core_values(tile), smoothed)
    return KernelPlane(
        values=_immutable_float64(residual),
        coverage=tile.region,
        halo_used=radius,
    )


def finite_differences(
    tile: LuminanceTile,
    *,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> GradientPlanes:
    """Return centered [−0.5, 0, 0.5] horizontal and vertical differences."""
    _check_luminance_tile(tile, required_halo=1, policy=policy, workspace_planes=4)
    halo = tile.halo
    height = tile.region.height
    width = tile.region.width
    values = tile.values
    horizontal = np.subtract(
        values[halo : halo + height, halo + 1 : halo + width + 1],
        values[halo : halo + height, halo - 1 : halo + width - 1],
    )
    horizontal *= 0.5
    vertical = np.subtract(
        values[halo + 1 : halo + height + 1, halo : halo + width],
        values[halo - 1 : halo + height - 1, halo : halo + width],
    )
    vertical *= 0.5
    coverage = tile.region
    return GradientPlanes(
        horizontal=KernelPlane(
            values=_immutable_float64(horizontal),
            coverage=coverage,
            halo_used=1,
        ),
        vertical=KernelPlane(
            values=_immutable_float64(vertical),
            coverage=coverage,
            halo_used=1,
        ),
    )


def robust_local_statistics(
    plane: KernelPlane,
    *,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> RobustLocalStatistics:
    """Return median, MAD, and quartiles for one bounded finite core plane."""
    if not isinstance(plane, KernelPlane):
        raise TypeError("statistics input must be a KernelPlane")
    plane_bytes = plane.values.size * _FLOAT64.itemsize
    policy.check_tile(
        plane.coverage.width,
        plane.coverage.height,
        plane.halo_used,
        4 * plane_bytes,
    )
    flattened = plane.values.reshape(-1)
    median = float(np.median(flattened))
    deviation = float(np.median(np.abs(flattened - median)))
    quartiles = np.quantile(flattened, (0.25, 0.75), method="linear")
    return RobustLocalStatistics(
        sample_count=flattened.size,
        median=median,
        median_absolute_deviation=deviation,
        lower_quartile=float(quartiles[0]),
        upper_quartile=float(quartiles[1]),
    )


def _validate_raster(raster: NDArray[np.generic]) -> tuple[int, int, int]:
    if not isinstance(raster, np.ndarray) or raster.dtype != _UINT8:
        raise TypeError("raster must be a uint8 ndarray")
    if raster.ndim == 2:
        height, width = raster.shape
        channels = 1
    elif raster.ndim == 3 and raster.shape[2] in (1, 3, 4):
        height, width, channels = raster.shape
    else:
        raise ValueError("raster shape must be HxW, HxWx1, HxWx3, or HxWx4")
    if height <= 0 or width <= 0:
        raise ValueError("raster dimensions must be positive")
    return height, width, channels


def _validate_halo(halo: int) -> None:
    if type(halo) is not int or halo < 0:
        raise ValueError("halo must be a nonnegative integer")


def _validate_float_plane(values: NDArray[np.float64], expected: tuple[int, int]) -> None:
    if (
        not isinstance(values, np.ndarray)
        or values.dtype != _FLOAT64
        or values.ndim != 2
        or values.shape != expected
        or not values.flags.c_contiguous
        or not _has_immutable_backing(values)
        or not np.isfinite(values).all()
    ):
        raise ValueError("numeric plane must be finite immutable C-order little-endian float64")


def _has_immutable_backing(array: NDArray[np.generic]) -> bool:
    owner: object = array
    while isinstance(owner, np.ndarray):
        if owner.flags.writeable:
            return False
        owner = owner.base
    return isinstance(owner, bytes)


def _immutable_uint8(array: NDArray[np.generic]) -> NDArray[np.uint8]:
    contiguous = np.ascontiguousarray(array, dtype=_UINT8)
    payload = contiguous.tobytes(order="C")
    return np.frombuffer(payload, dtype=_UINT8).reshape(contiguous.shape)


def _immutable_float64(array: NDArray[np.generic]) -> NDArray[np.float64]:
    contiguous = np.ascontiguousarray(array, dtype=_FLOAT64)
    payload = contiguous.tobytes(order="C")
    return np.frombuffer(payload, dtype=_FLOAT64).reshape(contiguous.shape)


def _check_tile_instance(tile: ImageTile, policy: ForensicResourcePolicy) -> None:
    if not isinstance(tile, ImageTile):
        raise TypeError("luminance input must be an ImageTile")
    policy.check_tile(tile.region.width, tile.region.height, tile.halo, 1)


def _check_luminance_tile(
    tile: LuminanceTile,
    *,
    required_halo: int,
    policy: ForensicResourcePolicy,
    workspace_planes: int,
) -> None:
    if not isinstance(tile, LuminanceTile):
        raise TypeError("kernel input must be a LuminanceTile")
    if tile.halo < required_halo:
        raise ValueError("tile halo is smaller than the kernel radius")
    workspace = tile.region.width * tile.region.height * _FLOAT64.itemsize * workspace_planes
    policy.check_tile(tile.region.width, tile.region.height, tile.halo, workspace)


def _smoothing_kernel(kernel_size: int) -> tuple[NDArray[np.float64], int]:
    if type(kernel_size) is not int or kernel_size not in _SMOOTHING_VECTORS:
        raise ValueError("smoothing kernel size must be 3 or 5")
    vector = np.asarray(_SMOOTHING_VECTORS[kernel_size], dtype=_FLOAT64)
    return np.multiply.outer(vector, vector), kernel_size // 2


def _filter_core(tile: LuminanceTile, kernel: NDArray[np.float64]) -> NDArray[np.float64]:
    size = kernel.shape[0]
    radius = size // 2
    windows = sliding_window_view(tile.values, (size, size))
    start = tile.halo - radius
    selected = windows[
        start : start + tile.region.height,
        start : start + tile.region.width,
    ]
    result: NDArray[np.float64] = np.einsum(
        "ijkl,kl->ij", selected, kernel, dtype=_FLOAT64, optimize=False
    )
    return result


def _core_values(tile: LuminanceTile) -> NDArray[np.float64]:
    halo = tile.halo
    return tile.values[
        halo : halo + tile.region.height,
        halo : halo + tile.region.width,
    ]


class _StreamedContainerError(Exception):
    """Signal invalid output-container bookkeeping without exposing details."""


class _FFmpegPreprocessingTool:
    """Write one prepared representation directly to a controlled target."""

    def __init__(self, *, executable: str, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    def audio_precision(
        self, source: Path, *, timeout_seconds: float | None
    ) -> AudioPrecisionFacts:
        return probe_audio(
            source, executable="ffprobe", timeout=self._effective_timeout(timeout_seconds)
        )

    def precision_window(
        self,
        source: Path,
        facts: AudioPrecisionFacts,
        requested: IndexRange,
        *,
        timeout_seconds: float | None,
    ) -> DecodedAudioWindow:
        return decode_audio_window(
            source,
            facts,
            requested,
            executable=self._executable,
            timeout=self._effective_timeout(timeout_seconds),
        )

    def normalized_audio(
        self,
        source: Path,
        target: Path,
        *,
        sample_rate_hz: int,
        channels: int,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Create a signed 16-bit little-endian PCM WAV without rate/channel changes."""
        self._run(
            source,
            target,
            (
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "pcm_s16le",
                "-ar",
                str(sample_rate_hz),
                "-ac",
                str(channels),
                "-f",
                "wav",
            ),
            phase="audio_normalize",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def audio_fragment(
        self,
        source: Path,
        target: Path,
        *,
        start_seconds: float,
        duration_seconds: float,
        sample_rate_hz: int,
        channels: int,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Stream one factual, unpadded interval from a normalized WAV."""
        self._run(
            source,
            target,
            (
                "-ss",
                _timestamp(start_seconds),
                "-t",
                _timestamp(duration_seconds),
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "pcm_s16le",
                "-ar",
                str(sample_rate_hz),
                "-ac",
                str(channels),
                "-f",
                "wav",
            ),
            phase="audio_fragment",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def spectrogram(
        self,
        source: Path,
        target: Path,
        *,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Create one bounded PNG spectrogram from a normalized audio artifact."""
        self._run(
            source,
            target,
            (
                "-lavfi",
                "showspectrumpic=s=640x320:legend=disabled",
                "-frames:v",
                "1",
                "-c:v",
                "png",
                "-f",
                "image2",
            ),
            phase="audio_spectrogram",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def sampled_frame(
        self,
        source: Path,
        target: Path,
        *,
        timestamp_seconds: float,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Decode one representative PNG at a deterministic target timestamp."""
        self._run(
            source,
            target,
            (
                "-ss",
                _timestamp(timestamp_seconds),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-c:v",
                "png",
                "-f",
                "image2",
            ),
            phase="video_frame",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def extracted_audio(
        self,
        source: Path,
        target: Path,
        *,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Extract the primary video audio stream as lossless FLAC."""
        self._run(
            source,
            target,
            (
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "flac",
                "-f",
                "flac",
            ),
            phase="video_audio",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def _run(
        self,
        source: Path,
        target: Path,
        output_arguments: Sequence[str],
        *,
        phase: str,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None,
    ) -> None:
        arguments = [
            self._executable,
            "-v",
            "error",
            "-nostdin",
            "-xerror",
            "-err_detect",
            "explode",
            "-n",
            "-protocol_whitelist",
            "file",
            "-i",
            str(source.absolute()),
            *output_arguments,
            "pipe:1",
        ]
        effective_timeout = self._effective_timeout(timeout_seconds)
        started_at = monotonic()
        try:
            with artifact_budget.open_output(target) as output:
                result = run_bounded_process(
                    arguments,
                    cwd=target.parent,
                    timeout_seconds=effective_timeout,
                    stdout_limit_bytes=artifact_budget.remaining_bytes,
                    stdout_sink=output,
                )
        except (ProcessOutputLimitError, _GeneratedArtifactLimitError):
            raise PreprocessingError("resource_limit", phase) from None
        except _GeneratedArtifactWriteError:
            raise PreprocessingError("artifact_write", phase) from None
        except ProcessTimeoutError:
            raise PreprocessingError("media_tool", f"{phase}_timeout") from None
        except ProcessInfrastructureError as error:
            if error.phase == "stdout_write":
                raise PreprocessingError("artifact_write", phase) from None
            raise PreprocessingError(
                "infrastructure",
                f"{phase}_process",
                _cleanup_safety_barrier=error._cleanup_safety_barrier,
            ) from None
        if result.return_code != 0:
            raise PreprocessingError("media_tool", phase)
        try:
            if phase in {"audio_normalize", "audio_fragment"}:
                _finalize_streamed_wav(target)
            elif phase == "video_audio":
                remaining_timeout = effective_timeout - (monotonic() - started_at)
                if remaining_timeout <= 0:
                    raise PreprocessingError("media_tool", "video_audio_timeout")
                self._finalize_streamed_flac(
                    target,
                    timeout_seconds=remaining_timeout,
                )
        except _GeneratedArtifactWriteError:
            raise PreprocessingError("artifact_write", phase) from None
        except _StreamedContainerError:
            raise PreprocessingError("media_tool", phase) from None

    def _finalize_streamed_flac(
        self,
        target: Path,
        *,
        timeout_seconds: float,
    ) -> None:
        arguments = [
            self._executable,
            "-v",
            "error",
            "-nostdin",
            "-xerror",
            "-err_detect",
            "explode",
            "-progress",
            "pipe:1",
            "-stats_period",
            "3600",
            "-protocol_whitelist",
            "file",
            "-i",
            str(target.absolute()),
            "-map",
            "0:a:0",
            "-f",
            "null",
            os.devnull,
        ]
        try:
            result = run_bounded_process(
                arguments,
                cwd=target.parent,
                timeout_seconds=timeout_seconds,
                stdout_limit_bytes=_MAX_FLAC_PROGRESS_BYTES,
            )
        except ProcessOutputLimitError:
            raise _StreamedContainerError from None
        except ProcessTimeoutError:
            raise PreprocessingError("media_tool", "video_audio_timeout") from None
        except ProcessInfrastructureError as error:
            raise PreprocessingError(
                "infrastructure",
                "video_audio_process",
                _cleanup_safety_barrier=error._cleanup_safety_barrier,
            ) from None
        if result.return_code != 0 or result.stdout is None:
            raise _StreamedContainerError
        _finalize_streamed_flac(target, result.stdout)

    def _effective_timeout(self, timeout_seconds: float | None) -> float:
        if timeout_seconds is None:
            return self._timeout_seconds
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise PreprocessingError("invariant", "execution_budget")
        return min(self._timeout_seconds, float(timeout_seconds))


def _timestamp(value: float) -> str:
    return format(value, ".9f").rstrip("0").rstrip(".") or "0"


def _finalize_streamed_wav(target: Path) -> None:
    """Replace non-seekable RIFF sentinels without growing the artifact."""
    try:
        file_size = target.stat().st_size
        if file_size < 20 or file_size - 8 > _RIFF_UINT32_MAX:
            raise _StreamedContainerError
        with target.open("r+b") as stream:
            if stream.read(12) != b"RIFF\xff\xff\xff\xffWAVE":
                raise _StreamedContainerError
            chunk_offset = 12
            while chunk_offset + 8 <= file_size:
                stream.seek(chunk_offset)
                chunk_header = stream.read(8)
                if len(chunk_header) != 8:
                    raise _StreamedContainerError
                chunk_size = int.from_bytes(chunk_header[4:], "little")
                if chunk_header[:4] == b"data":
                    data_size = file_size - chunk_offset - 8
                    if data_size > _RIFF_UINT32_MAX:
                        raise _StreamedContainerError
                    _rewrite_existing(
                        stream,
                        4,
                        (file_size - 8).to_bytes(4, "little"),
                    )
                    _rewrite_existing(
                        stream,
                        chunk_offset + 4,
                        data_size.to_bytes(4, "little"),
                    )
                    stream.flush()
                    return
                chunk_offset += 8 + chunk_size + (chunk_size & 1)
    except OSError:
        raise _GeneratedArtifactWriteError from None
    raise _StreamedContainerError


def _finalize_streamed_flac(target: Path, progress: bytes) -> None:
    """Fill STREAMINFO total samples measured by one bounded decode pass."""
    out_time_us: int | None = None
    completed = False
    for line in progress.splitlines():
        key, separator, value = line.partition(b"=")
        if not separator:
            continue
        if key == b"out_time_us":
            try:
                out_time_us = int(value)
            except ValueError:
                raise _StreamedContainerError from None
        elif key == b"progress" and value == b"end":
            completed = True
    if not completed or out_time_us is None or out_time_us <= 0:
        raise _StreamedContainerError

    try:
        with target.open("r+b") as stream:
            header = stream.read(42)
            if (
                len(header) != 42
                or header[:4] != b"fLaC"
                or header[4] & 0x7F
                or int.from_bytes(header[5:8], "big") != 34
            ):
                raise _StreamedContainerError
            streaminfo = int.from_bytes(header[18:26], "big")
            sample_rate_hz = streaminfo >> 44
            total_samples = (out_time_us * sample_rate_hz + 500_000) // 1_000_000
            if (
                sample_rate_hz <= 0
                or total_samples <= 0
                or total_samples > _FLAC_TOTAL_SAMPLES_MASK
            ):
                raise _StreamedContainerError
            updated = (streaminfo & ~_FLAC_TOTAL_SAMPLES_MASK) | total_samples
            _rewrite_existing(stream, 18, updated.to_bytes(8, "big"))
            stream.flush()
    except OSError:
        raise _GeneratedArtifactWriteError from None


def _rewrite_existing(stream: BinaryIO, offset: int, data: bytes) -> None:
    """Overwrite fixed header bytes and reject a short physical write."""
    stream.seek(offset)
    if stream.write(data) != len(data):
        raise _GeneratedArtifactWriteError


@dataclass(frozen=True, slots=True)
class _JpegStructure:
    header: JpegHeader
    tables: tuple[JpegQuantizationTable, ...]


@dataclass(slots=True)
class _JpegParser:
    """Bounded marker parser; entropy is skipped, never decoded or repaired."""

    data: bytes
    header: JpegHeader | None = None
    tables: dict[int, JpegQuantizationTable] = field(default_factory=dict)
    huffman: set[tuple[int, int]] = field(default_factory=set)
    progression: dict[tuple[int, int], int] = field(default_factory=dict)
    marker_count: int = 0
    payload_bytes: int = 0
    scans: int = 0
    restart_interval: int = 0

    def marker(self) -> None:
        self.marker_count += 1
        if self.marker_count > _FORENSIC_POLICY.jpeg_markers:
            raise PreprocessingError("resource_limit", "jpeg_structure_limit")

    def parse(self) -> _JpegStructure:
        if len(self.data) > _FORENSIC_POLICY.jpeg_input_bytes:
            raise PreprocessingError("resource_limit", "jpeg_input_limit")
        if not self.data.startswith(b"\xff\xd8"):
            raise ValueError("signature")
        self.marker()  # SOI is included in the total marker budget.
        position = 2
        while position < len(self.data):
            self.marker()
            if self.data[position] != 255:
                raise ValueError("marker")
            while position < len(self.data) and self.data[position] == 255:
                position += 1
            if position >= len(self.data):
                raise ValueError("marker exhaustion")
            marker = self.data[position]
            position += 1
            if marker == 0xD9:
                if (
                    position != len(self.data)
                    or self.header is None
                    or not self.scans
                    or any(
                        (c.component_id, 0) not in self.progression for c in self.header.components
                    )
                ):
                    raise ValueError("incomplete image or trailing bytes")
                return _JpegStructure(
                    self.header, tuple(self.tables[k] for k in sorted(self.tables))
                )
            if (
                marker not in {0xC0, 0xC2, 0xDB, 0xC4, 0xDD, 0xDA, 0xFE}
                and not 0xE0 <= marker <= 0xEF
            ):
                raise ValueError("unsupported marker")
            if position + 2 > len(self.data):
                raise ValueError("length exhaustion")
            length = int.from_bytes(self.data[position : position + 2], "big")
            if length < 2 or position + length > len(self.data):
                raise ValueError("segment length")
            self.payload_bytes += length
            if self.payload_bytes > _FORENSIC_POLICY.jpeg_marker_bytes:
                raise PreprocessingError("resource_limit", "jpeg_structure_limit")
            payload = self.data[position + 2 : position + length]
            position += length
            if marker in {0xC0, 0xC2}:
                self.sof(payload, marker)
            elif marker == 0xDB:
                self.dqt(payload)
            elif marker == 0xC4:
                self.dht(payload)
            elif marker == 0xDD:
                if len(payload) != 2:
                    raise ValueError("restart interval")
                self.restart_interval = int.from_bytes(payload, "big")
            elif marker == 0xDA:
                self.sos(payload)
                position = self.entropy_end(position)
        raise ValueError("missing EOI")

    def sof(self, payload: bytes, marker: int) -> None:
        if self.header is not None or len(payload) < 6 or len(payload) != 6 + 3 * payload[5]:
            raise ValueError("SOF definition")
        if payload[0] != 8:
            raise ValueError("unsupported sample precision")
        self.header = JpegHeader(
            width=int.from_bytes(payload[3:5], "big"),
            height=int.from_bytes(payload[1:3], "big"),
            precision_bits=8,
            coding="baseline" if marker == 0xC0 else "progressive",
            components=tuple(
                JpegComponent(
                    component_id=payload[i],
                    horizontal_sampling=payload[i + 1] >> 4,
                    vertical_sampling=payload[i + 1] & 15,
                    quantization_table_id=payload[i + 2],
                )
                for i in range(6, len(payload), 3)
            ),
        )
        try:
            self.header.preflight(len(self.data))
        except ValueError:
            raise PreprocessingError("resource_limit", "jpeg_preflight") from None

    def dqt(self, payload: bytes) -> None:
        if not payload or self.scans:
            raise ValueError("late or empty DQT")
        position = 0
        # Derive the JPEG zigzag positions rather than copying a decoder table.
        zigzag: list[tuple[int, int]] = []
        for diagonal in range(15):
            rows = range(max(0, diagonal - 7), min(7, diagonal) + 1)
            zigzag.extend(
                (r, diagonal - r) for r in (reversed(rows) if diagonal % 2 == 0 else rows)
            )
        while position < len(payload):
            precision, table_id = payload[position] >> 4, payload[position] & 15
            position += 1
            size = 64 * (precision + 1)
            if (
                precision > 1
                or table_id > 3
                or table_id in self.tables
                or position + size > len(payload)
            ):
                raise ValueError("DQT definition")
            values = [0] * 64
            for index, (row, column) in enumerate(zigzag):
                offset = position + index * (precision + 1)
                values[row * 8 + column] = int.from_bytes(
                    payload[offset : offset + precision + 1], "big"
                )
            self.tables[table_id] = JpegQuantizationTable(
                table_id=table_id, precision_bits=8 if precision == 0 else 16, values=tuple(values)
            )
            position += size

    def dht(self, payload: bytes) -> None:
        position = 0
        if not payload:
            raise ValueError("empty DHT")
        while position < len(payload):
            if position + 17 > len(payload):
                raise ValueError("DHT length")
            table_class, table_id = payload[position] >> 4, payload[position] & 15
            counts = payload[position + 1 : position + 17]
            symbols = sum(counts)
            slots = 1
            for count in counts:
                slots = slots * 2 - count
                if slots < 0:
                    raise ValueError("oversubscribed Huffman table")
            if (
                table_class > 1
                or table_id > 3
                or not 1 <= symbols <= 256
                or position + 17 + symbols > len(payload)
            ):
                raise ValueError("DHT definition")
            self.huffman.add((table_class, table_id))
            position += 17 + symbols

    def sos(self, payload: bytes) -> None:
        if (
            self.header is None
            or len(payload) < 6
            or not 1 <= payload[0] <= 4
            or len(payload) != 4 + 2 * payload[0]
        ):
            raise ValueError("SOS length or ordering")
        components = {c.component_id: c for c in self.header.components}
        ids = payload[1:-3:2]
        ss, se, approximation = payload[-3:]
        ah, al = approximation >> 4, approximation & 15
        if len(set(ids)) != len(ids) or any(c not in components for c in ids):
            raise ValueError("SOS components")
        if self.header.coding == "baseline":
            if (ss, se, ah, al) != (0, 63, 0, 0) or any(
                t.precision_bits != 8 for t in self.tables.values()
            ):
                raise ValueError("baseline scan")
        elif (
            not 0 <= ss <= se <= 63
            or (ss == 0 and se != 0)
            or (ss > 0 and len(ids) != 1)
            or ah > 13
            or al > 13
            or (ah != 0 and ah != al + 1)
        ):
            raise ValueError("progressive scan")
        for component_id, selector in zip(ids, payload[2:-3:2], strict=True):
            if (
                components[component_id].quantization_table_id not in self.tables
                or selector >> 4 > 3
                or selector & 15 > 3
            ):
                raise ValueError("missing quantization or invalid Huffman selector")
            if (ss == 0 and ah == 0 and (0, selector >> 4) not in self.huffman) or (
                se > 0 and (1, selector & 15) not in self.huffman
            ):
                raise ValueError("missing Huffman table")
            for coefficient in range(ss, se + 1):
                key = (component_id, coefficient)
                if (ah == 0 and key in self.progression) or (
                    ah and self.progression.get(key) != ah
                ):
                    raise ValueError("inconsistent scan progression")
                self.progression[key] = al
        self.scans += 1

    def entropy_end(self, position: int) -> int:
        restart = 0
        while position < len(self.data):
            position = self.data.find(b"\xff", position)
            if position < 0:
                break
            start = position
            position += 1
            while position < len(self.data) and self.data[position] == 255:
                position += 1
            if position >= len(self.data):
                break
            marker = self.data[position]
            if marker == 0:
                position += 1
            elif 0xD0 <= marker <= 0xD7:
                self.marker()
                if not self.restart_interval or marker != 0xD0 + restart:
                    raise ValueError("restart ordering")
                restart = (restart + 1) % 8
                position += 1
            else:
                return start
        raise ValueError("entropy exhaustion")


def _parse_jpeg(data: bytes) -> _JpegStructure:
    try:
        return _JpegParser(data).parse()
    except ValueError:
        raise PreprocessingError("decode", "jpeg_structure") from None


_JPEG_PROCESS_BYTES = 4096
_JPEG_PROCESS_SECONDS = 30.0


def _decode_jpeg_coefficients(
    source: Path, source_sha256: str, *, timeout_seconds: float | None
) -> None:
    """Only the child imports jpegio. Files have already been registered and charged."""
    if source.name != "source":
        raise PreprocessingError("invariant", "jpeg_source_name")
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    }
    # Coefficient projection needs no BLAS workers; bound NumPy's native pool.
    environment["OPENBLAS_NUM_THREADS"] = "1"
    executable = sys.executable
    if os.name == "nt":
        # The Windows venv executable is a redirector that spawns another process.
        # Launch CPython itself so terminate/kill/reap own the actual decoder.
        executable = vars(sys)["_base_executable"]
        if not isinstance(executable, str) or not Path(executable).is_absolute():
            raise PreprocessingError("invariant", "jpeg_interpreter")
        environment["__PYVENV_LAUNCHER__"] = sys.executable
    try:
        result = run_bounded_process(
            [
                executable,
                "-I",
                "-c",
                "from fakedetector.preprocessing._media_tools import _jpeg_child_main; "
                "_jpeg_child_main()",
                "--jpeg-child-v1",
                source_sha256,
            ],
            cwd=source.parent,
            timeout_seconds=min(_JPEG_PROCESS_SECONDS, timeout_seconds or _JPEG_PROCESS_SECONDS),
            stdout_limit_bytes=_JPEG_PROCESS_BYTES,
            stderr_limit_bytes=_JPEG_PROCESS_BYTES,
            environment=environment,
        )
    except ProcessOutputLimitError:
        raise PreprocessingError("resource_limit", "jpeg_native_output") from None
    except ProcessTimeoutError:
        raise PreprocessingError("media_tool", "jpeg_native_timeout") from None
    except ProcessInfrastructureError as error:
        raise PreprocessingError(
            "infrastructure",
            "jpeg_native_process",
            _cleanup_safety_barrier=error._cleanup_safety_barrier,
        ) from None
    if result.return_code != 0:
        raise PreprocessingError("decode", "jpeg_native_error")
    if result.stderr:
        raise PreprocessingError("decode", "jpeg_native_warning")
    expected = json.dumps(
        {"version": 1, "status": "clean", "source_sha256": source_sha256}, separators=(",", ":")
    ).encode("ascii")
    if result.stdout != expected or result.stderr != b"":
        raise PreprocessingError("infrastructure", "jpeg_native_protocol")


def _jpeg_child(source_sha256: str) -> None:
    """Closed child entry: bounded source, preflight again, fixed-size mapped outputs."""
    from fakedetector._filesystem import require_regular_file

    source = Path("source")
    require_regular_file(source)
    with source.open("rb") as stream:
        data = stream.read(_FORENSIC_POLICY.jpeg_input_bytes + 1)
    structure = _parse_jpeg(data)
    if hashlib.sha256(data).hexdigest() != source_sha256:
        raise ValueError("source identity")
    allocation = structure.header.preflight(len(data))
    del data
    targets = tuple(
        Path(f"jpeg_component_{index}.raw") for index in range(len(allocation.block_shapes))
    )
    for target, shape in zip(targets, allocation.block_shapes, strict=True):
        require_regular_file(target)
        if target.stat().st_size != shape[0] * shape[1] * 64 * 4:
            raise ValueError("output extent")
    jpegio = importlib.import_module("jpegio")
    decoded = jpegio.read("source")
    if (
        decoded is None
        or len(decoded.coef_arrays) != len(targets)
        or len(decoded.comp_info) != len(targets)
    ):
        raise ValueError("native components")
    for component, actual in zip(structure.header.components, decoded.comp_info, strict=True):
        if (
            actual.component_id,
            actual.h_samp_factor,
            actual.v_samp_factor,
            actual.quant_tbl_no,
        ) != (
            component.component_id,
            component.horizontal_sampling,
            component.vertical_sampling,
            component.quantization_table_id,
        ):
            raise ValueError("native component mismatch")
    if len(decoded.quant_tables) != len(structure.tables):
        raise ValueError("native quantization count")
    # pyjpegio exposes a compact list in ascending JPEG table-slot order;
    # component selectors retain the original (possibly sparse) table IDs.
    for table, native_table in zip(structure.tables, decoded.quant_tables, strict=True):
        if native_table.shape != (8, 8) or tuple(int(v) for v in native_table.flat) != table.values:
            raise ValueError("native quantization mismatch")
    for target, shape, plane in zip(
        targets, allocation.block_shapes, decoded.coef_arrays, strict=True
    ):
        rows, columns = shape
        if (
            plane.shape != (rows * 8, columns * 8)
            or plane.dtype.kind not in {"i", "u"}
            or int(plane.min()) < -(1 << 31)
            or int(plane.max()) >= 1 << 31
        ):
            raise ValueError("native coefficient layout or range")
        with (
            target.open("r+b") as output,
            mmap.mmap(output.fileno(), rows * columns * 256, access=mmap.ACCESS_WRITE) as mapped,
        ):
            for row in range(rows):
                blocks = plane[row * 8 : (row + 1) * 8].reshape(8, columns, 8).transpose(1, 0, 2)
                mapped[row * columns * 256 : (row + 1) * columns * 256] = blocks.astype(
                    "<i4", copy=False
                ).tobytes(order="C")
            mapped.flush()
    sys.stdout.write(
        json.dumps(
            {"version": 1, "status": "clean", "source_sha256": source_sha256}, separators=(",", ":")
        )
    )


def _jpeg_child_main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "--jpeg-child-v1":
        sys.exit(2)
    try:
        _jpeg_child(sys.argv[2])
    except Exception:
        # Do not emit native objects, paths, exception text, or a traceback.
        sys.exit(2)


_FORMATS = {"u8": 8, "s16": 16, "s32": 32, "flt": 32, "dbl": 64}
_FRAME = re.compile(
    rb"(?m)^\[Parsed_ashowinfo_\d+ @ [0-9a-fA-Fx]+\] "
    rb"n:(\d+) pts:(-?\d+) pts_time:\S+ fmt:(\w+) channels:(\d+) "
    rb"chlayout:([^\r\n]{1,64}?) rate:(\d+) nb_samples:(\d+) checksum:"
)


def select_audio_windows(
    total_samples: int,
    rate: int,
    channels: int,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> tuple[IndexRange, ...]:
    """Beginning/center/end; merge overlaps only while the merged extent fits policy.

    Overlapping candidates whose union exceeds the ceiling are clipped at the
    previous stop. This retains coverage without duplicate samples or larger windows.
    """
    policy.check_audio(1, channels, rate)
    if type(total_samples) is not int or not 1 <= total_samples < 1 << 63:
        raise ValueError("invalid declared audio duration")
    size = min(
        total_samples, policy.audio_window_seconds * rate, policy.audio_window_samples // channels
    )
    starts: tuple[int, ...] = (0, (total_samples - size) // 2, total_samples - size)
    if policy.audio_windows == 1:
        starts = (0,)
    elif policy.audio_windows == 2:
        starts = (0, total_samples - size)
    result: list[IndexRange] = []
    for start in sorted(set(starts)):
        stop = start + size
        if result and start <= result[-1].stop:
            if stop - result[-1].start <= size:
                result[-1] = IndexRange(start=result[-1].start, stop=stop)
                continue
            start = result[-1].stop
        if stop > start:
            result.append(IndexRange(start=start, stop=stop))
    return tuple(result)


def _process(
    arguments: list[str], source: Path, timeout: float, limit: int, phase: str
) -> ProcessResult:
    if not math.isfinite(timeout) or timeout <= 0:
        raise PreprocessingError("invariant", "execution_budget")
    try:
        result = run_bounded_process(
            arguments,
            cwd=source.parent,
            timeout_seconds=min(timeout, 30.0),
            stdout_limit_bytes=limit,
            stderr_limit_bytes=_FORENSIC_POLICY.timing_probe_bytes,
        )
    except ProcessOutputLimitError:
        raise PreprocessingError("resource_limit", f"{phase}_overflow") from None
    except ProcessTimeoutError:
        raise PreprocessingError("media_tool", f"{phase}_timeout") from None
    except ProcessInfrastructureError as error:
        raise PreprocessingError(
            "infrastructure",
            f"{phase}_process",
            _cleanup_safety_barrier=error._cleanup_safety_barrier,
        ) from None
    if result.return_code != 0 or result.stdout is None:
        # Only the decoder's explicit invalid-data diagnostic establishes malformed
        # media; other failures retain the unknown decoder-failure classification.
        if b"Invalid data found when processing input" in (result.stderr or b""):
            raise PreprocessingError("decode", f"{phase}_malformed_media")
        raise PreprocessingError("decode", f"{phase}_decoder")
    return result


def probe_audio(source: Path, *, executable: str, timeout: float) -> AudioPrecisionFacts:
    result = _process(
        [
            executable,
            "-v",
            "error",
            "-protocol_whitelist",
            "file",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index,codec_name,sample_fmt,sample_rate,channels,channel_layout,"
            "bits_per_sample,bits_per_raw_sample,duration,start_time",
            "-of",
            "json",
            str(source.absolute()),
        ],
        source,
        min(timeout, 15.0),
        _FORENSIC_POLICY.timing_probe_bytes,
        "audio_precision_probe",
    )
    try:
        payload = json.loads(result.stdout or b"")
        if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
            raise ValueError
        stream = payload["streams"][0]
        if len(payload["streams"]) != 1 or not isinstance(stream, dict):
            raise ValueError
        bits = int(stream.get("bits_per_sample", 0)) or None
        raw_bits = int(stream.get("bits_per_raw_sample", 0)) or None
        return AudioPrecisionFacts(
            stream_index=int(stream["index"]),
            codec=stream["codec_name"],
            source_bits=raw_bits or bits,
            decoder_format="unknown",
            sample_rate=int(stream["sample_rate"]),
            channels=int(stream["channels"]),
            declared_bits_per_sample=bits,
            declared_bits_per_raw_sample=raw_bits,
            declared_sample_format=stream.get("sample_fmt"),
            declared_channel_layout=stream.get("channel_layout"),
            declared_duration_seconds=_optional_seconds(stream.get("duration")),
            declared_start_seconds=_optional_seconds(stream.get("start_time")),
        )
    except (ValueError, TypeError, KeyError, IndexError):
        raise PreprocessingError("decode", "audio_precision_malformed") from None


def _optional_seconds(value: object) -> float | None:
    if value is None or value == "N/A":
        return None
    if not isinstance(value, str):
        raise ValueError
    result = float(value)
    if not math.isfinite(result):
        raise ValueError
    return result


@dataclass(frozen=True, slots=True)
class DecodedAudioWindow:
    facts: AudioPrecisionFacts
    first_pts: int
    values: NDArray[np.generic]


def decode_audio_window(
    source: Path,
    facts: AudioPrecisionFacts,
    requested: IndexRange,
    *,
    executable: str,
    timeout: float,
) -> DecodedAudioWindow:
    try:
        _FORENSIC_POLICY.check_audio(requested.count, facts.channels, facts.sample_rate)
    except ValueError:
        raise PreprocessingError("resource_limit", "audio_precision_preflight") from None
    declared = facts.declared_sample_format or "unknown"
    base = declared.removesuffix("p")
    if base not in _FORMATS or base in ("u8", "s16", "s32") and (facts.source_bits or 0) > 32:
        raise PreprocessingError("decode", "audio_precision_unsupported_format")
    integer = base in ("u8", "s16", "s32")
    encoding = "s32le" if integer else "f64le"
    dtype = "<i4" if integer else "<f8"
    rate = facts.sample_rate
    result = _process(
        [
            executable,
            "-hide_banner",
            "-nostats",
            "-v",
            "info",
            "-nostdin",
            "-xerror",
            "-err_detect",
            "explode",
            "-copyts",
            "-protocol_whitelist",
            "file",
            "-ss",
            format(requested.start / rate, ".12f"),
            "-t",
            format(requested.count / rate, ".12f"),
            "-i",
            str(source.absolute()),
            "-map",
            f"0:{facts.stream_index}",
            "-vn",
            "-sn",
            "-dn",
            "-af",
            f"asettb=1/{rate},atrim=end_sample={requested.count},ashowinfo",
            "-dither_method",
            "none",
            "-c:a",
            f"pcm_{encoding}",
            "-f",
            encoding,
            "pipe:1",
        ],
        source,
        timeout,
        requested.count * facts.channels * np.dtype(dtype).itemsize,
        "audio_precision_window",
    )
    output = result.stdout or b""
    records = _FRAME.findall(result.stderr or b"")
    if not records or not output:
        raise PreprocessingError("decode", "audio_precision_empty_window")
    try:
        first_pts = int(records[0][1])
        expected_pts = first_pts
        layout = records[0][4].decode("ascii")
        count = 0
        for ordinal, (
            number,
            pts,
            fmt,
            channels,
            channel_layout,
            sample_rate,
            samples,
        ) in enumerate(records):
            if (
                int(number) != ordinal
                or int(pts) != expected_pts
                or fmt.decode("ascii") != declared
                or int(channels) != facts.channels
                or int(sample_rate) != rate
                or channel_layout.decode("ascii") != layout
                or int(samples) <= 0
            ):
                raise ValueError
            count += int(samples)
            expected_pts += int(samples)
        if (
            count > requested.count
            or len(output) != count * facts.channels * np.dtype(dtype).itemsize
        ):
            raise ValueError
        values = np.frombuffer(output, dtype=dtype).reshape(count, facts.channels)
        if not np.isfinite(values).all():
            raise ValueError
        shift = 0
        if integer:
            precision = _FORMATS[base]
            if base == "s32" and facts.declared_bits_per_raw_sample is not None:
                precision = facts.declared_bits_per_raw_sample
            shift = 32 - precision
            if shift < 0 or shift > 24 or np.any(values.astype(np.int64) % (1 << shift)):
                raise ValueError
            values = np.frombuffer((values >> shift).astype("<i4").tobytes(), dtype="<i4").reshape(
                count, facts.channels
            )
        updated = facts.model_dump()
        updated.update(
            decoder_format=base,
            decoded_planar=declared.endswith("p"),
            decoder_storage_bits=_FORMATS[base],
            decoded_sample_rate=rate,
            decoded_channels=facts.channels,
            integer_right_shift=shift,
            decoded_channel_layout=layout,
        )
        observed = AudioPrecisionFacts.model_validate(updated)
    except (ValueError, UnicodeError, TypeError):
        raise PreprocessingError("decode", "audio_precision_observation_mismatch") from None
    return DecodedAudioWindow(observed, first_pts, cast(NDArray[np.generic], values))


def _freeze(values: NDArray[np.generic]) -> NDArray[np.generic]:
    return np.frombuffer(values.tobytes(order="C"), dtype=values.dtype).reshape(values.shape)


def validate_samples(
    samples: NDArray[np.generic], rate: int, policy: ForensicResourcePolicy = _FORENSIC_POLICY
) -> None:
    if (
        not isinstance(samples, np.ndarray)
        or samples.ndim != 2
        or samples.dtype.str not in ("<i4", "<f8")
        or not samples.flags.c_contiguous
        or not _has_immutable_backing(samples)
    ):
        raise ValueError("audio requires immutable little-endian sample/channel storage")
    policy.check_audio(samples.shape[0], samples.shape[1], rate)
    if not np.isfinite(samples).all():
        raise ValueError("audio samples must be finite")


@dataclass(frozen=True, slots=True)
class AudioFrames:
    """Read-only strided (frame, channel, sample) view with window-relative coverage."""

    values: NDArray[np.generic]
    hop: int
    covered_samples: int
    dropped_tail_samples: int


def frame_audio(
    samples: NDArray[np.generic],
    *,
    sample_rate: int,
    frame_length: int,
    hop: int,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> AudioFrames:
    validate_samples(samples, sample_rate, policy)
    policy.check_spectral(frame_length, hop, 1, 1)
    count = max(0, 1 + (samples.shape[0] - frame_length) // hop)
    if count:
        policy.check_spectral(frame_length, hop, count * samples.shape[1], 1)
        values = np.lib.stride_tricks.sliding_window_view(samples, frame_length, axis=0)[::hop]
        covered = (count - 1) * hop + frame_length
    else:
        values = np.frombuffer(b"", dtype=samples.dtype).reshape(0, samples.shape[1], frame_length)
        covered = 0
    return AudioFrames(values, hop, covered, samples.shape[0] - covered)


def periodic_hann(length: int) -> NDArray[np.generic]:
    """w[k] = (1 - cos(2*pi*k/N))/2, k=0..N-1; N=1 gives [0]."""
    if type(length) is not int or not 1 <= length <= _FORENSIC_POLICY.fft_size:
        raise ValueError("Hann length exceeds policy")
    return _freeze((0.5 - 0.5 * np.cos(2 * np.pi * np.arange(length) / length)).astype("<f8"))


def frequency_bins(sample_rate: int, n_fft: int) -> NDArray[np.generic]:
    _FORENSIC_POLICY.check_audio(1, 1, sample_rate)
    _FORENSIC_POLICY.check_spectral(n_fft, n_fft, 1, 1)
    return _freeze(np.arange(n_fft // 2 + 1, dtype="<f8") * (sample_rate / n_fft))


@dataclass(frozen=True, slots=True)
class SpectralBatch:
    """Frame ordinals; sample start = window start + ordinal * hop."""

    first_frame: int
    values: NDArray[np.generic]


def stft_batches(
    samples: NDArray[np.generic],
    *,
    sample_rate: int,
    n_fft: int,
    hop: int,
    scaling: Literal["complex", "magnitude", "power"] = "magnitude",
    window: Literal["hann", "rectangular"] = "hann",
    batch_size: int = 32,
    policy: ForensicResourcePolicy = _FORENSIC_POLICY,
) -> Iterator[SpectralBatch]:
    """Unnormalized rFFT, independent channels, increasing nonnegative bins.

    Power is abs(rFFT)**2, never PSD. No centering, padding, amplitude correction
    or one-sided doubling. At most one float64/complex128 batch is materialized.
    """
    frames = frame_audio(
        samples, sample_rate=sample_rate, frame_length=n_fft, hop=hop, policy=policy
    )
    policy.check_spectral(n_fft, hop, max(1, frames.values.shape[0] * samples.shape[1]), 1)
    if type(batch_size) is not int or not 1 <= batch_size <= policy.spectral_batch:
        raise ValueError("spectral batch exceeds policy")
    if scaling not in ("complex", "magnitude", "power") or window not in ("hann", "rectangular"):
        raise ValueError("unknown spectral definition")
    # Includes input conversion, multiply, promoted FFT/workspace, output + immutable copy.
    workspace = batch_size * samples.shape[1] * (n_fft * 16 + (n_fft // 2 + 1) * 64)
    if workspace > policy.residual_workspace_bytes:
        raise ValueError("spectral workspace exceeds policy")
    weights = periodic_hann(n_fft) if window == "hann" else np.ones(n_fft, dtype="<f8")

    def batches() -> Iterator[SpectralBatch]:
        for start in range(0, frames.values.shape[0], batch_size):
            values = frames.values[start : start + batch_size].astype("<f8") * weights
            with np.errstate(over="ignore", invalid="ignore"):
                spectrum = np.fft.rfft(values, n=n_fft, axis=-1, norm="backward")
                output = spectrum if scaling == "complex" else np.abs(spectrum)
                if scaling == "power":
                    output = np.square(output)
            if not np.isfinite(output).all():
                raise ValueError("nonfinite spectral output")
            yield SpectralBatch(
                start, _freeze(output.astype("<c16" if scaling == "complex" else "<f8"))
            )

    return batches()
