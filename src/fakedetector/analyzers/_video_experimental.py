"""Bounded dense-frame correspondence, visual transitions and measured PTS observations."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from statistics import median
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray
from pydantic import JsonValue

from fakedetector.analyzers._experimental_common import _distribution, _measurement_result
from fakedetector.analyzers._models import AnalyzerRequest, ApplicabilityResult
from fakedetector.domain import AnalyzerResult, MediaType
from fakedetector.preprocessing._models import (
    DenseVideoWindowDescriptor,
    StreamTimingFacts,
    TimingRecordsDescriptor,
)

_LIMITATION = (
    "Only retained dense frames and their same-decode PTS are observed. "
    "Static, periodic or ordinary edited content can produce these measurements. "
    "No fraud, authenticity, editing attribution or probability is established."
)


@dataclass(frozen=True)
class _DenseInput:
    pixels: DenseVideoWindowDescriptor
    timing: TimingRecordsDescriptor
    stream: StreamTimingFacts


def _dense_inputs(request: AnalyzerRequest) -> tuple[_DenseInput, ...]:
    manifest = request.forensic
    if manifest is None:
        raise ValueError("required dense manifest absent")
    streams = {
        r.facts.stream_index: r.facts
        for r in manifest.representations
        if isinstance(r.facts, StreamTimingFacts)
    }
    records = {
        r.facts.data.artifact_id: r.facts
        for r in manifest.representations
        if isinstance(r.facts, TimingRecordsDescriptor) and r.facts.data is not None
    }
    inputs = tuple(
        _DenseInput(
            r.facts,
            records[r.facts.timing_artifact_id],
            streams[records[r.facts.timing_artifact_id].stream_index],
        )
        for r in manifest.representations
        if isinstance(r.facts, DenseVideoWindowDescriptor)
    )
    if not inputs:
        raise ValueError("required dense pixels absent")
    return tuple(sorted(inputs, key=lambda w: (w.stream.stream_index, w.timing.region)))


def _video_applicability(request: AnalyzerRequest, *, grid: bool = True) -> ApplicabilityResult:
    if request.media_type is not MediaType.VIDEO:
        return ApplicabilityResult(False, "media_type")
    windows = _dense_inputs(request)
    if grid and all(w.pixels.pixels.shape[1] < 9 or w.pixels.pixels.shape[2] < 16 for w in windows):
        return ApplicabilityResult(False, "dense_geometry")
    return ApplicabilityResult(True)


def _block_descriptor(frame: NDArray[np.uint8]) -> NDArray[np.int64]:
    """P1 16x9 RGB block means, integer half-up rounding, all pixels included."""
    height, width = frame.shape[:2]
    if height < 9 or width < 16:
        raise ValueError("frame too small for descriptor")
    output = np.empty((9, 16, 3), dtype=np.int64)
    for row in range(9):
        for column in range(16):
            block = frame[
                row * height // 9 : (row + 1) * height // 9,
                column * width // 16 : (column + 1) * width // 16,
            ]
            area = block.shape[0] * block.shape[1]
            output[row, column] = (block.sum(axis=(0, 1), dtype=np.int64) + area // 2) // area
    return output.reshape(432)


def _timing(request: AnalyzerRequest, window: _DenseInput) -> NDArray[np.int64]:
    assert window.timing.data is not None
    return np.asarray(request.read_numeric(window.timing.data), dtype=np.int64)


def _ticks(rows: NDArray[np.int64], start: int, length: int) -> tuple[int, ...] | None:
    selected = rows[start : start + length]
    if not np.all(selected[:, 4] & 1):
        return None
    ticks = tuple(int(row[0]) for row in selected)
    if any(a >= b for a, b in zip(ticks, ticks[1:], strict=False)):
        return None
    return ticks


def _window_coverage(window: _DenseInput) -> dict[str, JsonValue]:
    return {
        "stream_index": window.stream.stream_index,
        "region": window.timing.region,
        "frame_count": window.timing.record_count,
        "time_base": [window.stream.time_base.numerator, window.stream.time_base.denominator],
        "first_tick": window.timing.first_tick,
        "last_tick": window.timing.last_tick,
        "requested_ticks": [window.timing.requested.start, window.timing.requested.stop],
        "coverage": window.timing.coverage,
        "stop_reason": window.timing.stop_reason,
    }


@dataclass(frozen=True)
class _Group:
    window: _DenseInput
    start: int
    ticks: tuple[int, ...]
    values: NDArray[np.int64]

    @property
    def first(self) -> Fraction:
        return self.window.stream.time_base.seconds(self.ticks[0])

    @property
    def last(self) -> Fraction:
        return self.window.stream.time_base.seconds(self.ticks[-1])

    def location(self) -> dict[str, JsonValue]:
        return {
            "region": self.window.timing.region,
            "start_ordinal": self.start,
            "pts_ticks": [int(tick) for tick in self.ticks],
        }


def _pair_order(first: _Group, second: _Group) -> tuple[_Group, _Group] | None:
    a, b = first.window, second.window
    if a.stream.stream_index != b.stream.stream_index or (
        a.pixels.native_width,
        a.pixels.native_height,
        a.pixels.pixels.shape[1:],
    ) != (b.pixels.native_width, b.pixels.native_height, b.pixels.pixels.shape[1:]):
        return None
    if a.timing.region == b.timing.region and abs(first.start - second.start) < 5:
        return None
    if first.last < second.first:
        return first, second
    if second.last < first.first:
        return second, first
    return None


def _distances(a: NDArray[np.int64], b: NDArray[np.int64]) -> tuple[int, int, int, int]:
    da, db = np.diff(a, axis=0), np.diff(b, axis=0)
    return (
        int(np.abs(a - b).sum()),
        int(np.abs(da - db).sum()),
        int(np.abs(da).sum()),
        int(np.abs(db).sum()),
    )


class VideoRepeatedContentCorrespondenceAnalyzer:
    analyzer_id: ClassVar[str] = "video_repeated_content_correspondence"
    analyzer_name: ClassVar[str] = "Video repeated-content correspondence (experimental weak)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "video"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.VIDEO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _video_applicability(request)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        groups: list[_Group] = []
        coverage: list[JsonValue] = []
        for window in _dense_inputs(request):
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
        colors: list[float | None] = []
        deltas: list[float | None] = []
        minima: list[tuple[int, dict[str, JsonValue]] | None] = [None, None]
        zero_pairs = dynamic_zero_pairs = eligible = 0
        for first, second in combinations(groups, 2):
            ordered = _pair_order(first, second)
            if ordered is None:
                continue
            a, b = ordered
            color, delta, ta, tb = _distances(a.values, b.values)
            eligible += 1
            colors.append(color / 440640)
            deltas.append(delta / 660960)
            zero_pairs += color == delta == 0
            dynamic_zero_pairs += color == delta == 0 and ta > 0 and tb > 0
            pair: dict[str, JsonValue] = {
                "stream_index": a.window.stream.stream_index,
                "a": a.location(),
                "b": b.location(),
                "color_numerator": color,
                "delta_numerator": delta,
                "temporal_a_numerator": ta,
                "temporal_b_numerator": tb,
            }
            for index, value in enumerate((color, delta)):
                previous = minima[index]
                if previous is None or value < previous[0]:
                    minima[index] = value, pair
        return _measurement_result(
            self,
            request,
            "VRC-DENSE-DIPLOMA-1",
            {
                "state": "measured" if eligible else "insufficient_evidence",
                "windows": coverage,
                "valid_groups": len(groups),
                "eligible_pairs": eligible,
                "excluded_pairs": len(groups) * (len(groups) - 1) // 2 - eligible,
                "zero_descriptor_pairs": zero_pairs,
                "dynamic_zero_descriptor_pairs": dynamic_zero_pairs,
                "color": _distribution(colors),
                "delta": _distribution(deltas),
                "minimum_color_pair": minima[0][1] if minima[0] else None,
                "minimum_delta_pair": minima[1][1] if minima[1] else None,
                "denominators": {"color": 440640, "delta": 660960, "temporal": 330480},
            },
            "Descriptor equality is not pixel equality or a copied-content verdict. " + _LIMITATION,
        )


class VideoVisualDiscontinuityAnalyzer:
    analyzer_id: ClassVar[str] = "video_visual_discontinuity"
    analyzer_name: ClassVar[str] = "Video visual transitions (experimental weak)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "video"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.VIDEO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _video_applicability(request)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        coverage: list[JsonValue] = []
        pairs = 0
        for window in _dense_inputs(request):
            row = _window_coverage(window)
            if window.pixels.pixels.shape[1] < 9 or window.pixels.pixels.shape[2] < 16:
                row["state"] = "unsupported_geometry"
                coverage.append(row)
                continue
            pixels = np.asarray(request.read_numeric(window.pixels.pixels), dtype=np.uint8)
            descriptors = np.stack([_block_descriptor(frame) for frame in pixels])
            del pixels
            timing = _timing(request, window)
            values: list[float | None] = []
            for index in range(len(descriptors) - 1):
                ticks = _ticks(timing, index, 2)
                value = (
                    float(np.abs(descriptors[index + 1] - descriptors[index]).sum() / (432 * 255))
                    if ticks
                    else None
                )
                values.append(value)
                pairs += value is not None
            summary = _distribution(values)
            peak = summary.pop("max_index")
            if isinstance(peak, int):
                summary["max_ordinals"] = [peak, peak + 1]
                summary["max_pts_ticks"] = [int(timing[peak, 0]), int(timing[peak + 1, 0])]
            row["transition"] = summary
            coverage.append(row)
        return _measurement_result(
            self,
            request,
            "VISUAL-DENSE-DIPLOMA-1",
            {
                "state": "measured" if pairs else "insufficient_evidence",
                "windows": coverage,
            },
            "Cuts, motion, flashes and lighting changes are not distinguished. " + _LIMITATION,
        )


class VideoTimingAnomalyAnalyzer:
    analyzer_id: ClassVar[str] = "video_timing_anomaly"
    analyzer_name: ClassVar[str] = "Video measured timing irregularity (experimental weak)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "video"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.VIDEO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _video_applicability(request, grid=False)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        coverage: list[JsonValue] = []
        pair_count = 0
        for window in _dense_inputs(request):
            timing = _timing(request, window)
            gaps: list[int] = []
            ordinals: list[int] = []
            for index in range(len(timing) - 1):
                if int(timing[index, 4]) & 1 and int(timing[index + 1, 4]) & 1:
                    gaps.append(int(timing[index + 1, 0]) - int(timing[index, 0]))
                    ordinals.append(index)
            positive = [value for value in gaps if value > 0]
            reference = median(positive) if positive else None
            deviations: list[float | None] = (
                [abs(value - reference) / (abs(value) + reference) for value in gaps]
                if reference is not None
                else [None] * len(gaps)
            )
            row = _window_coverage(window)
            summary = _distribution(deviations)
            peak = summary.pop("max_index")
            if isinstance(peak, int):
                index = ordinals[peak]
                summary["max_ordinals"] = [index, index + 1]
                summary["max_pts_ticks"] = [int(timing[index, 0]), int(timing[index + 1, 0])]
            row.update(
                {
                    "observed_pairs": len(gaps),
                    "missing_pts_frames": int(np.count_nonzero((timing[:, 4] & 1) == 0)),
                    "duplicate_pts_pairs": gaps.count(0),
                    "decreasing_pts_pairs": sum(value < 0 for value in gaps),
                    "positive_gap_median_ticks": reference,
                    "gap_deviation": summary,
                    "gap_ticks": [int(gap) for gap in gaps],
                }
            )
            pair_count += len(gaps)
            coverage.append(row)
        return _measurement_result(
            self,
            request,
            "TIMING-DENSE-DIPLOMA-1",
            {
                "state": "measured" if pair_count else "insufficient_evidence",
                "windows": coverage,
            },
            "Variable frame rate and decoder timing can explain irregular gaps; "
            "semantic A/V sync is not measured. "
            + _LIMITATION,
        )
