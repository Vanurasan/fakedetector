"""M2-R2 arithmetic for the proposed METHODS profiles, without forensic decisions."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from fakedetector.analyzers._models import AnalyzerRequest
from fakedetector.preprocessing._media_tools import (
    TileRegion,
    extract_image_tiles,
    to_luminance,
)
from fakedetector.preprocessing._models import JpegCoefficientsDescriptor, OriginalImageFacts
from fakedetector.preprocessing._requirements import ForensicResourcePolicy

MODES = tuple((u, v) for u in range(4) for v in range(4) if 1 <= u + v <= 3)


@dataclass(frozen=True)
class HistogramMeasurement:
    n: int
    minimum: int | None = None
    maximum: int | None = None
    span: int | None = None
    occupied: int | None = None
    zero_fraction: float | None = None
    empty_fraction: float | None = None
    frequency: float | None = None
    amplitude: float | None = None
    state: str = "no_full_blocks"


def histogram(values: NDArray[np.generic]) -> HistogramMeasurement:
    """Signed counts with Python-integer range checks before dense allocation."""
    if values.dtype != np.dtype("<i4"):
        raise ValueError("expected native int32 coefficients")
    n = values.size
    if not n:
        return HistogramMeasurement(n=0)
    low, high = int(values.min()), int(values.max())
    span = high - low + 1
    if span > 65536:
        return HistogramMeasurement(n, low, high, span, state="histogram_limit")
    counts = np.bincount(values.ravel().astype(np.int64) - low, minlength=span)
    occupied = int(np.count_nonzero(counts))
    zero = int(counts[-low]) if low <= 0 <= high else 0
    frequency = amplitude = None
    if span > 1:
        length = 1 << (span - 1).bit_length()
        spectrum = np.abs(np.fft.rfft(counts / n, n=length, norm="backward"))
        peak = int(np.argmax(spectrum[1:])) + 1
        frequency, amplitude = peak / length, float(spectrum[peak])
    return HistogramMeasurement(
        n,
        low,
        high,
        span,
        occupied,
        zero / n,
        (span - occupied) / span,
        frequency,
        amplitude,
        "constant" if span == 1 else "measured",
    )


@dataclass(frozen=True)
class DQMeasurement:
    component: int
    u: int
    v: int
    q2: int
    excluded_blocks: int
    histogram: HistogramMeasurement


def measure_dq(request: AnalyzerRequest) -> tuple[DQMeasurement, ...]:
    manifest = request.forensic
    if manifest is None:
        raise ValueError("required manifest absent")
    original = next(
        r.facts for r in manifest.representations if isinstance(r.facts, OriginalImageFacts)
    )
    if original.jpeg is None:
        return ()
    descriptor = next(
        r.facts for r in manifest.representations if isinstance(r.facts, JpegCoefficientsDescriptor)
    )
    if original.jpeg != descriptor.header or descriptor.decode_quality != "clean":
        raise ValueError("inconsistent JPEG identity")
    header = descriptor.header
    max_h = max(c.horizontal_sampling for c in header.components)
    max_v = max(c.vertical_sampling for c in header.components)
    tables = {t.table_id: t.values for t in original.quantization_tables}
    results = []
    for component, plane in zip(header.components, descriptor.planes, strict=True):
        coefficients = request.read_numeric(plane)
        width = header.width * component.horizontal_sampling // (8 * max_h)
        height = header.height * component.vertical_sampling // (8 * max_v)
        excluded = plane.shape[0] * plane.shape[1] - width * height
        for u, v in MODES:
            results.append(
                DQMeasurement(
                    component.component_id,
                    u,
                    v,
                    tables[component.quantization_table_id][8 * u + v],
                    excluded,
                    histogram(coefficients[:height, :width, u, v]),
                )
            )
        del coefficients
    return tuple(results)


def ideal_requantize(t: int, q1: int, q2: int) -> int:
    """Exact rational R+ arithmetic, explanatory only; never estimates q1."""
    if q1 <= 0 or q2 <= 0:
        raise ValueError("positive quantization required")
    first = (2 * t + q1) // (2 * q1)
    return (2 * q1 * first + q2) // (2 * q2)


def ideal_bin_count(k: int, q1: int, q2: int) -> int:
    if q1 <= 0 or q2 <= 0:
        raise ValueError("positive quantization required")
    # ceil(a/b) == -((-a)//b), also for negative a.
    return -(-(2 * k + 1) * q2 // (2 * q1)) + (-(2 * k - 1) * q2 // (2 * q1))


def windows(width: int, height: int) -> tuple[TileRegion, ...]:
    ForensicResourcePolicy().check_raster(width, height)
    available_x, available_y = width - 3, height - 3
    w, h = (8 * (min(512, side) // 8) for side in (available_x, available_y))
    if min(w, h) < 64:
        return ()
    xs = sorted({1 + i * (available_x - w) // 3 for i in range(4)})
    ys = sorted({1 + i * (available_y - h) // 3 for i in range(4)})
    return tuple(TileRegion(x=x, y=y, width=w, height=h) for y in ys for x in xs)


def rectangle_count(side: int) -> int:
    count = side // 8
    return count * (side + 1) - 4 * count * (count + 1)


def log_tail(eta: int, kappa: int, p: float) -> float:
    """Full binomial tail in natural log space, fixed-order fsum, no cutoff."""
    if not 0 <= p <= 1 or not 0 <= kappa <= eta:
        raise ValueError("invalid binomial arguments")
    if p == 0 and kappa > 0:
        raise ValueError("impossible positive count at p=0")
    if kappa == 0 or p == 1:
        return 0.0
    log_p, log_q = math.log(p), math.log1p(-p)
    term = (
        math.lgamma(eta + 1)
        - math.lgamma(kappa + 1)
        - math.lgamma(eta - kappa + 1)
        + kappa * log_p
        + (eta - kappa) * log_q
    )
    terms = [term]
    for j in range(kappa, eta):
        term += math.log(eta - j) - math.log(j + 1) + log_p - log_q
        terms.append(term)
    largest = max(terms)
    return largest + math.log(math.fsum(math.exp(t - largest) for t in terms))


@dataclass(frozen=True)
class AxisMeasurement:
    counts: tuple[int, ...]
    n: int
    m: int
    fractions: tuple[float, ...] | None
    maximum_fraction: float | None
    boundary_phase: int | None
    block_phase: int | None
    ell: float | None


def axis_measurement(counts: tuple[int, ...], area: int, nt: int) -> AxisMeasurement:
    if len(counts) != 8 or min(counts) < 0 or area % 16 or sum(counts) > area:
        raise ValueError("invalid vote support")
    n, m = sum(counts), max(counts)
    phase = counts.index(m) if counts.count(m) == 1 else None
    ell = None
    if n:
        ell = math.log10(nt) + log_tail(area // 16, (m + 1) // 2, n / area) / math.log(10)
    return AxisMeasurement(
        counts,
        n,
        m,
        tuple(c / n for c in counts) if n else None,
        m / n if n else None,
        phase,
        (phase + 1) % 8 if phase is not None else None,
        ell,
    )


@dataclass(frozen=True)
class GridWindow:
    centers: tuple[int, int, int, int]
    support: tuple[int, int, int, int]
    area: int
    x: AxisMeasurement
    y: AxisMeasurement
    flag: bool


def grid_window(luminance: NDArray[np.float64], region: TileRegion, nt: int) -> GridWindow:
    """Luminance is precisely the source support (h+3,w+3), without padding."""
    h, w = region.height, region.width
    if luminance.shape != (h + 3, w + 3) or not np.isfinite(luminance).all():
        raise ValueError("invalid window support")
    cross = np.abs(
        luminance[:-1, :-1] + luminance[1:, 1:] - luminance[:-1, 1:] - luminance[1:, :-1]
    )
    center = cross[1 : h + 1, 1 : w + 1]
    votes_x = (center > cross[1 : h + 1, :w]) & (center > cross[1 : h + 1, 2 : w + 2])
    votes_y = (center > cross[:h, 1 : w + 1]) & (center > cross[2 : h + 2, 1 : w + 1])
    cx = tuple(int(votes_x[:, (phase - region.x) % 8 :: 8].sum()) for phase in range(8))
    cy = tuple(int(votes_y[(phase - region.y) % 8 :: 8, :].sum()) for phase in range(8))
    x, y = axis_measurement(cx, w * h, nt), axis_measurement(cy, w * h, nt)
    flag = (
        x.block_phase is not None
        and y.block_phase is not None
        and x.ell is not None
        and y.ell is not None
        and x.ell < 0
        and y.ell < 0
    )
    return GridWindow(
        (region.x, region.y, region.x + w, region.y + h),
        (region.x - 1, region.y - 1, region.x + w + 2, region.y + h + 2),
        w * h,
        x,
        y,
        flag,
    )


def native_raster(raster: NDArray[np.uint8], orientation: int) -> NDArray[np.uint8]:
    """Inverse EXIF permutation, preserving native pixels without interpolation."""
    if orientation == 1:
        return raster
    if orientation == 2:
        return raster[:, ::-1]
    if orientation == 3:
        return raster[::-1, ::-1]
    if orientation == 4:
        return raster[::-1]
    if orientation == 5:
        return raster.swapaxes(0, 1)
    if orientation == 6:
        return np.rot90(raster, 1)
    if orientation == 7:
        return raster.swapaxes(0, 1)[::-1, ::-1]
    if orientation == 8:
        return np.rot90(raster, -1)
    raise ValueError("unknown orientation")


def measure_grid(
    raster: NDArray[np.uint8],
    *,
    check_time: Callable[[], float],
) -> tuple[GridWindow, ...]:
    h, w = raster.shape[:2]
    regions = windows(w, h)
    nt = 16 * rectangle_count(w - 3) * rectangle_count(h - 3)
    results = []
    for region in regions:
        check_time()
        tile = extract_image_tiles(raster, (region,), halo=2)[0]
        # Halo index 0 is outside the mathematical support; never use its reflection.
        luminance = to_luminance(tile).values[1:, 1:]
        results.append(grid_window(luminance, region, nt))
        del tile, luminance
    check_time()
    return tuple(results)
