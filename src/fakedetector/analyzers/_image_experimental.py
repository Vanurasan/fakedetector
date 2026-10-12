"""Bounded N-MAD-MATCH-1 and R-D2-MATCH-1 descriptive image profiles."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pydantic import JsonValue

from fakedetector.analyzers._experimental_common import _measurement_result
from fakedetector.analyzers._models import AnalyzerRequest, ApplicabilityResult
from fakedetector.analyzers._real_common import _artifacts
from fakedetector.domain import AnalyzerResult, ImageTechnicalParameters, MediaType
from fakedetector.preprocessing._media_tools import (
    ImageTile,
    TileRegion,
    extract_image_tiles,
    finite_differences,
    high_pass_residual,
    periodic_hann,
    to_luminance,
)

_LIMITATION = (
    "Content, texture, ordinary filtering and compression can produce these differences. "
    "No camera identity, editing attribution, authenticity or probability is established. "
    "Sixteen fixed cores cover only part of the oriented raster."
)


def _image_applicability(request: AnalyzerRequest) -> ApplicabilityResult:
    if request.media_type is not MediaType.IMAGE:
        return ApplicabilityResult(False, "media_type")
    parameters = request.file_facts.technical_parameters
    assert isinstance(parameters, ImageTechnicalParameters)
    if (
        min(parameters.width, parameters.height) < 512
        or parameters.width * parameters.height > 2**22
    ):
        return ApplicabilityResult(False, "image_dimensions")
    artifacts = _artifacts(request, "normalized_image")
    if not artifacts:
        return ApplicabilityResult(False, "normalized_image_missing")
    if len(artifacts) != 1:
        raise ValueError("duplicate normalized image")
    with artifacts[0].content.open_for_read() as stream, Image.open(stream) as image:
        if image.format != "PNG" or image.mode not in ("RGB", "RGBA"):
            raise ValueError("unexpected normalized representation")
        if min(image.size) < 512 or image.width * image.height > 2**22:
            return ApplicabilityResult(False, "image_dimensions")
    return ApplicabilityResult(True)


def _tiles(request: AnalyzerRequest) -> tuple[tuple[ImageTile, ...], tuple[int, int]]:
    artifacts = _artifacts(request, "normalized_image")
    if len(artifacts) != 1:
        raise ValueError("one normalized artifact required")
    with artifacts[0].content.open_for_read() as stream, Image.open(stream) as image:
        width, height = image.size
        if (
            image.format != "PNG"
            or image.mode not in ("RGB", "RGBA")
            or min(width, height) < 512
            or width * height > 2**22
        ):
            raise ValueError("unsupported normalized raster")
        regions = tuple(
            TileRegion(2 + i * (width - 132) // 3, 2 + j * (height - 132) // 3, 128, 128)
            for j in range(4)
            for i in range(4)
        )
        return extract_image_tiles(np.asarray(image), regions, halo=2), (width, height)


@dataclass(frozen=True)
class _TileContext:
    index: int
    region: TileRegion
    brightness: float
    texture: float
    eligible: bool


def _peers(target: _TileContext, contexts: list[_TileContext]) -> list[int]:
    peers = [
        other
        for other in contexts
        if other.index != target.index
        and other.eligible
        and abs(target.brightness - other.brightness) <= 16
        and abs(math.log2((target.texture + 0.25) / (other.texture + 0.25))) <= 0.5
    ]
    peers.sort(
        key=lambda c: (
            (c.region.x - target.region.x) ** 2 + (c.region.y - target.region.y) ** 2,
            c.index,
        )
    )
    return [c.index for c in peers[:5]]


def _support(tile: ImageTile) -> NDArray[np.bool_]:
    rgb = tile.pixels[..., :3]
    mask = np.all((rgb > 4) & (rgb < 251), axis=2)
    if tile.pixels.shape[2] == 4:
        mask &= tile.pixels[..., 3] == 255
    return mask


def _coverage(context: _TileContext) -> dict[str, JsonValue]:
    return {
        "tile": context.index,
        "bbox_pixels": [context.region.x, context.region.y, 128, 128],
        "brightness": context.brightness,
        "texture": context.texture,
        "eligible": context.eligible,
    }


def _lag_covariance(
    residual: NDArray[np.float64], mask: NDArray[np.bool_], axis: int
) -> float | None:
    a, b = (residual[:, :-1], residual[:, 1:]) if axis == 0 else (residual[:-1], residual[1:])
    valid = (mask[:, :-1] & mask[:, 1:]) if axis == 0 else (mask[:-1] & mask[1:])
    if np.count_nonzero(valid) < 2:
        return None
    av, bv = a[valid], b[valid]
    av, bv = av - av.mean(), bv - bv.mean()
    denominator = float(np.sqrt(np.sum(av**2) * np.sum(bv**2)))
    return float(np.sum(av * bv) / denominator) if denominator > 1e-12 else None


class ImageNoiseResidualConsistencyAnalyzer:
    analyzer_id: ClassVar[str] = "image_noise_residual_consistency"
    analyzer_name: ClassVar[str] = "Image residual consistency (experimental weak)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "image"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.IMAGE})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _image_applicability(request)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        tiles, size = _tiles(request)
        contexts: list[_TileContext] = []
        scales: list[float | None] = []
        rows: list[JsonValue] = []
        for index, tile in enumerate(tiles):
            luminance = to_luminance(tile)
            gradients = finite_differences(luminance)
            g = np.maximum(np.abs(gradients.horizontal.values), np.abs(gradients.vertical.values))
            mask = np.lib.stride_tricks.sliding_window_view(_support(tile), (5, 5)).all(
                axis=(-1, -2)
            ) & (g <= 8)
            support = int(np.count_nonzero(mask))
            brightness, texture = (
                float(np.median(luminance.values[2:-2, 2:-2])),
                float(np.median(g)),
            )
            context = _TileContext(
                index,
                tile.region,
                brightness,
                texture,
                support >= 8192 and texture <= 12 and 16 <= brightness <= 239,
            )
            contexts.append(context)
            residual = high_pass_residual(luminance, kernel_size=5).values
            values = residual[mask]
            mad = float(np.median(np.abs(values - np.median(values)))) if support else None
            scales.append(mad)
            rows.append(
                {
                    **_coverage(context),
                    "support_pixels": support,
                    "mad": mad,
                    "variance": float(np.var(values)) if support else None,
                    "energy": float(np.mean(values**2)) if support else None,
                    "lag_x": _lag_covariance(residual, mask, 0),
                    "lag_y": _lag_covariance(residual, mask, 1),
                }
            )
        comparisons: list[JsonValue] = []
        maximum: float | None = None
        for context, scale in zip(contexts, scales, strict=True):
            peers = _peers(context, contexts)
            if not context.eligible or scale is None or len(peers) < 3:
                continue
            reference = float(np.median([scales[j] for j in peers]))
            value = abs(math.log2((scale + 0.25) / (reference + 0.25)))
            comparisons.append(
                {
                    "tile": context.index,
                    "peers": [int(peer) for peer in peers],
                    "reference_mad": reference,
                    "log2_ratio": value,
                }
            )
            maximum = value if maximum is None else max(maximum, value)
        return _measurement_result(
            self,
            request,
            "N-MAD-MATCH-1",
            {
                "state": "measured" if comparisons else "insufficient_evidence",
                "oriented_size": list(size),
                "core_pixels": 16 * 128 * 128,
                "tiles": rows,
                "comparisons": comparisons,
                "max_log2_ratio": maximum,
            },
            "Residual MAD is not isolated sensor noise. " + _LIMITATION,
        )


def _periodogram(
    vector: NDArray[np.float64],
) -> tuple[NDArray[np.float64] | None, NDArray[np.complex128]]:
    spectrum = np.fft.rfft(
        (vector - vector.mean()) * np.asarray(periodic_hann(128), dtype=np.float64)
    )
    power = np.abs(spectrum) ** 2
    total = float(power[1:].sum())
    return (power / total if total > 1e-12 else None), spectrum


@dataclass(frozen=True)
class _Direction:
    power: NDArray[np.float64] | None
    peak: int | None
    raw_peak: int | None
    veto: bool
    phase: float | None


def _direction(
    second: NDArray[np.float64], luminance: NDArray[np.float64], axis: int
) -> _Direction:
    # x projects over rows (axis=0); y projects over columns (axis=1).
    magnitude = np.abs(second)
    power, _ = _periodogram(magnitude.mean(axis=axis))
    if power is None:
        return _Direction(None, None, None, False, None)
    bins = [k for k in range(4, 65) if all(abs(k - 16 * m) > 2 for m in range(1, 5))]
    peak = max(bins, key=lambda k: float(power[k]))
    texture, _ = _periodogram(luminance.mean(axis=axis))
    veto = texture is not None and float(texture[peak - 1 : peak + 2].sum()) >= 0.1
    halves = np.split(magnitude, 2, axis=axis)
    _, first = _periodogram(halves[0].mean(axis=axis))
    _, second_spectrum = _periodogram(halves[1].mean(axis=axis))
    phase = (
        float(np.angle(first[peak] * np.conj(second_spectrum[peak])))
        if abs(first[peak]) and abs(second_spectrum[peak])
        else None
    )
    return _Direction(power, peak, int(np.argmax(power[1:])) + 1, veto, phase)


class ImageResamplingConsistencyAnalyzer:
    analyzer_id: ClassVar[str] = "image_resampling_consistency"
    analyzer_name: ClassVar[str] = "Image resampling consistency (experimental weak)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "image"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.IMAGE})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _image_applicability(request)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        tiles, size = _tiles(request)
        contexts: list[_TileContext] = []
        directions: list[tuple[_Direction, _Direction]] = []
        rows: list[JsonValue] = []
        for index, tile in enumerate(tiles):
            luminance = to_luminance(tile)
            y = luminance.values
            core = y[2:-2, 2:-2]
            gradients = finite_differences(luminance)
            g = np.maximum(np.abs(gradients.horizontal.values), np.abs(gradients.vertical.values))
            brightness, texture = float(np.median(core)), float(np.median(g))
            context = _TileContext(
                index,
                tile.region,
                brightness,
                texture,
                bool(_support(tile).all()) and 16 <= brightness <= 239,
            )
            contexts.append(context)
            x = _direction(y[2:-2, 1:-3] - 2 * core + y[2:-2, 3:-1], core, 0)
            vertical = _direction(y[1:-3, 2:-2] - 2 * core + y[3:-1, 2:-2], core, 1)
            directions.append((x, vertical))
            rows.append(_coverage(context))
        comparisons: list[JsonValue] = []
        maximum: float | None = None
        diagnostics: list[JsonValue] = []
        for context, axes in zip(contexts, directions, strict=True):
            for axis, direction in enumerate(axes):
                diagnostics.append(
                    {
                        "tile": context.index,
                        "axis": "xy"[axis],
                        "peak_bin": direction.peak,
                        "raw_peak_bin": direction.raw_peak,
                        "texture_veto": direction.veto,
                        "phase": direction.phase,
                    }
                )
                if (
                    not context.eligible
                    or direction.veto
                    or direction.power is None
                    or direction.peak is None
                ):
                    continue
                eligible = [c for c in contexts if directions[c.index][axis].power is not None]
                peers = _peers(context, eligible)
                if len(peers) < 3:
                    continue
                reference_values: list[float] = []
                for peer in peers:
                    power = directions[peer][axis].power
                    assert power is not None
                    reference_values.append(float(power[direction.peak]))
                reference = float(np.median(reference_values))
                peak_power = float(direction.power[direction.peak])
                value = max(0.0, math.log2((peak_power + 1e-12) / (reference + 1e-12)))
                comparisons.append(
                    {
                        "tile": context.index,
                        "axis": "xy"[axis],
                        "peak_bin": direction.peak,
                        "peers": [int(peer) for peer in peers],
                        "peak_power": peak_power,
                        "reference_power": reference,
                        "log2_ratio": value,
                    }
                )
                maximum = value if maximum is None else max(maximum, value)
        return _measurement_result(
            self,
            request,
            "R-D2-MATCH-1",
            {
                "state": "measured" if comparisons else "insufficient_evidence",
                "oriented_size": list(size),
                "core_pixels": 16 * 128 * 128,
                "tiles": rows,
                "directions": diagnostics,
                "comparisons": comparisons,
                "max_log2_ratio": maximum,
            },
            "Periodicity does not establish a resampling operation. " + _LIMITATION,
        )
