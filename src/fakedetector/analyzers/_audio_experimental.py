"""ATD-LOCAL-1, ASC-TV-1 and ABN-FLOOR-1 without forensic thresholds."""

from __future__ import annotations

import math
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray
from pydantic import JsonValue

from fakedetector.analyzers._experimental_common import _distribution, _measurement_result
from fakedetector.analyzers._models import AnalyzerRequest, ApplicabilityResult
from fakedetector.domain import AnalyzerResult, MediaType
from fakedetector.preprocessing._media_tools import frame_audio
from fakedetector.preprocessing._models import (
    AudioPrecisionFacts,
    AudioWindowDescriptor,
    SpectralWindowDescriptor,
)

_LIMITATION = (
    "Natural transients, speech, music and ordinary processing can produce these responses. "
    "No editing attribution, authenticity conclusion or probability is supported. "
    "Only retained windows are measured; gaps are not joined."
)


def _audio_inputs(
    request: AnalyzerRequest,
) -> tuple[AudioPrecisionFacts, tuple[AudioWindowDescriptor, ...]]:
    manifest = request.forensic
    if manifest is None:
        raise ValueError("required audio manifest absent")
    precisions = [r for r in manifest.representations if isinstance(r.facts, AudioPrecisionFacts)]
    if len(precisions) != 1:
        raise ValueError("expected one audio precision stream")
    precision = precisions[0]
    if (
        precision.provenance.producer,
        precision.provenance.producer_version,
        precision.provenance.profile,
        precision.provenance.profile_version,
    ) != ("ffmpeg_audio", "1", "precision_windows", "1"):
        raise ValueError("unexpected audio precision provenance")
    assert isinstance(precision.facts, AudioPrecisionFacts)
    windows = tuple(
        sorted(
            (
                r.facts
                for r in manifest.representations
                if isinstance(r.facts, AudioWindowDescriptor)
            ),
            key=lambda w: (w.stream_index, w.samples.start),
        )
    )
    if not windows or any(
        a.samples.stop > b.samples.start for a, b in zip(windows, windows[1:], strict=False)
    ):
        raise ValueError("missing or overlapping audio support")
    if any(w.samples.count > precision.facts.sample_rate * 10 for w in windows):
        raise ValueError("audio window exceeds ten-second profile")
    return precision.facts, windows


def _audio_applicability(
    request: AnalyzerRequest, *, spectral: bool = False
) -> ApplicabilityResult:
    if request.media_type is not MediaType.AUDIO:
        return ApplicabilityResult(False, "media_type")
    precision, windows = _audio_inputs(request)
    if not 8000 <= precision.sample_rate <= 48000 or precision.channels not in (1, 2):
        return ApplicabilityResult(False, "audio_profile")
    if spectral:
        for window in windows:
            descriptor = _spectrum(request, window)
            if descriptor is not None and (
                descriptor.n_fft,
                descriptor.hop,
                descriptor.window,
                descriptor.scaling,
            ) != (4096, 1024, "hann", "magnitude"):
                return ApplicabilityResult(False, "spectral_profile")
    return ApplicabilityResult(True)


def _spectrum(
    request: AnalyzerRequest, window: AudioWindowDescriptor
) -> SpectralWindowDescriptor | None:
    manifest = request.forensic
    assert manifest is not None
    matches = [
        r
        for r in manifest.representations
        if isinstance(r.facts, SpectralWindowDescriptor)
        and r.facts.samples_artifact_id == window.data.artifact_id
    ]
    if not matches and window.samples.count < 4096:
        return None
    if len(matches) != 1:
        raise ValueError("missing or duplicate spectral representation")
    representation = matches[0]
    provenance = representation.provenance
    if (
        provenance.producer,
        provenance.producer_version,
        provenance.profile,
        provenance.profile_version,
    ) != ("numpy_stft", "1", "hann4096_hop1024", "1"):
        raise ValueError("unexpected spectral provenance")
    assert isinstance(representation.facts, SpectralWindowDescriptor)
    return representation.facts


def _window_metrics(window: AudioWindowDescriptor, channel: int, rate: int) -> dict[str, JsonValue]:
    return {
        "stream_index": window.stream_index,
        "channel": channel,
        "sample_rate": rate,
        "samples": [window.samples.start, window.samples.stop],
        "first_sample_pts": window.first_sample_pts,
    }


def _atd(frame: NDArray[np.generic]) -> tuple[int, tuple[float | None, ...]]:
    # Scale before subtraction, including finite float64 values near its maximum.
    center = frame[767:1280].astype(np.float64)
    scale = float(np.max(np.abs(center)))
    boundary = 768 + int(np.argmax(np.abs(np.diff(center / scale if scale else center))))
    context = frame[boundary - 512 : boundary + 512].astype(np.float64)
    scale = float(np.max(np.abs(context)))
    if scale:
        context /= scale
    left, right = context[:512], context[512:]
    jump = abs(float(right[0] - left[-1]))
    typical = float(np.median(np.concatenate((np.abs(np.diff(left)), np.abs(np.diff(right))))))
    rms_left, rms_right = float(np.sqrt(np.mean(left**2))), float(np.sqrt(np.mean(right**2)))
    mean_left, mean_right = float(np.median(left)), float(np.median(right))
    change = abs(mean_right - mean_left)
    spread = float(np.median(np.abs(left - mean_left)) + np.median(np.abs(right - mean_right)))
    energy = (rms_right - rms_left) / (rms_right + rms_left) if rms_right + rms_left else None
    return boundary, (
        jump / (jump + typical) if jump + typical else None,
        abs(energy) if energy is not None else None,
        energy,
        change / (change + spread) if change + spread else None,
    )


class AudioTemporalDiscontinuityAnalyzer:
    analyzer_id: ClassVar[str] = "audio_temporal_discontinuity"
    analyzer_name: ClassVar[str] = "Audio temporal discontinuity (experimental)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "audio"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.AUDIO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _audio_applicability(request)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        precision, windows = _audio_inputs(request)
        rows: list[JsonValue] = []
        count = 0
        for window in windows:
            samples = request.read_numeric(window.data)
            frames = frame_audio(
                samples, sample_rate=precision.sample_rate, frame_length=2048, hop=512
            )
            for channel in range(precision.channels):
                positions: list[int] = []
                measurements: list[tuple[float | None, ...]] = []
                for i, frame in enumerate(frames.values[:, channel]):
                    boundary, values = _atd(frame)
                    positions.append(i * 512 + boundary)
                    measurements.append(values)
                metrics: dict[str, JsonValue] = _window_metrics(
                    window, channel, precision.sample_rate
                )
                metrics["frame_count"] = len(positions)
                metrics["dropped_tail_samples"] = frames.dropped_tail_samples
                for index, name in enumerate(("J", "E", "Es", "A")):
                    summary = _distribution([v[index] for v in measurements])
                    peak = summary.pop("max_index")
                    if isinstance(peak, int):
                        local = positions[peak]
                        summary["max_sample"] = window.samples.start + local
                        summary["support_samples"] = [
                            window.samples.start + local - 512,
                            window.samples.start + local + 512,
                        ]
                        summary["max_source_pts"] = (
                            window.first_sample_pts + local
                            if window.first_sample_pts is not None
                            else None
                        )
                    metrics[name] = summary
                count += len(positions)
                rows.append(metrics)
            del samples, frames
        return _measurement_result(
            self,
            request,
            "ATD-LOCAL-1",
            {
                "state": "measured" if count else "insufficient_evidence",
                "windows": rows,
            },
            _LIMITATION,
        )


def _spectral_pair(
    left: NDArray[np.float64], right: NDArray[np.float64]
) -> tuple[float | None, float | None]:
    scale = max(float(left.max()), float(right.max()))
    if not scale:
        return None, None
    left, right = left / scale, right / scale
    total_left, total_right = float(left.sum()), float(right.sum())
    tv = (
        float(np.abs(left / total_left - right / total_right).sum() / 2)
        if total_left and total_right
        else None
    )
    flux = float(np.maximum(right - left, 0).sum() / (total_left + total_right))
    return tv, flux


class AudioSpectralConsistencyAnalyzer:
    analyzer_id: ClassVar[str] = "audio_spectral_consistency"
    analyzer_name: ClassVar[str] = "Audio spectral consistency (experimental)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "audio"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.AUDIO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _audio_applicability(request, spectral=True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        precision, windows = _audio_inputs(request)
        rows: list[JsonValue] = []
        count = 0
        for window in windows:
            descriptor = _spectrum(request, window)
            if descriptor is None:
                rows.append(
                    {
                        "samples": [window.samples.start, window.samples.stop],
                        "state": "no_full_stft_frame",
                    }
                )
                continue
            magnitude = np.asarray(request.read_numeric(descriptor.data), dtype=np.float64)
            if np.any(magnitude < 0):
                raise ValueError("negative magnitude")
            for channel in range(precision.channels):
                metrics = _window_metrics(window, channel, precision.sample_rate)
                metrics["frame_count"] = descriptor.frames.count
                for lag in (1, 4):
                    pairs = [
                        _spectral_pair(magnitude[j, channel], magnitude[j + lag, channel])
                        for j in range(max(0, descriptor.frames.count - lag))
                    ]
                    count += len(pairs)
                    for index, name in enumerate(("D", "F")):
                        summary = _distribution([p[index] for p in pairs])
                        peak = summary.pop("max_index")
                        if isinstance(peak, int):
                            start = (descriptor.frames.start + peak) * 1024
                            summary["support_samples"] = [
                                window.samples.start + start,
                                window.samples.start + start + lag * 1024 + 4096,
                            ]
                            summary["support_source_pts"] = (
                                [
                                    window.first_sample_pts + start,
                                    window.first_sample_pts + start + lag * 1024 + 4096,
                                ]
                                if window.first_sample_pts is not None
                                else None
                            )
                        metrics[f"{name}{lag}"] = summary
                rows.append(metrics)
            del magnitude
        return _measurement_result(
            self,
            request,
            "ASC-TV-1",
            {
                "state": "measured" if count else "insufficient_evidence",
                "windows": rows,
            },
            _LIMITATION,
        )


def _floor(magnitude: NDArray[np.float64]) -> NDArray[np.float64]:
    power = np.square(magnitude)
    order = np.argsort(power.sum(axis=1), kind="stable")
    selected = power[order[: max(4, math.ceil(len(order) / 5))], 1:]
    return np.asarray(
        np.median(selected.reshape(-1, 16, 128).mean(axis=2), axis=0), dtype=np.float64
    )


class AudioBackgroundNoiseConsistencyAnalyzer:
    analyzer_id: ClassVar[str] = "audio_background_noise_consistency"
    analyzer_name: ClassVar[str] = "Audio low-energy spectral consistency (experimental weak)"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "audio"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.AUDIO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        return _audio_applicability(request, spectral=True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        precision, windows = _audio_inputs(request)
        rows: list[JsonValue] = []
        for window in windows:
            descriptor = _spectrum(request, window)
            if descriptor is None:
                continue
            magnitude = np.asarray(request.read_numeric(descriptor.data), dtype=np.float64)
            if np.any(magnitude < 0):
                raise ValueError("negative magnitude")
            starts = np.arange(descriptor.frames.start, descriptor.frames.stop) * 1024
            side = 2 * precision.sample_rate
            for channel in range(precision.channels):
                for boundary in range(side, window.samples.count - side + 1, precision.sample_rate):
                    left = magnitude[
                        (starts >= boundary - side) & (starts + 4096 <= boundary), channel
                    ]
                    right = magnitude[
                        (starts >= boundary) & (starts + 4096 <= boundary + side), channel
                    ]
                    if min(len(left), len(right)) < 8:
                        continue
                    scale = max(float(left.max()), float(right.max()))
                    lv, rv = (
                        _floor(left / scale if scale else left),
                        _floor(right / scale if scale else right),
                    )
                    ll, rl = float(lv.sum()), float(rv.sum())
                    row = _window_metrics(window, channel, precision.sample_rate)
                    row.update(
                        {
                            "boundary_sample": window.samples.start + boundary,
                            "support_samples": [
                                window.samples.start + boundary - side,
                                window.samples.start + boundary + side,
                            ],
                            "left_frames": len(left),
                            "right_frames": len(right),
                            "left_bands": lv.tolist(),
                            "right_bands": rv.tolist(),
                            "left_level": ll,
                            "right_level": rl,
                            "tv": float(np.abs(lv / ll - rv / rl).sum() / 2) if ll and rl else None,
                            "signed_level_change": (rl - ll) / (rl + ll) if rl + ll else None,
                        }
                    )
                    rows.append(row)
            del magnitude
        return _measurement_result(
            self,
            request,
            "ABN-FLOOR-1",
            {
                "state": "measured" if rows else "insufficient_evidence",
                "background_attribution": "insufficient_evidence_no_independent_matching",
                "contexts": rows,
            },
            "Low-energy selection does not isolate background or identify a microphone. "
            + _LIMITATION,
        )
