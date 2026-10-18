"""Worker-only frozen D2/I25/K9/R10 prototype; no runtime/ensemble registration."""

from __future__ import annotations

import math
from itertools import combinations
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray
from pydantic import JsonValue

from fakedetector.analyzers._experimental_common import _measurement_result
from fakedetector.analyzers._models import AnalyzerRequest, ApplicabilityResult
from fakedetector.analyzers._video_experimental import (
    _block_descriptor,
    _dense_inputs,
    _Group,
    _ticks,
    _timing,
    _video_applicability,
    _window_coverage,
)
from fakedetector.domain import AnalyzerResult, MediaType

_PROFILE = "VRC2-D2-I25-K9-R10-PROTOTYPE-1"
_K = 9
_EPSILON = 1e-12
_MAX_GROUPS = 3 * (32 - 3)


def _quantile(values: list[float], p: float) -> float | None:
    """PR #75 linear interpolation, preserving its arithmetic order exactly."""
    if any(not math.isfinite(v) for v in values):
        raise ValueError("nonfinite distance or energy")
    if not values:
        return None
    ordered = sorted(values)
    at = (len(ordered) - 1) * p
    left, right = math.floor(at), math.ceil(at)
    return ordered[left] + (at - left) * (ordered[right] - ordered[left])


def _descriptor_and_energy(values: NDArray[np.int64]) -> tuple[NDArray[np.float64], float]:
    grid = values.astype(np.float64).reshape(4, 9, 16, 3)
    centered = grid - grid.mean(axis=(1, 2), keepdims=True)
    spatial = np.concatenate((np.diff(grid, axis=2).ravel(), np.diff(grid, axis=1).ravel()))
    return spatial, float(np.abs(np.diff(centered, axis=0).ravel()).mean())


def _key(group: _Group) -> tuple[int, int, int]:
    return group.window.stream.stream_index, group.window.timing.region, group.start


def _distant_pairs(groups: list[_Group]) -> list[tuple[int, int]]:
    pairs = []
    for i, j in combinations(range(len(groups)), 2):
        a, b = groups[i], groups[j]
        wa, wb = a.window, b.window
        if wa.stream.stream_index != wb.stream.stream_index or (
            wa.pixels.native_width,
            wa.pixels.native_height,
            wa.pixels.pixels.shape[1:],
        ) != (wb.pixels.native_width, wb.pixels.native_height, wb.pixels.pixels.shape[1:]):
            continue
        if b.first - a.last >= 2:
            pairs.append((i, j))
        elif a.first - b.last >= 2:
            pairs.append((j, i))
    return pairs


def _contiguous_support(groups: list[_Group], keep: NDArray[np.bool_]) -> list[JsonValue]:
    result: list[JsonValue] = []
    for stream, region in sorted({_key(g)[:2] for g in groups}):
        starts = [
            g.start for i, g in enumerate(groups) if _key(g)[:2] == (stream, region) and keep[i]
        ]
        lengths: list[JsonValue] = []
        previous = -2
        length = 0
        for start in starts:
            if start != previous + 1:
                if length:
                    lengths.append(length)
                length = 0
            length += 1
            previous = start
        if length:
            lengths.append(length)
        result.append(
            {"stream_index": stream, "region": region, "contiguous_eligible_start_lengths": lengths}
        )
    return result


def _best_run_details(
    groups: list[_Group],
    run: list[tuple[int, int]],
    distances: NDArray[np.float64],
    energies: NDArray[np.float64],
    distance: float,
) -> dict[str, JsonValue]:
    constituents: list[JsonValue] = []
    for i, j in run:
        a, b = groups[i], groups[j]
        constituents.append(
            {
                "a": {
                    **a.location(),
                    "time_base": [
                        a.window.stream.time_base.numerator,
                        a.window.stream.time_base.denominator,
                    ],
                },
                "b": {
                    **b.location(),
                    "time_base": [
                        b.window.stream.time_base.numerator,
                        b.window.stream.time_base.denominator,
                    ],
                },
                "gap_fraction": str(b.first - a.last),
                "gap_seconds": float(b.first - a.last),
                "lag_fraction": str(b.first - a.first),
                "lag_seconds": float(b.first - a.first),
                "distance": float(distances[i, j]),
                "energy_a": float(energies[i]),
                "energy_b": float(energies[j]),
            }
        )
    a, b = (groups[index] for index in run[0])
    return {
        "stream_index": a.window.stream.stream_index,
        "region_a": a.window.timing.region,
        "region_b": b.window.timing.region,
        "start_ordinal_a": a.start,
        "start_ordinal_b": b.start,
        "run_median_distance": distance,
        "constituents": constituents,
    }


def _measure_groups(groups: list[_Group]) -> dict[str, JsonValue]:
    """Bounded group math; retain scalar population and the first minimum run only."""
    if len(groups) > _MAX_GROUPS:
        raise ValueError("dense group budget exceeded")
    lookup = {_key(g): i for i, g in enumerate(groups)}
    if len(lookup) != len(groups):
        raise ValueError("duplicate group identity")
    descriptors = [_descriptor_and_energy(g.values) for g in groups]
    energies = np.array([energy for _, energy in descriptors], dtype=np.float64)
    p25 = _quantile(energies.tolist(), 0.25)
    keep = energies > (p25 or 0)
    distances = np.zeros((len(groups), len(groups)), dtype=np.float64)
    if groups:
        vectors = np.stack([vector for vector, _ in descriptors])
        for i, vector in enumerate(vectors):
            distances[i] = np.abs(vectors - vector).mean(axis=1)
    pairs = _distant_pairs(groups)
    eligible = {(a, b) for a, b in pairs if keep[a] and keep[b]}
    population: list[float] = []
    best_run: list[tuple[int, int]] | None = None
    best_distance: float | None = None
    maximum_support = 0
    for a, b in pairs:
        ka, kb = _key(groups[a]), _key(groups[b])
        aligned: list[tuple[int, int]] = []
        for offset in range(29):
            i = lookup.get((ka[0], ka[1], ka[2] + offset), -1)
            j = lookup.get((kb[0], kb[1], kb[2] + offset), -1)
            if (i, j) not in eligible:
                break
            aligned.append((i, j))
        maximum_support = max(maximum_support, len(aligned))
        if len(aligned) < _K:
            continue
        run = aligned[:_K]
        value = float(np.median([distances[i, j] for i, j in run]))
        population.append(value)
        if best_distance is None or value < best_distance:
            best_distance, best_run = value, run
    p10 = _quantile(population, 0.1)
    score = None
    if not groups:
        state = "INSUFFICIENT_RUN_SUPPORT"
    elif not keep.any():
        state = "INSUFFICIENT_LOW_INFORMATION"
    elif p10 is None:
        state = "INSUFFICIENT_RUN_SUPPORT"
    elif p10 <= _EPSILON:
        state = "INSUFFICIENT_NONSELECTIVE_DISTRIBUTION"
    else:
        assert best_distance is not None
        score = min(1.0, max(0.0, 1 - best_distance / p10))
        state = "MEASURED"
    return {
        "state": state,
        "valid_group_count": len(groups),
        "eligible_group_count": int(keep.sum()),
        "eligible_run_count": len(population),
        "energy_p25": p25,
        "descriptor": "D2_SPATIAL_GRADIENT",
        "information_policy": "I25_DYNAMIC",
        "run_length": _K,
        "minimum_gap_seconds": 2.0,
        "relative_policy": "R10_TAIL_DISTINCTIVENESS",
        "d_best": best_distance,
        "p10_distance": p10,
        "median_distance": _quantile(population, 0.5),
        "relative_distinctiveness": score,
        "best_run": _best_run_details(groups, best_run, distances, energies, best_distance)
        if best_run is not None and best_distance is not None
        else None,
        "run_support": {
            "sequences": _contiguous_support(groups, keep),
            "maximum_aligned_run_support": maximum_support,
            "temporal_gap_eligible_pair_count": len(pairs),
            "informative_temporal_gap_pair_count": len(eligible),
        },
    }


class VideoRepeatedContentCorrespondenceV2PrototypeAnalyzer:
    analyzer_id: ClassVar[str] = "video_repeated_content_correspondence_v2_prototype"
    analyzer_name: ClassVar[str] = "Video repeated-content correspondence V2 (prototype)"
    analyzer_version: ClassVar[str] = "0.1.0"
    group: ClassVar[str] = "video"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.VIDEO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _video_applicability(request)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        windows = _dense_inputs(request)
        if len(windows) > 3:
            raise ValueError("dense region budget exceeded")
        groups: list[_Group] = []
        coverage: list[JsonValue] = []
        for window in windows:
            row = _window_coverage(window)
            if window.pixels.pixels.shape[1] < 9 or window.pixels.pixels.shape[2] < 16:
                row["state"] = "unsupported_geometry"
                coverage.append(row)
                continue
            pixels = np.asarray(request.read_numeric(window.pixels.pixels), dtype=np.uint8)
            descriptors = np.stack([_block_descriptor(frame) for frame in pixels])
            del pixels
            timing = _timing(request, window)
            undefined: list[JsonValue] = []
            for start in range(max(0, len(descriptors) - 3)):
                ticks = _ticks(timing, start, 4)
                if ticks is None:
                    undefined.append(start)
                else:
                    groups.append(_Group(window, start, ticks, descriptors[start : start + 4]))
            row["undefined_group_starts"] = undefined
            coverage.append(row)
        return _measurement_result(
            self,
            request,
            _PROFILE,
            {"coverage": coverage, **_measure_groups(groups)},
            "Worker-only prototype; no ensemble contribution. Relative distinctiveness is not "
            "probability or authenticity evidence. Static, periodic and ordinary edited content "
            "can repeat; missing run support is not evidence of absence. Only retained frames "
            "are observed; median run support does not locate exact episode boundaries.",
        )
