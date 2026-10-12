"""ARC-NCC-1 bounded retrieval and signed NCC, retaining frozen-v2 numeric guards."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray
from pydantic import JsonValue

from fakedetector.analyzers._audio_experimental import (
    _audio_applicability,
    _audio_inputs,
    _spectrum,
)
from fakedetector.analyzers._experimental_common import _measurement_result
from fakedetector.analyzers._models import AnalyzerRequest, ApplicabilityResult
from fakedetector.domain import AnalyzerResult, MediaType
from fakedetector.preprocessing._models import AudioWindowDescriptor

_EPS = 2.0**-52


def _centered(values: NDArray[np.generic]) -> tuple[NDArray[np.float64], float] | None:
    x = np.asarray(values, dtype=np.float64)
    scale = float(np.max(np.abs(x)))
    if not scale:
        return None
    x = x / scale
    x -= x.mean()
    variance = float(np.sum(x * x))
    if not math.isfinite(variance):
        raise ValueError("nonfinite centered variance")
    return (x, variance) if variance > 64 * _EPS * len(x) else None


def _checked(values: NDArray[np.float64]) -> NDArray[np.float64]:
    if not np.isfinite(values).all() or np.any(np.abs(values) > 1 + 64 * _EPS):
        raise ValueError("NCC exceeds numeric guard")
    return np.clip(values, -1, 1)


def _support(x: NDArray[np.generic], y: NDArray[np.generic]) -> float | None:
    a, b = _centered(x), _centered(y)
    if a is None or b is None:
        return None
    value = float(np.sum(a[0] * b[0]) / np.sqrt(a[1] * b[1]))
    return float(_checked(np.asarray(value)))


def _compensated_prefix(values: NDArray[np.float64]) -> NDArray[np.float64]:
    # Frozen-v2 correction: ordinary cumsum loses the 64-eps NCC guard on tones.
    output = np.empty(len(values) + 1, dtype=np.float64)
    output[0] = total = correction = 0.0
    for index, value in enumerate(values.tolist(), 1):
        adjusted = value - correction
        updated = total + adjusted
        correction = (updated - total) - adjusted
        output[index] = total = updated
    return output


def _lag_ncc(x: NDArray[np.generic], search: NDArray[np.generic]) -> NDArray[np.float64]:
    length = len(x)
    if not 8192 <= length <= 48128 or not length <= len(search) <= length + 8192:
        raise ValueError("NCC search exceeds bounded profile")
    output = np.full(len(search) - length + 1, np.nan)
    centered = _centered(x)
    y = np.asarray(search, dtype=np.float64)
    scale = float(np.max(np.abs(y)))
    if centered is None or not scale:
        return output
    u, vx = centered
    y = y / scale
    fft_length = 1 << (2 * length + 8192 - 2).bit_length()
    convolution = np.fft.irfft(
        np.fft.rfft(u[::-1], fft_length) * np.fft.rfft(y, fft_length), fft_length
    )[length - 1 : len(y)]
    sums, squares = _compensated_prefix(y), _compensated_prefix(y * y)
    sums = sums[length:] - sums[:-length]
    variance = squares[length:] - squares[:-length] - sums * sums / length
    floor = 64 * _EPS * length
    if not np.isfinite(variance).all() or np.any(variance < -floor):
        raise ValueError("invalid NCC prefix variance")
    valid = variance > floor
    numerator = convolution - sums * (float(np.sum(u)) / length)
    output[valid] = _checked(numerator[valid] / np.sqrt(vx * variance[valid]))
    return output


def _best(values: NDArray[np.float64], deltas: NDArray[np.int64]) -> int | None:
    valid = np.flatnonzero(np.isfinite(values))
    return (
        int(min(valid, key=lambda i: (-float(values[i]), abs(int(deltas[i])), int(deltas[i]))))
        if len(valid)
        else None
    )


@dataclass(frozen=True)
class _Seed:
    window: int
    local: int
    absolute: int


def _descriptor(
    spectra: NDArray[np.float64], start: int, length: int, channel: int
) -> NDArray[np.float64] | None:
    frames = spectra[start // 1024 : (start + length - 4096) // 1024 + 1, channel]
    if len(frames) < 4:
        return None
    scale = float(frames.max())
    if not scale:
        return None
    bands = (frames[:, 1:] / scale).reshape(len(frames), 16, 128).sum(axis=2)
    vector = np.concatenate(
        [bands[t * len(frames) // 4 : (t + 1) * len(frames) // 4].mean(axis=0) for t in range(4)]
    )
    norm = float(np.sqrt(np.sum(vector**2)))
    return vector / norm if norm else None


def _retrieve(
    seeds: list[_Seed],
    descriptors: list[list[NDArray[np.float64] | None]],
    length: int,
    channels: int,
) -> tuple[list[tuple[float, int, int]], int]:
    top: list[list[list[tuple[float, int, int]]]] = [[[] for _ in range(channels)] for _ in seeds]
    for i, first in enumerate(seeds):
        for j in range(i + 1, len(seeds)):
            if seeds[j].absolute - first.absolute < 2 * length:
                continue
            for channel in range(channels):
                a, b = descriptors[i][channel], descriptors[j][channel]
                if a is None or b is None:
                    continue
                distance = float(np.sum((a - b) ** 2))
                for origin, target in ((i, j), (j, i)):
                    items = top[origin][channel]
                    items.append((distance, seeds[target].absolute, target))
                    items.sort()
                    del items[4:]
    nominations: set[tuple[int, int]] = set()
    for i, rows in enumerate(top):
        for items in rows:
            for _, _, j in items:
                nominations.add((min(i, j), max(i, j)))
    pairs = []
    for i, j in nominations:
        distances = []
        for a, b in zip(descriptors[i], descriptors[j], strict=True):
            if a is not None and b is not None:
                distances.append(float(np.sum((a - b) ** 2)))
        pairs.append((min(distances), i, j))
    pairs.sort()
    return pairs[:64], len(pairs)


def _measure_pair(
    request: AnalyzerRequest,
    windows: tuple[AudioWindowDescriptor, ...],
    a: _Seed,
    b: _Seed,
    length: int,
    channels: int,
) -> dict[str, JsonValue]:
    wa, wb = windows[a.window], windows[b.window]
    xa = request.read_numeric(wa.data)
    yb = xa if a.window == b.window else request.read_numeric(wb.data)
    low = max(-4096, -b.local, a.absolute + 2 * length - b.absolute)
    high = min(4096, wb.samples.count - b.local - 2 * length)
    row: dict[str, JsonValue] = {"a_seed": a.absolute, "b_seed": b.absolute}
    if low > high:
        return {**row, "state": "insufficient_support"}
    deltas = np.arange(low, high + 1, dtype=np.int64)
    rhos = np.stack(
        [
            _lag_ncc(
                xa[a.local : a.local + length, c], yb[b.local + low : b.local + high + length, c]
            )
            for c in range(channels)
        ]
    )
    valid = np.isfinite(rhos)
    counts = valid.sum(axis=0)
    means = np.full(len(deltas), np.nan)
    selected = counts > 0
    means[selected] = np.where(valid, rhos, 0).sum(axis=0)[selected] / counts[selected]
    best = _best(means, deltas)
    own = [_best(values, deltas) for values in rhos]
    best_deltas = [None if index is None else int(deltas[index]) for index in own]
    row["channel_best_deltas"] = list(best_deltas)
    row["channel_offset_disagreement"] = len({v for v in best_deltas if v is not None}) > 1
    if best is None:
        return {**row, "state": "insufficient_evidence", "delta": None}
    delta = int(deltas[best])
    bb = b.local + delta
    channel_rows: list[JsonValue] = []
    for channel in range(channels):
        supports = [
            _support(
                xa[
                    a.local + length + h * length // 2 : a.local + length + (h + 1) * length // 2,
                    channel,
                ],
                yb[bb + length + h * length // 2 : bb + length + (h + 1) * length // 2, channel],
            )
            for h in range(2)
        ]
        first = float(rhos[channel, best]) if valid[channel, best] else None
        channel_rows.append(
            {
                "channel": channel,
                "rho": first,
                "support_rhos": list(supports),
                "structural_support": first is not None and all(v is not None for v in supports),
                "exact_decoded": bool(
                    np.array_equal(
                        xa[a.local : a.local + 2 * length, channel],
                        yb[bb : bb + 2 * length, channel],
                    )
                ),
            }
        )
    row.update(
        {
            "state": "measured",
            "delta": delta,
            "a_interval": [a.absolute, a.absolute + 2 * length],
            "b_interval": [b.absolute + delta, b.absolute + delta + 2 * length],
            "a_source_pts": [
                wa.first_sample_pts + a.local,
                wa.first_sample_pts + a.local + 2 * length,
            ]
            if wa.first_sample_pts is not None
            else None,
            "b_source_pts": [wb.first_sample_pts + bb, wb.first_sample_pts + bb + 2 * length]
            if wb.first_sample_pts is not None
            else None,
            "mean_selection_rho": float(means[best]),
            "equal_best_lag_count": int(np.count_nonzero(means == means[best])),
            "channels": channel_rows,
        }
    )
    return row


class AudioRepeatedSegmentCorrespondenceAnalyzer:
    analyzer_id: ClassVar[str] = "audio_repeated_segment_correspondence"
    analyzer_name: ClassVar[str] = "Audio repeated-segment correspondence (experimental)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "audio"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.AUDIO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        result = _audio_applicability(request, spectral=True)
        if result.applicable:
            _, windows = _audio_inputs(request)
            if any(
                (s := _spectrum(request, w)) is not None and s.frames.start != 0 for w in windows
            ):
                return ApplicabilityResult(False, "spectral_origin")
        return result

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        precision, windows = _audio_inputs(request)
        length = 1024 * ((precision.sample_rate + 1023) // 1024)
        seeds = [
            _Seed(i, local, window.samples.start + local)
            for i, window in enumerate(windows)
            for local in range(0, window.samples.count - 2 * length + 1, 4096)
        ]
        before_cap = len(seeds)
        if len(seeds) > 256:
            seeds = [seeds[i * (len(seeds) - 1) // 255] for i in range(256)]
        descriptors: list[list[NDArray[np.float64] | None]] = [
            [None] * precision.channels for _ in seeds
        ]
        for index, window in enumerate(windows):
            descriptor = _spectrum(request, window)
            if descriptor is None:
                continue
            spectra = np.asarray(request.read_numeric(descriptor.data), dtype=np.float64)
            if np.any(spectra < 0):
                raise ValueError("negative magnitude")
            for i, seed in enumerate(seeds):
                if seed.window == index:
                    descriptors[i] = [
                        _descriptor(spectra, seed.local, length, c)
                        for c in range(precision.channels)
                    ]
            del spectra
        pairs, union_count = _retrieve(seeds, descriptors, length, precision.channels)
        del descriptors
        rows: list[JsonValue] = []
        for distance, first, second in pairs:
            row = _measure_pair(
                request, windows, seeds[first], seeds[second], length, precision.channels
            )
            row["descriptor_distance"] = distance
            rows.append(row)
        return _measurement_result(
            self,
            request,
            "ARC-NCC-1",
            {
                "state": "measured"
                if any(isinstance(r, dict) and r["state"] == "measured" for r in rows)
                else "insufficient_evidence",
                "sample_rate": precision.sample_rate,
                "stream_index": precision.stream_index,
                "length_samples": length,
                "seeds_before_cap": before_cap,
                "seeds_retained": len(seeds),
                "candidate_union_count": union_count,
                "candidate_cap_hit": union_count > 64,
                "pairs": rows,
                "observed_windows": [
                    {
                        "samples": [w.samples.start, w.samples.stop],
                        "first_sample_pts": w.first_sample_pts,
                    }
                    for w in windows
                ],
            },
            "Repeated waveform correspondence also occurs in legitimate loops, tones "
            "and background. "
            "Retrieval caps can lose speech copies; source/foreground attribution is unresolved. "
            "No authenticity conclusion or probability is supported.",
        )
