"""Accepted DQ-HIST-1 measurements and frozen DQ-R3C-1 decision."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import ClassVar, cast

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, JsonValue

from fakedetector.analyzers._candidates import _JpegRecompressionPatternCandidate
from fakedetector.analyzers._models import AnalyzerRequest, ApplicabilityResult
from fakedetector.analyzers._real_common import _completed_real_result
from fakedetector.domain import AnalyzerResult, FileLocalization, MediaType
from fakedetector.preprocessing._models import JpegCoefficientsDescriptor, OriginalImageFacts

_MODES = tuple((u, v) for u in range(4) for v in range(4) if 1 <= u + v <= 3)
_THRESHOLD = 0.6005747126436781
_LIMITATION = (
    "Sensitivity is limited to the supported aligned JPEG recompression-history scenario; "
    "portability beyond the evaluated population is not established. Same/close-quality, "
    "reverse-quality and shifted-grid recompression may be missed."
)


@dataclass(frozen=True, slots=True)
class _Histogram:
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

    def valid(self) -> bool:
        return (
            self.state == "measured"
            and self.n >= 1024
            and self.zero_fraction is not None
            and self.n - round(self.n * self.zero_fraction) >= 256
            and self.occupied is not None
            and self.occupied >= 8
            and self.span is not None
            and self.span >= 16
        )


def _histogram(values: NDArray[np.generic]) -> _Histogram:
    if values.dtype != np.dtype("<i4"):
        raise ValueError("expected native int32 coefficients")
    n = values.size
    if not n:
        return _Histogram(n=0)
    low, high = int(values.min()), int(values.max())
    span = high - low + 1
    if span > 65536:
        return _Histogram(n, low, high, span, state="histogram_limit")
    counts = np.bincount(values.ravel().astype(np.int64) - low, minlength=span)
    occupied = int(np.count_nonzero(counts))
    zero = int(counts[-low]) if low <= 0 <= high else 0
    frequency = amplitude = None
    if span > 1:
        length = 1 << (span - 1).bit_length()
        spectrum = np.abs(np.fft.rfft(counts / n, n=length, norm="backward"))
        peak = int(np.argmax(spectrum[1:])) + 1
        frequency, amplitude = peak / length, float(spectrum[peak])
    return _Histogram(
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


def _original(request: AnalyzerRequest) -> OriginalImageFacts:
    manifest = request.forensic
    if manifest is None:
        raise ValueError("required original image manifest absent")
    originals = [r for r in manifest.representations if isinstance(r.facts, OriginalImageFacts)]
    if len(originals) != 1:
        raise ValueError("required original image identity absent")
    representation = originals[0]
    provenance = representation.provenance
    if (
        provenance.producer,
        provenance.producer_version,
        provenance.profile,
        provenance.profile_version,
    ) != ("fakedetector", "1", "original_image", "1"):
        raise ValueError("unexpected original image provenance")
    return cast(OriginalImageFacts, representation.facts)


class ImageJpegDoubleQuantizationSettings(BaseModel):
    """The v1 method has no configurable parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ImageJpegDoubleQuantizationAnalyzer:
    analyzer_id: ClassVar[str] = "image_jpeg_double_quantization"
    analyzer_name: ClassVar[str] = "JPEG double quantization"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "image"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.IMAGE})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        if request.media_type is not MediaType.IMAGE:
            return ApplicabilityResult(False, "media_type")
        original = _original(request)
        if original.format != "jpeg":
            return ApplicabilityResult(False, "source_format_not_jpeg")
        if original.jpeg is None:
            raise ValueError("required JPEG header absent")
        sampling = tuple(
            (c.horizontal_sampling, c.vertical_sampling) for c in original.jpeg.components
        )
        if original.source_mode == "L" and sampling == ((1, 1),):
            return ApplicabilityResult(True)
        if original.source_mode == "RGB" and sampling in (
            ((1, 1), (1, 1), (1, 1)),
            ((2, 1), (1, 1), (1, 1)),
            ((2, 2), (1, 1), (1, 1)),
        ):
            return ApplicabilityResult(True)
        return ApplicabilityResult(False, "source_mode_or_sampling_layout_outside_dq_scope")

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        if not isinstance(request.settings, ImageJpegDoubleQuantizationSettings):
            raise TypeError("unexpected settings contract")
        original = _original(request)
        manifest = request.forensic
        assert manifest is not None
        representations = [
            r for r in manifest.representations if isinstance(r.facts, JpegCoefficientsDescriptor)
        ]
        if len(representations) != 1:
            raise ValueError("required coefficient representation absent or duplicate")
        representation = representations[0]
        provenance = representation.provenance
        if (
            provenance.producer,
            provenance.producer_version,
            provenance.profile,
            provenance.profile_version,
        ) != ("pyjpegio", "0.3.0", "jpeg_coefficients", "1"):
            raise ValueError("unexpected JPEG coefficient provenance")
        descriptor = cast(JpegCoefficientsDescriptor, representation.facts)
        if original.jpeg != descriptor.header or descriptor.decode_quality != "clean":
            raise ValueError("inconsistent JPEG identity")
        header = descriptor.header
        tables = {table.table_id: table.values for table in original.quantization_tables}
        if any(c.quantization_table_id not in tables for c in header.components):
            raise ValueError("required quantization table absent")
        max_h = max(c.horizontal_sampling for c in header.components)
        max_v = max(c.vertical_sampling for c in header.components)
        modes: list[JsonValue] = []
        values: list[float] = []
        for index, (component, plane) in enumerate(
            zip(header.components, descriptor.planes, strict=True)
        ):
            coefficients = request.read_numeric(plane)
            width = header.width * component.horizontal_sampling // (8 * max_h)
            height = header.height * component.vertical_sampling // (8 * max_v)
            excluded = plane.shape[0] * plane.shape[1] - width * height
            for u, v in _MODES:
                h = _histogram(coefficients[:height, :width, u, v])
                diagnostic: dict[str, JsonValue] = {
                    "component": component.component_id,
                    "u": u,
                    "v": v,
                    "q2": tables[component.quantization_table_id][8 * u + v],
                    "excluded_blocks": excluded,
                    **asdict(h),
                }
                if index == 0:
                    diagnostic["valid"] = h.valid()
                    if h.valid():
                        assert h.empty_fraction is not None
                        values.append(h.empty_fraction)
                modes.append(diagnostic)
            del coefficients
        measurement = median(values) if len(values) >= 5 else None
        decision = (
            "insufficient_evidence"
            if measurement is None
            else "positive"
            if measurement > _THRESHOLD
            else "no_signal"
        )
        summaries = {
            "positive": (
                "A JPEG coefficient-statistics pattern consistent with the supported aligned "
                "recompression-history scenario was observed. Compare it with the known export "
                "and transfer history; verify the source independently if provenance matters."
            ),
            "no_signal": (
                "The supported JPEG recompression-history pattern was not observed. "
                "This does not confirm authenticity or exclude recompression."
            ),
            "insufficient_evidence": (
                "Insufficient statistical support for this JPEG recompression-history pattern. "
                "Repeating analysis of the same bytes does not create additional support."
            ),
        }
        result = _completed_real_result(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            group=self.group,
            request=request,
            summary=summaries[decision],
            raw_metrics={
                "method": "DQ-HIST-1",
                "rule": "DQ-R3C-1",
                "metric": "empty_fraction",
                "threshold": _THRESHOLD,
                "median": measurement,
                "measurement_description": "Median fraction of empty bins",
                "decision": decision,
                "first_component": header.components[0].component_id,
                "valid_mode_count": len(values),
                "modes": modes,
            },
            candidates=(
                _JpegRecompressionPatternCandidate(
                    type="jpeg_recompression_pattern",
                    localization=FileLocalization(type="file"),
                    correlation_group="image_jpeg_compression_history",
                    evidence_refs=(),
                ),
            )
            if decision == "positive"
            else (),
        )
        result.warnings.append(_LIMITATION)
        if measurement is None:
            result.warnings.append("insufficient_evidence: fewer than 5 valid AC modes.")
        return result
