"""Immutable internal values shared by media preprocessing."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePath
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import Field, model_validator

from fakedetector._generated_artifact_budget import _MAX_GENERATED_ARTIFACTS
from fakedetector.domain import MediaType
from fakedetector.intake.temporary_input import PreparedSourceRef
from fakedetector.preprocessing._requirements import (
    _FORENSIC_POLICY,
    _MAX_FORENSIC_MANIFEST_BYTES,
    _MAX_FORENSIC_REPRESENTATIONS,
    _MAX_INDEX,
    _MAX_NUMERIC_BYTES,
    ForensicResourcePolicy,
    _BoundedValue,
    _checked_product,
    _NonnegativeIndex,
    _PositiveIndex,
)

if TYPE_CHECKING:
    from fakedetector.lifecycle.artifacts import WorkspaceArtifactRef

_Token = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")]
_ArtifactId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
_Tick = Annotated[int, Field(ge=-_MAX_INDEX, le=_MAX_INDEX)]


class RepresentationProvenance(_BoundedValue):
    producer: _Token
    producer_version: _Token
    profile: _Token
    profile_version: _Token


class IndexRange(_BoundedValue):
    """Actual observed half-open range; never a requested seek interval."""

    start: _NonnegativeIndex
    stop: _PositiveIndex

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.stop <= self.start:
            raise ValueError("coverage must be nonempty and ordered")
        return self

    @property
    def count(self) -> int:
        return self.stop - self.start


class ImageCoordinates(_BoundedValue):
    """Native edges [0,W]x[0,H]; centers are edges (i+0.5,j+0.5).

    The oriented image is not resized. Absent EXIF is orientation 1; invalid
    EXIF must be handled explicitly by the producer, not silently coerced here.
    """

    native_width: Annotated[int, Field(gt=0, le=65_535)]
    native_height: Annotated[int, Field(gt=0, le=65_535)]
    orientation: Annotated[int, Field(ge=1, le=8)] = 1

    @property
    def oriented_size(self) -> tuple[int, int]:
        if self.orientation >= 5:
            return self.native_height, self.native_width
        return self.native_width, self.native_height

    def transform_edge(self, x: float, y: float) -> tuple[float, float]:
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (x, y)):
            raise ValueError("coordinates must be finite numbers")
        width, height = self.native_width, self.native_height
        if not 0 <= x <= width or not 0 <= y <= height:
            raise ValueError("native edge is outside the source")
        return (
            (x, y),
            (width - x, y),
            (width - x, height - y),
            (x, height - y),
            (y, x),
            (height - y, x),
            (height - y, width - x),
            (y, width - x),
        )[self.orientation - 1]

    def normalized_bbox(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
    ) -> tuple[float, float, float, float]:
        """Return x/y/width/height for the existing public normalized convention."""
        corners = tuple(
            self.transform_edge(x, y)
            for x, y in (
                (left, top),
                (right, top),
                (left, bottom),
                (right, bottom),
            )
        )
        if left >= right or top >= bottom:
            raise ValueError("native bbox must be nonempty")
        width, height = self.oriented_size
        xs, ys = zip(*corners, strict=True)
        return (
            min(xs) / width,
            min(ys) / height,
            (max(xs) - min(xs)) / width,
            (max(ys) - min(ys)) / height,
        )


class JpegComponent(_BoundedValue):
    component_id: Annotated[int, Field(ge=0, le=255)]
    horizontal_sampling: Annotated[int, Field(ge=1, le=4)]
    vertical_sampling: Annotated[int, Field(ge=1, le=4)]
    quantization_table_id: Annotated[int, Field(ge=0, le=3)]


class JpegHeader(_BoundedValue):
    """SOF facts required before native decoding; no marker payloads or entropy."""

    width: Annotated[int, Field(gt=0, le=65_535)]
    height: Annotated[int, Field(gt=0, le=65_535)]
    precision_bits: Literal[8]
    coding: Literal["baseline", "progressive"]
    components: Annotated[tuple[JpegComponent, ...], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def sampling(self) -> Self:
        max_h = max(c.horizontal_sampling for c in self.components)
        max_v = max(c.vertical_sampling for c in self.components)
        if (
            len({c.component_id for c in self.components}) != len(self.components)
            or sum(c.horizontal_sampling * c.vertical_sampling for c in self.components) > 10
            or any(
                max_h % c.horizontal_sampling or max_v % c.vertical_sampling
                for c in self.components
            )
        ):
            raise ValueError("unsupported JPEG component sampling")
        return self

    def preflight(
        self,
        source_bytes: int,
        policy: ForensicResourcePolicy = _FORENSIC_POLICY,
    ) -> JpegAllocation:
        """Bound output and MCU-padded native coefficient slots without decoding."""
        _checked_product(source_bytes, limit=policy.jpeg_input_bytes)
        max_h = max(c.horizontal_sampling for c in self.components)
        max_v = max(c.vertical_sampling for c in self.components)
        shapes = tuple(
            (
                (self.height * c.vertical_sampling + 8 * max_v - 1) // (8 * max_v),
                (self.width * c.horizontal_sampling + 8 * max_h - 1) // (8 * max_h),
            )
            for c in self.components
        )
        output_count = sum(_checked_product(rows, cols, 64) for rows, cols in shapes)
        mcus = _checked_product(
            (self.width + 8 * max_h - 1) // (8 * max_h),
            (self.height + 8 * max_v - 1) // (8 * max_v),
        )
        padded_count = _checked_product(
            mcus,
            64,
            sum(c.horizontal_sampling * c.vertical_sampling for c in self.components),
            limit=policy.jpeg_coefficients,
        )
        return JpegAllocation(
            block_shapes=shapes,
            output_coefficients=output_count,
            native_coefficients=padded_count,
        )


class JpegAllocation(_BoundedValue):
    block_shapes: Annotated[
        tuple[tuple[_PositiveIndex, _PositiveIndex], ...], Field(min_length=1, max_length=4)
    ]
    output_coefficients: _PositiveIndex
    native_coefficients: _PositiveIndex

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.output_coefficients != sum(
            _checked_product(*shape, 64) for shape in self.block_shapes
        ):
            raise ValueError("JPEG coefficient estimate does not match shapes")
        if (
            not self.output_coefficients
            <= self.native_coefficients
            <= _FORENSIC_POLICY.jpeg_coefficients
        ):
            raise ValueError("JPEG coefficient allocation exceeds policy")
        return self

    @property
    def output_bytes(self) -> int:
        return self.output_coefficients * 4  # pyjpegio int32 projection

    @property
    def native_coefficient_bytes(self) -> int:
        return self.native_coefficients * 2  # libjpeg JCOEF; excludes other decoder memory


class NumericArtifact(_BoundedValue):
    """Opaque C-order raw numeric storage, never an ndarray or a filesystem path.

    A future reader must resolve this ID through its registered read capability,
    verify exact byte length before allocation, and expose an immutable backing
    buffer (not merely ndarray.flags.writeable=False on a writable owner).
    Explicit little endian dtypes make host-native endian/object/pickle invalid.
    """

    artifact_id: _ArtifactId
    shape: Annotated[tuple[_PositiveIndex, ...], Field(min_length=1, max_length=4)]
    dtype: Literal["|u1", "<i4", "<i8", "<f8", "<c16"]

    @model_validator(mode="after")
    def bounded(self) -> Self:
        _checked_product(*self.shape, self.itemsize, limit=_MAX_NUMERIC_BYTES)
        return self

    @property
    def itemsize(self) -> int:
        return {"|u1": 1, "<i4": 4, "<i8": 8, "<f8": 8, "<c16": 16}[self.dtype]

    @property
    def nbytes(self) -> int:
        return _checked_product(*self.shape, self.itemsize, limit=_MAX_NUMERIC_BYTES)

    def validate_byte_length(self, actual_bytes: int) -> None:
        if type(actual_bytes) is not int or actual_bytes != self.nbytes:
            raise ValueError("numeric artifact byte length does not match its descriptor")


class OriginalImageFacts(_BoundedValue):
    kind: Literal["original_image"] = "original_image"
    format: _Token
    coordinates: ImageCoordinates
    source_frame: _NonnegativeIndex = 0
    jpeg: JpegHeader | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.jpeg is not None and (
            self.format != "jpeg"
            or self.jpeg.width != self.coordinates.native_width
            or self.jpeg.height != self.coordinates.native_height
        ):
            raise ValueError("JPEG facts disagree with native image identity")
        return self


class ImageRasterDescriptor(_BoundedValue):
    kind: Literal["image_raster"] = "image_raster"
    coordinates: ImageCoordinates
    x: IndexRange
    y: IndexRange
    pixels: NumericArtifact

    @model_validator(mode="after")
    def layout(self) -> Self:
        width, height = self.coordinates.oriented_size
        _FORENSIC_POLICY.check_raster(width, height)
        if (
            self.x.stop > width
            or self.y.stop > height
            or self.pixels.dtype != "|u1"
            or len(self.pixels.shape) != 3
            or self.pixels.shape[:2] != (self.y.count, self.x.count)
            or self.pixels.shape[2] not in (1, 3, 4)
        ):
            raise ValueError("raster layout does not match oriented coverage")
        return self


class JpegCoefficientsDescriptor(_BoundedValue):
    kind: Literal["jpeg_coefficients"] = "jpeg_coefficients"
    header: JpegHeader
    planes: Annotated[tuple[NumericArtifact, ...], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def layout(self) -> Self:
        estimate = self.header.preflight(1)
        if len(self.planes) != len(estimate.block_shapes) or any(
            plane.dtype != "<i4" or plane.shape != (*shape, 8, 8)
            for plane, shape in zip(self.planes, estimate.block_shapes, strict=False)
        ):
            raise ValueError("coefficient planes must follow native SOF component order")
        return self


class AudioPrecisionFacts(_BoundedValue):
    kind: Literal["audio_precision"] = "audio_precision"
    stream_index: Annotated[int, Field(ge=0, le=255)]
    codec: _Token
    source_bits: Annotated[int, Field(gt=0, le=64)] | None
    decoder_format: Literal["u8", "s16", "s32", "flt", "dbl", "unknown"]
    sample_rate: Annotated[int, Field(gt=0, le=768_000)]
    channels: Annotated[int, Field(gt=0, le=64)]


class AudioWindowDescriptor(_BoundedValue):
    """Sample indices are relative to the source stream, never a seek target.

    int32 stores right-aligned signed sample codes (u8 centered on zero);
    float64 preserves decoder floating samples without gain/clipping. No resample,
    downmix or silent precision reduction. Channel order follows source facts.
    """

    kind: Literal["audio_samples"] = "audio_samples"
    stream_index: Annotated[int, Field(ge=0, le=255)]
    samples: IndexRange
    data: NumericArtifact

    @model_validator(mode="after")
    def layout(self) -> Self:
        if (
            self.data.dtype not in ("<i4", "<f8")
            or len(self.data.shape) != 2
            or self.data.shape[0] != self.samples.count
        ):
            raise ValueError("audio storage must have sample/channel axes")
        return self


class SpectralWindowDescriptor(_BoundedValue):
    kind: Literal["audio_spectral"] = "audio_spectral"
    samples_artifact_id: _ArtifactId
    frames: IndexRange
    n_fft: Annotated[int, Field(ge=4, le=_FORENSIC_POLICY.fft_size)]
    hop: _PositiveIndex
    window: Literal["hann", "rectangular"]
    scaling: Literal["complex", "magnitude", "power"]
    data: NumericArtifact

    @model_validator(mode="after")
    def layout(self) -> Self:
        if (
            len(self.data.shape) != 3
            or self.data.shape[0] != self.frames.count
            or self.data.shape[2] != self.n_fft // 2 + 1
            or self.data.dtype != ("<c16" if self.scaling == "complex" else "<f8")
        ):
            raise ValueError("spectral storage must have frame/channel/rFFT-bin axes")
        _FORENSIC_POLICY.check_spectral(
            self.n_fft,
            self.hop,
            self.frames.count * self.data.shape[1],
            1,
        )
        return self


class TimeBase(_BoundedValue):
    numerator: Annotated[int, Field(gt=0, le=(1 << 31) - 1)]
    denominator: Annotated[int, Field(gt=0, le=(1 << 31) - 1)]


class StreamTimingFacts(_BoundedValue):
    kind: Literal["stream_timing"] = "stream_timing"
    stream_index: Annotated[int, Field(ge=0, le=255)]
    stream_kind: Literal["audio", "video"]
    time_base: TimeBase
    start_tick: _Tick | None
    duration_ticks: _NonnegativeIndex | None


class TimingRecordsDescriptor(_BoundedValue):
    """Rows: PTS, DTS, duration, decode ordinal, validity mask (bits 0..2).

    Missing tick fields use zero plus a cleared validity bit. Records preserve
    decode order, including signed/repeated PTS; endpoints do not prove continuity.
    """

    kind: Literal["timing_records"] = "timing_records"
    stream_index: Annotated[int, Field(ge=0, le=255)]
    region: Annotated[int, Field(ge=0, lt=_FORENSIC_POLICY.timing_regions)]
    record_kind: Literal["packet", "frame"]
    first_tick: _Tick | None
    last_tick: _Tick | None
    data: NumericArtifact

    @model_validator(mode="after")
    def layout(self) -> Self:
        limit = (
            _FORENSIC_POLICY.timing_packets
            if self.record_kind == "packet"
            else _FORENSIC_POLICY.timing_frames
        )
        if (
            self.data.dtype != "<i8"
            or len(self.data.shape) != 2
            or self.data.shape[1] != 5
            or self.data.shape[0] > limit
            or self.data.nbytes > _FORENSIC_POLICY.timing_artifact_bytes
        ):
            raise ValueError("timing records exceed the typed table layout")
        return self


class DenseVideoWindowDescriptor(_BoundedValue):
    kind: Literal["dense_video"] = "dense_video"
    timing_artifact_id: _ArtifactId
    native_width: Annotated[int, Field(gt=0, le=_FORENSIC_POLICY.native_video_width)]
    native_height: Annotated[int, Field(gt=0, le=_FORENSIC_POLICY.native_video_height)]
    pixels: NumericArtifact

    @model_validator(mode="after")
    def layout(self) -> Self:
        if self.pixels.dtype != "|u1" or len(self.pixels.shape) != 4:
            raise ValueError("dense storage must be RGB24 frame/height/width/channel")
        frames, height, width, channels = self.pixels.shape
        if (
            frames > _FORENSIC_POLICY.dense_frames
            or channels != 3
            or width > min(self.native_width, _FORENSIC_POLICY.dense_width)
            or height > min(self.native_height, _FORENSIC_POLICY.dense_height)
            or abs(width * self.native_height - height * self.native_width)
            > max(self.native_width, self.native_height)
        ):
            raise ValueError("dense frame geometry exceeds bounded aspect-preserving decode")
        return self


class AVTimelineDescriptor(_BoundedValue):
    """Measured piecewise anchors; no inferred synchronization/drift conclusion.

    Rows: audio sample start/stop, video tick start/stop. Each row covers only
    observed continuous data; gaps between rows are not observed discontinuities.
    """

    kind: Literal["av_timeline"] = "av_timeline"
    samples_artifact_id: _ArtifactId
    timing_artifact_id: _ArtifactId
    data: NumericArtifact

    @model_validator(mode="after")
    def layout(self) -> Self:
        if (
            self.data.dtype != "<i8"
            or len(self.data.shape) != 2
            or self.data.shape[1] != 4
            or self.data.shape[0] > _FORENSIC_POLICY.timing_frames
        ):
            raise ValueError("AV mapping exceeds the typed anchor layout")
        return self


_ForensicFacts = Annotated[
    OriginalImageFacts
    | ImageRasterDescriptor
    | JpegCoefficientsDescriptor
    | AudioPrecisionFacts
    | AudioWindowDescriptor
    | SpectralWindowDescriptor
    | StreamTimingFacts
    | TimingRecordsDescriptor
    | DenseVideoWindowDescriptor
    | AVTimelineDescriptor,
    Field(discriminator="kind"),
]


class ForensicRepresentation(_BoundedValue):
    provenance: RepresentationProvenance
    facts: _ForensicFacts

    def numeric_artifacts(self) -> tuple[NumericArtifact, ...]:
        facts = self.facts
        if isinstance(facts, JpegCoefficientsDescriptor):
            return facts.planes
        if isinstance(facts, (ImageRasterDescriptor, DenseVideoWindowDescriptor)):
            return (facts.pixels,)
        if isinstance(
            facts,
            (
                AudioWindowDescriptor,
                SpectralWindowDescriptor,
                TimingRecordsDescriptor,
                AVTimelineDescriptor,
            ),
        ):
            return (facts.data,)
        return ()


class ForensicManifest(_BoundedValue):
    """Small projection in metadata['forensic']; source hash binds all entries once."""

    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    media_type: MediaType
    representations: Annotated[
        tuple[ForensicRepresentation, ...],
        Field(min_length=1, max_length=_MAX_FORENSIC_REPRESENTATIONS),
    ]

    @model_validator(mode="after")
    def bounded_graph(self) -> Self:
        facts = tuple(item.facts for item in self.representations)
        numeric = tuple(a for item in self.representations for a in item.numeric_artifacts())
        if len({a.artifact_id for a in numeric}) != len(numeric):
            raise ValueError("numeric artifacts must have unique ownership")
        audio = {f.stream_index: f for f in facts if isinstance(f, AudioPrecisionFacts)}
        streams = {f.stream_index: f for f in facts if isinstance(f, StreamTimingFacts)}
        samples = {f.data.artifact_id: f for f in facts if isinstance(f, AudioWindowDescriptor)}
        timing = {f.data.artifact_id: f for f in facts if isinstance(f, TimingRecordsDescriptor)}
        originals = tuple(f for f in facts if isinstance(f, OriginalImageFacts))
        if len(originals) > 1:
            raise ValueError("original image facts must have a single source identity")
        if (
            len(audio) != sum(isinstance(f, AudioPrecisionFacts) for f in facts)
            or len(streams) != sum(isinstance(f, StreamTimingFacts) for f in facts)
            or len(streams) > _FORENSIC_POLICY.timing_streams
            or len(audio) > _FORENSIC_POLICY.timing_streams
            or len(samples) > _FORENSIC_POLICY.audio_windows
            or sum(
                f.data.shape[0] * f.data.shape[1]
                for f in facts
                if isinstance(f, SpectralWindowDescriptor)
            )
            > _FORENSIC_POLICY.spectral_frames
            or sum(isinstance(f, DenseVideoWindowDescriptor) for f in facts)
            > _FORENSIC_POLICY.dense_windows
            or sum(f.data.shape[0] for f in timing.values()) > _FORENSIC_POLICY.timing_records
            or sum(f.data.nbytes for f in timing.values()) > _FORENSIC_POLICY.timing_artifact_bytes
            or len({(f.stream_index, f.region, f.record_kind) for f in timing.values()})
            != len(timing)
        ):
            raise ValueError("duplicate facts or aggregate representation limits exceeded")
        for fact in facts:
            if isinstance(
                fact, (OriginalImageFacts, ImageRasterDescriptor, JpegCoefficientsDescriptor)
            ):
                if self.media_type is not MediaType.IMAGE:
                    raise ValueError("image facts require the image route")
                if isinstance(fact, ImageRasterDescriptor) and (
                    not originals or fact.coordinates != originals[0].coordinates
                ):
                    raise ValueError("raster coordinates must match original image facts")
                if isinstance(fact, JpegCoefficientsDescriptor) and (
                    not originals or fact.header != originals[0].jpeg
                ):
                    raise ValueError("coefficients must match original JPEG facts")
            elif self.media_type is MediaType.IMAGE:
                raise ValueError("stream facts require audio/video")
            if isinstance(fact, AudioWindowDescriptor):
                precision = audio.get(fact.stream_index)
                if precision is None or fact.data.shape[1] != precision.channels:
                    raise ValueError("sample window requires matching source precision facts")
                integer_decode = precision.decoder_format in ("u8", "s16", "s32")
                if (
                    precision.decoder_format == "unknown"
                    or fact.data.dtype != ("<i4" if integer_decode else "<f8")
                    or integer_decode
                    and precision.source_bits is not None
                    and precision.source_bits > 32
                ):
                    raise ValueError("sample dtype cannot preserve declared decoder precision")
                _FORENSIC_POLICY.check_audio(
                    fact.samples.count, precision.channels, precision.sample_rate
                )
            if isinstance(fact, SpectralWindowDescriptor):
                source = samples.get(fact.samples_artifact_id)
                if (
                    source is None
                    or fact.data.shape[1] != source.data.shape[1]
                    or (fact.frames.stop - 1) * fact.hop + fact.n_fft > source.samples.count
                ):
                    raise ValueError("spectral frames must fit referenced unpadded samples")
            if isinstance(fact, TimingRecordsDescriptor) and fact.stream_index not in streams:
                raise ValueError("timing records require a known stream time base")
            if isinstance(fact, StreamTimingFacts) and (
                self.media_type is MediaType.AUDIO and fact.stream_kind != "audio"
            ):
                raise ValueError("audio route cannot have a video stream")
            if isinstance(fact, (DenseVideoWindowDescriptor, AVTimelineDescriptor)):
                records = timing.get(fact.timing_artifact_id)
                if (
                    self.media_type is not MediaType.VIDEO
                    or records is None
                    or records.record_kind != "frame"
                    or records.stream_index not in streams
                    or streams[records.stream_index].stream_kind != "video"
                ):
                    raise ValueError("video mapping requires video frame records")
                if isinstance(fact, DenseVideoWindowDescriptor):
                    base = streams[records.stream_index].time_base
                    if (
                        records.data.shape[0] != fact.pixels.shape[0]
                        or records.first_tick is None
                        or records.last_tick is None
                        or not 0
                        <= (records.last_tick - records.first_tick) * base.numerator
                        <= _FORENSIC_POLICY.dense_window_seconds * base.denominator
                    ):
                        raise ValueError("dense pixels require bounded measured frame timing")
                elif fact.samples_artifact_id not in samples:
                    raise ValueError("AV mapping requires known precision samples")
        if len(self.model_dump_json().encode("utf-8")) > _MAX_FORENSIC_MANIFEST_BYTES:
            raise ValueError("forensic manifest exceeds its metadata allowance")
        return self

    def to_metadata(self) -> str:
        return self.model_dump_json()

    def validate_binding(
        self,
        media_type: MediaType,
        artifact_formats: Mapping[str, str],
        *,
        source_sha256: str | None = None,
    ) -> None:
        if self.media_type is not media_type or (
            source_sha256 is not None and self.source_sha256 != source_sha256
        ):
            raise ValueError("forensic source identity mismatch")
        if any(
            artifact_formats.get(a.artifact_id) != "forensic_raw"
            for item in self.representations
            for a in item.numeric_artifacts()
        ):
            raise ValueError("forensic descriptor requires an available forensic_raw artifact")


def _forensic_manifest(metadata: Mapping[str, object]) -> ForensicManifest | None:
    if "forensic" not in metadata:
        return None
    payload = metadata["forensic"]
    if (
        not isinstance(payload, str)
        or len(payload) > _MAX_FORENSIC_MANIFEST_BYTES
        or (len(payload.encode("utf-8")) > _MAX_FORENSIC_MANIFEST_BYTES)
    ):
        raise ValueError("forensic metadata must be bounded typed JSON")
    return ForensicManifest.model_validate_json(payload)


@dataclass(frozen=True, slots=True)
class PreparedArtifact:
    """One registered generated artifact without a physical path or media bytes."""

    artifact_id: str
    artifact_type: str
    artifact_ref: WorkspaceArtifactRef = field(repr=False)
    format: str
    start_time_seconds: float | None = None
    end_time_seconds: float | None = None
    frame_index: int | None = None
    cleanup_required: bool = True

    def __post_init__(self) -> None:
        # Lifecycle imports PreparedMedia; facts must also be importable on their own.
        from fakedetector.lifecycle.artifacts import WorkspaceArtifactRef

        if not self.artifact_id:
            raise ValueError("artifact_id must not be empty")
        if not self.artifact_type:
            raise ValueError("artifact_type must not be empty")
        if not isinstance(self.artifact_ref, WorkspaceArtifactRef):
            raise TypeError("artifact_ref must be a WorkspaceArtifactRef")
        if not self.format:
            raise ValueError("format must not be empty")
        if not self.cleanup_required:
            raise ValueError("prepared artifacts must remain cleanup obligations")
        if self.frame_index is not None and self.frame_index < 0:
            raise ValueError("frame_index must not be negative")
        for field_name, value in (
            ("start_time_seconds", self.start_time_seconds),
            ("end_time_seconds", self.end_time_seconds),
        ):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{field_name} must be finite and non-negative")
        if (
            self.start_time_seconds is not None
            and self.end_time_seconds is not None
            and self.end_time_seconds < self.start_time_seconds
        ):
            raise ValueError("artifact time interval must not regress")


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    """Defensively immutable prepared media state for one accepted media source."""

    analysis_id: str
    media_type: MediaType
    source_file_ref: PreparedSourceRef = field(repr=False)
    artifacts: tuple[PreparedArtifact, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.analysis_id:
            raise ValueError("analysis_id must not be empty")
        if not isinstance(self.source_file_ref, PreparedSourceRef):
            raise TypeError("source_file_ref must be a PreparedSourceRef")
        if self.source_file_ref.analysis_id != self.analysis_id:
            raise ValueError("prepared source identity does not match media")

        artifacts = tuple(self.artifacts)
        if any(not isinstance(artifact, PreparedArtifact) for artifact in artifacts):
            raise TypeError("artifacts must contain only PreparedArtifact values")
        if len(artifacts) > _MAX_GENERATED_ARTIFACTS:
            raise ValueError("prepared media contains too many artifacts")
        artifact_ids = [artifact.artifact_id for artifact in artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("prepared artifacts contain conflicting IDs")

        manifest = _forensic_manifest(self.metadata)
        if manifest is not None:
            manifest.validate_binding(self.media_type, {a.artifact_id: a.format for a in artifacts})

        warnings = tuple(self.warnings)
        if any(not isinstance(warning, str) for warning in warnings):
            raise TypeError("warnings must contain only strings")

        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        object.__setattr__(self, "warnings", warnings)

    @property
    def forensic(self) -> ForensicManifest | None:
        return _forensic_manifest(self.metadata)


def _freeze_metadata(metadata: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping")
    frozen: dict[str, object] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise TypeError("metadata keys must be strings")
        frozen[key] = _freeze_metadata_value(value)
    return MappingProxyType(frozen)


def _freeze_metadata_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_metadata(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_metadata_value(item) for item in value)
    if isinstance(value, (PurePath, bytes, bytearray, memoryview)):
        raise TypeError("metadata cannot contain paths or binary data")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise TypeError("metadata contains an unsupported value")
