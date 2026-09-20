"""Internal capability and immutable model tests for Stage 5 Increment 1."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePath
from typing import cast

import numpy as np
import pytest
from PIL import Image, ImageOps
from pydantic import BaseModel, ValidationError

import fakedetector
import fakedetector.intake as intake
import fakedetector.lifecycle as lifecycle
import fakedetector.preprocessing as preprocessing
from fakedetector.domain import (
    AnalysisStatus,
    ImageTechnicalParameters,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.intake import AcceptedSource, LocalTemporaryInputOwner
from fakedetector.intake.temporary_input import PreparedSourceRef
from fakedetector.lifecycle import AnalysisContext, AnalysisTask, TaskSnapshot
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry
from fakedetector.lifecycle.models import Stage5TaskData, _StoredAnalyzerResult
from fakedetector.preprocessing._media_tools import (
    GradientPlanes,
    ImageTile,
    KernelPlane,
    LuminanceTile,
    RobustLocalStatistics,
    TileRegion,
    extract_image_tiles,
    finite_differences,
    high_pass_residual,
    robust_local_statistics,
    smooth_luminance,
    to_luminance,
)
from fakedetector.preprocessing._models import (
    AudioPrecisionFacts,
    AudioWindowDescriptor,
    AVTimelineDescriptor,
    DenseVideoWindowDescriptor,
    ForensicManifest,
    ForensicRepresentation,
    ImageCoordinates,
    ImageRasterDescriptor,
    IndexRange,
    JpegCoefficientsDescriptor,
    JpegComponent,
    JpegHeader,
    NumericArtifact,
    OriginalImageFacts,
    PreparedArtifact,
    PreparedMedia,
    RepresentationProvenance,
    SpectralWindowDescriptor,
    StreamTimingFacts,
    TimeBase,
    TimingRecordsDescriptor,
    _forensic_manifest,
)
from fakedetector.preprocessing._requirements import (
    _MAX_FORENSIC_MANIFEST_BYTES,
    ForensicResourcePolicy,
    _checked_product,
)

_CREATED_AT = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


def _jpeg_header(width=17, height=17, sampling=((2, 2), (1, 1), (1, 1))):
    return JpegHeader(
        width=width,
        height=height,
        precision_bits=8,
        coding="baseline",
        components=tuple(
            JpegComponent(
                component_id=i,
                horizontal_sampling=h,
                vertical_sampling=v,
                quantization_table_id=0 if i == 0 else 3,
            )
            for i, (h, v) in enumerate(sampling)
        ),
    )


def _numeric(artifact_id, shape, dtype="<i4"):
    return NumericArtifact(artifact_id=artifact_id, shape=shape, dtype=dtype)


def _manifest(*facts, media_type=MediaType.IMAGE):
    return ForensicManifest(
        source_sha256="0" * 64,
        media_type=media_type,
        representations=tuple(
            ForensicRepresentation(
                provenance=RepresentationProvenance(
                    producer="preprocessing",
                    producer_version="1",
                    profile="bounded",
                    profile_version="1",
                ),
                facts=fact,
            )
            for fact in facts
        ),
    )


@pytest.mark.parametrize(
    "orientation,expected_point,expected_box",
    [
        (1, (0.5, 0.5), (0.25, 0, 0.5, 0.5)),
        (2, (3.5, 0.5), (0.25, 0, 0.5, 0.5)),
        (3, (3.5, 1.5), (0.25, 0.5, 0.5, 0.5)),
        (4, (0.5, 1.5), (0.25, 0.5, 0.5, 0.5)),
        (5, (0.5, 0.5), (0, 0.25, 0.5, 0.5)),
        (6, (1.5, 0.5), (0.5, 0.25, 0.5, 0.5)),
        (7, (1.5, 3.5), (0.5, 0.25, 0.5, 0.5)),
        (8, (0.5, 3.5), (0, 0.25, 0.5, 0.5)),
    ],
)
def test_forensic_exif_edges_centers_and_bbox_match_existing_orientation(
    orientation,
    expected_point,
    expected_box,
):
    coords = ImageCoordinates(native_width=4, native_height=2, orientation=orientation)
    assert coords.oriented_size == ((4, 2) if orientation < 5 else (2, 4))
    assert coords.transform_edge(0.5, 0.5) == expected_point
    assert coords.normalized_bbox(1, 0, 3, 1) == expected_box
    assert coords.normalized_bbox(0, 0, 4, 2) == (0, 0, 1, 1)
    with Image.new("L", (4, 2)) as native:
        native.putdata(range(8))
        native.getexif()[274] = orientation
        with ImageOps.exif_transpose(native) as oriented:
            for y in range(2):
                for x in range(4):
                    ox, oy = coords.transform_edge(x + 0.5, y + 0.5)
                    assert oriented.getpixel((int(ox), int(oy))) == native.getpixel((x, y))


@pytest.mark.parametrize(
    "box", [(-1, 0, 1, 1), (0, 0, 5, 1), (1, 1, 0, 2), (0, 0, 0, 1), (0, 0, float("nan"), 1)]
)
def test_forensic_coordinate_rejects_invalid_bbox(box):
    with pytest.raises(ValueError):
        ImageCoordinates(native_width=4, native_height=2).normalized_bbox(*box)


@pytest.mark.parametrize("orientation", [0, 9, True, 1.0, "1"])
def test_forensic_coordinate_rejects_non_exif_values(orientation):
    with pytest.raises(ValidationError):
        ImageCoordinates(native_width=4, native_height=2, orientation=orientation)


def test_jpeg_preflight_bounds_mcu_padding_before_any_decoder():
    estimate = _jpeg_header().preflight(100)
    assert estimate.block_shapes == ((3, 3), (2, 2), (2, 2))
    assert estimate.output_coefficients == 17 * 64
    assert estimate.native_coefficients == 24 * 64
    assert estimate.output_bytes == 4352
    assert estimate.native_coefficient_bytes == 3072
    for sampling, shapes in [
        (((1, 1),), ((3, 3),)),
        (((1, 1),) * 3, ((3, 3),) * 3),
        (((2, 1), (1, 1), (1, 1)), ((3, 3), (3, 2), (3, 2))),
    ]:
        assert _jpeg_header(sampling=sampling).preflight(100).block_shapes == shapes
    maximum = _jpeg_header(4096, 1024, ((1, 1),)).preflight(32 << 20)
    assert maximum.output_bytes == 16 << 20
    assert maximum.native_coefficient_bytes == 8 << 20
    with pytest.raises(ValueError):
        _jpeg_header(4097, 1024, ((1, 1),)).preflight(1)
    with pytest.raises(ValueError):
        _jpeg_header(65_535, 65_535).preflight(1)
    with pytest.raises(ValueError):
        _jpeg_header().preflight((32 << 20) + 1)
    with pytest.raises(ValueError):
        _jpeg_header().preflight(1, ForensicResourcePolicy(jpeg_coefficients=1088))
    progressive = _jpeg_header().model_dump()
    progressive["coding"] = "progressive"
    assert JpegHeader.model_validate(progressive).preflight(100) == estimate


@pytest.mark.parametrize(
    "updates",
    [
        {"width": 0},
        {"height": 1 << 64},
        {"precision_bits": 12},
        {"coding": "lossless"},
        {"components": ()},
        {"components": _jpeg_header().components * 2},
        {"components": (_jpeg_header().components[0],) * 2},
    ],
)
def test_jpeg_preflight_rejects_malformed_header_facts(updates):
    with pytest.raises(ValidationError):
        JpegHeader.model_validate(_jpeg_header().model_dump() | updates)


@pytest.mark.parametrize(
    "sampling", [((0, 1),), ((5, 1),), ((4, 4),), ((3, 1), (2, 1)), ((1, 3), (1, 2))]
)
def test_jpeg_preflight_rejects_unsupported_sampling(sampling):
    with pytest.raises(ValidationError):
        _jpeg_header(sampling=sampling)


@pytest.mark.parametrize("values", [(0,), (-1,), (True,), (1.0,), (1 << 63,), ((1 << 63) - 1, 2)])
def test_forensic_size_arithmetic_rejects_invalid_or_overflowing_values(values):
    with pytest.raises(ValueError):
        _checked_product(*values)


@pytest.mark.parametrize(
    "updates",
    [
        {"audio_windows": 0},
        {"audio_rate": True},
        {"fft_size": 4097},
        {"spectral_frames": 4},
        {"audio_window_samples": 1},
        {"raster_pixels": 1},
        {"jpeg_input_bytes": 100},
        {"timing_regions": 1},
        {"timing_artifact_bytes": 1},
        {"native_video_width": 320},
        {"dense_frames": 1 << 64},
        {"extra": 1},
    ],
)
def test_forensic_resource_policy_rejects_incoherent_or_unbounded_limits(updates):
    with pytest.raises(ValidationError):
        ForensicResourcePolicy(**updates)


def test_forensic_resource_policy_uses_existing_shared_budget(tmp_path):
    import yaml

    from fakedetector._generated_artifact_budget import (
        _GeneratedArtifactBudget,
        _GeneratedArtifactLimitError,
    )
    from fakedetector.config._snapshot import _ConfigSnapshot
    from fakedetector.config.models import AppConfig

    config = AppConfig.model_validate(
        yaml.safe_load(
            Path("config/config.example.yaml").read_text(encoding="utf-8"),
        )
    )
    budget = _GeneratedArtifactBudget(_ConfigSnapshot.capture(config), MediaType.IMAGE)
    with budget.open_output(tmp_path / "already_created") as output:
        output.write(b"used")
    policy = ForensicResourcePolicy()
    policy.check_artifacts(budget, total_count=256, additional_bytes=budget.remaining_bytes)
    assert budget.used_bytes == 4
    with pytest.raises(_GeneratedArtifactLimitError):
        policy.check_artifacts(budget, total_count=257, additional_bytes=0)
    with pytest.raises(_GeneratedArtifactLimitError):
        policy.check_artifacts(budget, total_count=1, additional_bytes=budget.max_bytes)


@pytest.mark.parametrize(
    "method,args",
    [
        ("check_raster", (4096, 1025)),
        ("check_tile", (513, 512, 2, 1024)),
        ("check_tile", (512, 512, 3, 1024)),
        ("check_tile", (512, 512, 2, (32 << 20) + 1)),
        ("check_audio", (100, 9, 48000)),
        ("check_audio", (480001, 1, 48000)),
        ("check_audio", (1 << 20, 2, 192000)),
        ("check_audio", (1, 1, 192001)),
        ("check_spectral", (4096, 1023, 32, 1)),
        ("check_spectral", (4096, 1024, 8193, 1)),
        ("check_spectral", (4096, 1024, 40, 33)),
    ],
)
def test_forensic_operation_limits_are_executable(method, args):
    with pytest.raises(ValueError):
        getattr(ForensicResourcePolicy(), method)(*args)


@pytest.mark.parametrize(
    "updates",
    [
        {"artifact_id": "../source"},
        {"artifact_id": "C:\\private"},
        {"artifact_id": "a" * 65},
        {"shape": ()},
        {"shape": (1,) * 5},
        {"shape": (0,)},
        {"shape": (-1,)},
        {"shape": (True,)},
        {"shape": (1 << 63,)},
        {"shape": (4096, 4097)},
        {"dtype": "object"},
        {"dtype": "=i4"},
        {"dtype": ">i4"},
        {"dtype": "int32"},
        {"path": "private"},
        {"data": [1, 2]},
    ],
)
def test_numeric_descriptors_reject_unbounded_or_ambiguous_storage(updates):
    with pytest.raises(ValidationError):
        NumericArtifact.model_validate(
            {"artifact_id": "samples", "shape": (2, 3), "dtype": "<i4"} | updates
        )


@pytest.mark.parametrize(
    "dtype,itemsize", [("|u1", 1), ("<i4", 4), ("<i8", 8), ("<f8", 8), ("<c16", 16)]
)
def test_numeric_byte_length_and_immutable_descriptor(dtype, itemsize):
    descriptor = _numeric("samples", (2, 3), dtype)
    assert descriptor.nbytes == 6 * itemsize
    descriptor.validate_byte_length(6 * itemsize)
    with pytest.raises(ValueError):
        descriptor.validate_byte_length(6 * itemsize + 1)
    with pytest.raises(ValidationError):
        descriptor.shape = (3, 2)
    assert NumericArtifact.model_validate_json(descriptor.model_dump_json()) == descriptor


def _audio_facts():
    return AudioPrecisionFacts(
        stream_index=1,
        codec="pcm_s24le",
        source_bits=24,
        decoder_format="s32",
        sample_rate=48000,
        channels=2,
    )


def _sample_window():
    return AudioWindowDescriptor(
        stream_index=1,
        samples=IndexRange(start=48000, stop=49024),
        data=_numeric("samples", (1024, 2)),
    )


def _video_facts():
    return (
        StreamTimingFacts(
            stream_index=0,
            stream_kind="video",
            time_base=TimeBase(numerator=1, denominator=25),
            start_tick=-10,
            duration_ticks=None,
        ),
        TimingRecordsDescriptor(
            stream_index=0,
            region=0,
            record_kind="frame",
            first_tick=-10,
            last_tick=40,
            data=_numeric("timing", (2, 5), "<i8"),
        ),
        DenseVideoWindowDescriptor(
            timing_artifact_id="timing",
            native_width=640,
            native_height=360,
            pixels=_numeric("dense", (2, 180, 320, 3), "|u1"),
        ),
    )


def test_all_forensic_representation_families_roundtrip_without_media_payloads():
    coords = ImageCoordinates(native_width=17, native_height=17, orientation=6)
    header = _jpeg_header()
    coefficients = JpegCoefficientsDescriptor(
        header=header,
        planes=tuple(
            _numeric(f"coeff_{i}", (*shape, 8, 8))
            for i, shape in enumerate(header.preflight(100).block_shapes)
        ),
    )
    image = _manifest(
        OriginalImageFacts(format="jpeg", coordinates=coords, jpeg=header),
        coefficients,
        ImageRasterDescriptor(
            coordinates=coords,
            x=IndexRange(start=0, stop=17),
            y=IndexRange(start=0, stop=17),
            pixels=_numeric("raster", (17, 17, 3), "|u1"),
        ),
    )
    spectral = SpectralWindowDescriptor(
        samples_artifact_id="samples",
        frames=IndexRange(start=0, stop=3),
        n_fft=512,
        hop=256,
        window="hann",
        scaling="complex",
        data=_numeric("spectral", (3, 2, 257), "<c16"),
    )
    audio = _manifest(_audio_facts(), _sample_window(), spectral, media_type=MediaType.AUDIO)
    av = AVTimelineDescriptor(
        samples_artifact_id="samples",
        timing_artifact_id="timing",
        data=_numeric("av_map", (2, 4), "<i8"),
    )
    video = _manifest(
        *_video_facts(), _audio_facts(), _sample_window(), av, media_type=MediaType.VIDEO
    )
    from fakedetector.analyzers._transport import _MAX_METADATA_BYTES, _MAX_RESPONSE_BYTES

    assert _MAX_RESPONSE_BYTES == 65_536
    for manifest in (image, audio, video):
        payload = manifest.to_metadata()
        assert len(payload.encode()) < _MAX_FORENSIC_MANIFEST_BYTES
        assert len(json.dumps({"forensic": payload}).encode()) < _MAX_METADATA_BYTES
        assert _forensic_manifest({"forensic": payload}) == manifest
        assert "path" not in payload and "raw_metrics" not in payload
        artifact_formats = {
            a.artifact_id: "forensic_raw"
            for r in manifest.representations
            for a in r.numeric_artifacts()
        }
        manifest.validate_binding(manifest.media_type, artifact_formats, source_sha256="0" * 64)
        with pytest.raises(ValueError):
            manifest.validate_binding(manifest.media_type, {})
        with pytest.raises(ValueError, match="forensic_raw"):
            manifest.validate_binding(manifest.media_type, dict.fromkeys(artifact_formats, "png"))


@pytest.mark.parametrize(
    "decoder_format,source_bits,dtype",
    [
        ("unknown", None, "<i4"),
        ("s32", 32, "<f8"),
        ("dbl", 64, "<i4"),
        ("s32", 64, "<i4"),
    ],
)
def test_sample_descriptor_rejects_lossy_or_ambiguous_precision(
    decoder_format,
    source_bits,
    dtype,
):
    precision = AudioPrecisionFacts.model_validate(
        _audio_facts().model_dump()
        | {
            "decoder_format": decoder_format,
            "source_bits": source_bits,
        }
    )
    window = AudioWindowDescriptor.model_validate(
        _sample_window().model_dump()
        | {
            "data": _numeric("samples", (1024, 2), dtype),
        }
    )
    with pytest.raises(ValidationError, match="decoder precision"):
        _manifest(precision, window, media_type=MediaType.AUDIO)


def test_float_precision_samples_remain_float64():
    precision = AudioPrecisionFacts.model_validate(
        _audio_facts().model_dump()
        | {
            "codec": "pcm_f64le",
            "decoder_format": "dbl",
            "source_bits": 64,
        }
    )
    window = AudioWindowDescriptor.model_validate(
        _sample_window().model_dump()
        | {
            "data": _numeric("samples", (1024, 2), "<f8"),
        }
    )
    manifest = _manifest(precision, window, media_type=MediaType.AUDIO)
    assert _forensic_manifest({"forensic": manifest.to_metadata()}) == manifest


@pytest.mark.parametrize(
    "bad_value",
    ["a" * 16_385, "é" * 9000, b"{}", {}, "[" * 1000 + "]" * 1000, '{"raw_ffprobe":{}}'],
    ids=["chars", "utf8", "bytes", "mapping", "recursive", "raw"],
)
def test_forensic_projection_rejects_unbounded_raw_or_recursive_data(bad_value):
    with pytest.raises(ValueError):
        _forensic_manifest({"forensic": bad_value})


@pytest.mark.parametrize(
    "changes",
    [
        {"source_sha256": "A" * 64},
        {"source_sha256": "../private"},
        {"representations": ()},
        {"metadata": {"raw_exif": "secret"}},
    ],
)
def test_forensic_manifest_rejects_bad_identity_or_schema(changes):
    base = _manifest(
        OriginalImageFacts(
            format="png",
            coordinates=ImageCoordinates(
                native_width=4,
                native_height=2,
            ),
        )
    )
    with pytest.raises(ValidationError):
        ForensicManifest.model_validate(base.model_dump() | changes)
    with pytest.raises(ValidationError):
        base.representations[0].provenance.profile = "changed"


@pytest.mark.parametrize("token", ["", "a" * 65, "../path/", "C:\\path", "raw json {}"])
def test_forensic_provenance_has_bounded_non_path_identifiers(token):
    with pytest.raises(ValidationError):
        RepresentationProvenance(
            producer=token, producer_version="1", profile="a", profile_version="1"
        )


def test_forensic_manifest_rejects_missing_or_conflicting_references():
    with pytest.raises(ValidationError, match="precision"):
        _manifest(_sample_window(), media_type=MediaType.AUDIO)
    with pytest.raises(ValidationError, match="unique"):
        _manifest(_audio_facts(), _sample_window(), _sample_window(), media_type=MediaType.AUDIO)
    with pytest.raises(ValidationError, match="video frame"):
        _manifest(_video_facts()[2], media_type=MediaType.VIDEO)
    with pytest.raises(ValidationError, match="audio/video"):
        _manifest(_audio_facts())
    with pytest.raises(ValidationError, match="video"):
        _manifest(*_video_facts(), media_type=MediaType.AUDIO)


@pytest.mark.parametrize(
    "family,changes",
    [
        ("original", {"format": "png"}),
        ("raster", {"x": IndexRange(start=0, stop=18)}),
        ("coefficients", {"planes": (_numeric("bad", (1, 1, 8, 8)),)}),
        ("samples", {"samples": IndexRange(start=0, stop=1)}),
        ("spectral", {"data": _numeric("spectral", (1, 2, 256), "<f8")}),
        ("timing", {"data": _numeric("timing", (513, 5), "<i8")}),
        ("dense", {"pixels": _numeric("dense", (33, 180, 320, 3), "|u1")}),
        ("dense", {"pixels": _numeric("dense", (2, 180, 640, 3), "|u1")}),
        ("av", {"data": _numeric("av", (1, 5), "<i8")}),
    ],
)
def test_each_forensic_descriptor_validates_layout_and_coverage(family, changes):
    coords = ImageCoordinates(native_width=17, native_height=17)
    header = _jpeg_header()
    fixtures = {
        "original": OriginalImageFacts(format="jpeg", coordinates=coords, jpeg=header),
        "raster": ImageRasterDescriptor(
            coordinates=coords,
            x=IndexRange(start=0, stop=17),
            y=IndexRange(start=0, stop=17),
            pixels=_numeric("raster", (17, 17, 3), "|u1"),
        ),
        "coefficients": JpegCoefficientsDescriptor(
            header=header,
            planes=tuple(
                _numeric(f"coeff_{i}", (*shape, 8, 8))
                for i, shape in enumerate(header.preflight(100).block_shapes)
            ),
        ),
        "samples": _sample_window(),
        "spectral": SpectralWindowDescriptor(
            samples_artifact_id="samples",
            frames=IndexRange(start=0, stop=1),
            n_fft=512,
            hop=128,
            window="hann",
            scaling="power",
            data=_numeric("spectral", (1, 2, 257), "<f8"),
        ),
        "timing": _video_facts()[1],
        "dense": _video_facts()[2],
        "av": AVTimelineDescriptor(
            samples_artifact_id="samples",
            timing_artifact_id="timing",
            data=_numeric("av", (1, 4), "<i8"),
        ),
    }
    valid = fixtures[family]
    with pytest.raises(ValidationError):
        type(valid).model_validate(valid.model_dump() | changes)


def test_forensic_serialized_manifest_cap_and_representation_count():
    header = _jpeg_header(1024, 1024, ((1, 1),) * 4)
    original = OriginalImageFacts(
        format="jpeg",
        jpeg=header,
        coordinates=ImageCoordinates(native_width=1024, native_height=1024),
    )
    long_provenance = RepresentationProvenance(
        producer="p" * 64,
        producer_version="v" * 64,
        profile="p" * 64,
        profile_version="v" * 64,
    )
    representations = (ForensicRepresentation(provenance=long_provenance, facts=original),) + tuple(
        ForensicRepresentation(
            provenance=long_provenance,
            facts=JpegCoefficientsDescriptor(
                header=header,
                planes=tuple(
                    _numeric(f"plane_{i}_{j}_" + "a" * 50, (128, 128, 8, 8)) for j in range(4)
                ),
            ),
        )
        for i in range(15)
    )
    with pytest.raises(ValidationError, match="metadata allowance"):
        ForensicManifest(
            source_sha256="0" * 64, media_type=MediaType.IMAGE, representations=representations
        )
    with pytest.raises(ValidationError, match="at most 16"):
        ForensicManifest(
            source_sha256="0" * 64,
            media_type=MediaType.IMAGE,
            representations=representations + representations[:1],
        )


def test_forensic_image_and_stream_references_reject_inconsistent_facts():
    original = OriginalImageFacts(
        format="png",
        coordinates=ImageCoordinates(
            native_width=4,
            native_height=2,
        ),
    )
    raster = ImageRasterDescriptor(
        coordinates=ImageCoordinates(native_width=4, native_height=2, orientation=6),
        x=IndexRange(start=0, stop=2),
        y=IndexRange(start=0, stop=4),
        pixels=_numeric("raster", (4, 2, 3), "|u1"),
    )
    with pytest.raises(ValidationError, match="coordinates"):
        _manifest(original, raster)
    with pytest.raises(ValidationError, match="single source"):
        _manifest(original, original)
    with pytest.raises(ValidationError, match="duplicate facts"):
        _manifest(_audio_facts(), _audio_facts(), media_type=MediaType.AUDIO)
    spectrum = SpectralWindowDescriptor(
        samples_artifact_id="samples",
        frames=IndexRange(start=0, stop=4),
        n_fft=512,
        hop=256,
        window="hann",
        scaling="power",
        data=_numeric("spectrum", (4, 2, 257), "<f8"),
    )
    with pytest.raises(ValidationError, match="unpadded"):
        _manifest(_audio_facts(), _sample_window(), spectrum, media_type=MediaType.AUDIO)
    stream, timing, dense = _video_facts()
    out_of_time = TimingRecordsDescriptor.model_validate(timing.model_dump() | {"last_tick": 41})
    with pytest.raises(ValidationError, match="bounded measured"):
        _manifest(stream, out_of_time, dense, media_type=MediaType.VIDEO)


def test_forensic_facts_bind_to_prepared_media_parent_and_worker(tmp_path):
    from fakedetector.analyzers._errors import AnalyzerInfrastructureError
    from fakedetector.analyzers._models import (
        AnalyzerRequest,
        _AnalyzerFileFacts,
        _ReadOnlyAnalyzerInput,
    )
    from fakedetector.analyzers._orchestrator import AnalyzerOrchestrator

    class EmptySettings(BaseModel):
        pass

    manifest = _manifest(
        OriginalImageFacts(
            format="png",
            coordinates=ImageCoordinates(
                native_width=1,
                native_height=1,
            ),
        )
    )
    prepared, _, accepted, registry = make_prepared_media(
        tmp_path,
        "forensic_binding",
        metadata={"forensic": manifest.to_metadata()},
    )
    try:
        assert prepared.forensic == manifest
        validated = image_descriptor(prepared.analysis_id)
        AnalyzerOrchestrator._validate_inputs(prepared, validated, registry)
        request = AnalyzerRequest(
            analysis_id=prepared.analysis_id,
            media_type=MediaType.IMAGE,
            file_facts=_AnalyzerFileFacts.from_validated_file(validated),
            source=_ReadOnlyAnalyzerInput(tmp_path / "unused"),
            settings=EmptySettings(),
            timeout_seconds=1,
            metadata=prepared.metadata,
        )
        assert request.forensic == manifest
        wrong_hash = validated.model_copy(update={"sha256": "1" * 64})
        with pytest.raises(AnalyzerInfrastructureError) as error:
            AnalyzerOrchestrator._validate_inputs(prepared, wrong_hash, registry)
        assert error.value.phase == "forensic_identity"
        with pytest.raises(ValueError, match="source identity"):
            replace(request, file_facts=_AnalyzerFileFacts.from_validated_file(wrong_hash))
        assert replace(request, metadata={}).forensic is None
        assert replace(prepared, metadata={}).forensic is None
    finally:
        cleanup_prepared(accepted, registry)


@pytest.mark.parametrize("length_delta", [-1, 0, 1])
def test_numeric_reader_binds_identity_extent_and_immutable_backing(tmp_path, length_delta):
    from fakedetector.analyzers._models import (
        AnalyzerArtifactInput,
        AnalyzerRequest,
        _AnalyzerFileFacts,
        _ReadOnlyAnalyzerInput,
    )

    class EmptySettings(BaseModel):
        pass

    header = _jpeg_header(width=8, height=8, sampling=((1, 1),))
    plane = _numeric("coefficients", (1, 1, 8, 8))
    manifest = _manifest(
        OriginalImageFacts(
            format="jpeg",
            coordinates=ImageCoordinates(native_width=8, native_height=8),
            jpeg=header,
        ),
        JpegCoefficientsDescriptor(header=header, planes=(plane,)),
    )
    path = tmp_path / "coefficients.raw"
    path.write_bytes(bytes(plane.nbytes + length_delta))
    request = AnalyzerRequest(
        analysis_id="reader",
        media_type=MediaType.IMAGE,
        file_facts=_AnalyzerFileFacts.from_validated_file(image_descriptor("reader")),
        source=_ReadOnlyAnalyzerInput(tmp_path / "unused"),
        settings=EmptySettings(),
        timeout_seconds=1,
        metadata={"forensic": manifest.to_metadata()},
        artifacts=(
            AnalyzerArtifactInput(
                artifact_id="coefficients",
                artifact_type="jpeg_coefficients",
                content=_ReadOnlyAnalyzerInput(path),
                format="forensic_raw",
            ),
        ),
    )
    with pytest.raises(ValueError, match="not bound"):
        request.read_numeric(_numeric("unrelated", plane.shape))
    with pytest.raises(ValueError, match="not bound"):
        request.read_numeric(_numeric("coefficients", (1, 2, 8, 8)))
    if length_delta:
        with pytest.raises(ValueError, match="byte length"):
            request.read_numeric(plane)
    else:
        array = request.read_numeric(plane)
        assert array.shape == plane.shape and array.dtype.str == "<i4"
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.setflags(write=True)
        with pytest.raises(ValueError):
            array[0, 0, 0, 0] = 1


def make_accepted_source(root: Path, analysis_id: str) -> AcceptedSource:
    owner = LocalTemporaryInputOwner(root)
    owned_source = owner.create(analysis_id)
    owner.ingest(owned_source, BytesIO(b"source"), 100)
    return owner.transfer(owned_source)


def make_prepared_media(
    root: Path,
    analysis_id: str,
    *,
    media_type: MediaType = MediaType.IMAGE,
    metadata: dict[str, object] | None = None,
    warnings: list[str] | None = None,
) -> tuple[PreparedMedia, PreparedArtifact, AcceptedSource, WorkspaceArtifactRegistry]:
    accepted_source = make_accepted_source(root, analysis_id)
    registry = WorkspaceArtifactRegistry(root / analysis_id)
    artifact_ref = registry.register("normalized_image", "normalized.png")
    artifact = PreparedArtifact(
        artifact_id="normalized_image",
        artifact_type="normalized_image",
        artifact_ref=artifact_ref,
        format="png",
        cleanup_required=True,
    )
    prepared_media = PreparedMedia(
        analysis_id=analysis_id,
        media_type=media_type,
        source_file_ref=PreparedSourceRef(accepted_source),
        artifacts=(artifact,),
        metadata=metadata or {},
        warnings=warnings or [],
    )
    return prepared_media, artifact, accepted_source, registry


def image_descriptor(analysis_id: str) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name=f"{analysis_id}.png",
        extension="png",
        declared_mime_type="image/png",
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=6,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=ImageTechnicalParameters(
            width=1,
            height=1,
            format="PNG",
            color_mode="RGB",
            has_metadata=False,
        ),
    )


def make_task(
    root: Path,
    analysis_id: str,
    accepted_source: AcceptedSource,
    artifacts: WorkspaceArtifactRegistry,
    stage5_data: Stage5TaskData,
) -> AnalysisTask:
    descriptor = image_descriptor(analysis_id)
    validation = ValidationResult(
        accepted=True,
        checks=[],
        errors=[],
        validated_file=descriptor,
    )
    return AnalysisTask(
        context=AnalysisContext(
            analysis_id=analysis_id,
            created_at=_CREATED_AT,
            status=AnalysisStatus.QUEUED,
            stage=ProcessingStage.REGISTERED,
            source=SourceContext(channel=SourceChannel.API),
            workspace_path=root / analysis_id,
            media_type=MediaType.IMAGE,
            config_snapshot_id="a" * 64,
        ),
        validation=validation,
        validated_file=descriptor,
        accepted_source=accepted_source,
        artifacts=artifacts,
        stage5_data=stage5_data,
    )


def cleanup_prepared(
    accepted_source: AcceptedSource,
    registry: WorkspaceArtifactRegistry,
) -> None:
    assert registry.cleanup_once().completed
    accepted_source.cleanup()


def test_stage5_internal_types_do_not_expand_public_exports() -> None:
    for module, internal_names in (
        (
            fakedetector,
            (
                "PreparedSourceRef",
                "WorkspaceArtifactRef",
                "Stage5TaskData",
                "_StoredAnalyzerResult",
                "_read_stage5_analyzer_results",
            ),
        ),
        (intake, ("PreparedSourceRef",)),
        (
            lifecycle,
            (
                "WorkspaceArtifactRef",
                "Stage5TaskData",
                "_StoredAnalyzerResult",
                "_read_stage5_analyzer_results",
            ),
        ),
        (preprocessing, ("PreparedArtifact", "PreparedMedia")),
    ):
        assert not any(hasattr(module, name) for name in internal_names)


@pytest.mark.parametrize("mutable_json", [bytearray(b"{}"), memoryview(b"{}")])
def test_stored_analyzer_result_rejects_non_bytes_storage(mutable_json: object) -> None:
    with pytest.raises(TypeError, match="immutable bytes"):
        _StoredAnalyzerResult(
            analyzer_id="fake_image_analyzer",
            media_type=MediaType.IMAGE,
            canonical_json=cast(bytes, mutable_json),
        )


def test_prepared_models_are_immutable_defensive_and_path_free(tmp_path: Path) -> None:
    metadata: dict[str, object] = {"camera": {"tags": ["original"]}}
    warnings = ["first-frame representation"]
    prepared, artifact, accepted_source, registry = make_prepared_media(
        tmp_path / "temp",
        "a" * 32,
        metadata=metadata,
        warnings=warnings,
    )
    artifact_alias = [artifact]
    prepared_from_aliases = PreparedMedia(
        analysis_id=prepared.analysis_id,
        media_type=prepared.media_type,
        source_file_ref=prepared.source_file_ref,
        artifacts=artifact_alias,
        metadata=metadata,
        warnings=warnings,
    )

    cast(dict[str, object], metadata["camera"])["tags"] = ["mutated"]
    metadata["new"] = "caller-only"
    warnings.append("caller-only")
    artifact_alias.clear()

    assert prepared_from_aliases.artifacts == (artifact,)
    assert prepared_from_aliases.metadata == {"camera": {"tags": ("original",)}}
    assert prepared_from_aliases.warnings == ("first-frame representation",)
    with pytest.raises(TypeError):
        cast(dict[str, object], prepared_from_aliases.metadata)["new"] = "blocked"
    with pytest.raises(FrozenInstanceError):
        artifact.format = "jpeg"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        prepared_from_aliases.analysis_id = "changed"  # type: ignore[misc]

    assert not any(
        isinstance(getattr(artifact, model_field.name), PurePath)
        for model_field in fields(PreparedArtifact)
    )
    assert not any(
        hasattr(value, attribute)
        for value in (artifact, prepared_from_aliases)
        for attribute in ("path", "physical_path", "workspace_path")
    )
    assert str(tmp_path) not in repr(artifact)
    assert str(tmp_path) not in repr(prepared_from_aliases)

    cleanup_prepared(accepted_source, registry)


def _tile(
    raster: np.ndarray,
    *,
    region: TileRegion | None = None,
    halo: int = 0,
    policy: ForensicResourcePolicy | None = None,
) -> ImageTile:
    height, width = raster.shape[:2]
    selected = region or TileRegion(x=0, y=0, width=width, height=height)
    kwargs = {} if policy is None else {"policy": policy}
    return extract_image_tiles(raster, (selected,), halo=halo, **kwargs)[0]


def _luminance(
    raster: np.ndarray,
    *,
    region: TileRegion | None = None,
    halo: int = 0,
) -> LuminanceTile:
    return to_luminance(_tile(raster, region=region, halo=halo))


def _readonly_float64(values: object) -> np.ndarray:
    array = np.asarray(values, dtype="<f8")
    return np.frombuffer(array.tobytes(), dtype="<f8").reshape(array.shape)


def _plane(values: object, *, halo_used: int = 0) -> KernelPlane:
    array = _readonly_float64(values)
    return KernelPlane(
        values=array,
        coverage=TileRegion(x=0, y=0, width=array.shape[1], height=array.shape[0]),
        halo_used=halo_used,
    )


@pytest.mark.parametrize(
    "shape",
    [
        (3, 4),
        (3, 4, 1),
    ],
)
def test_image_residual_luminance_accepts_explicit_grayscale_layouts(shape):
    raster = np.arange(12, dtype=np.uint8).reshape(shape)
    luminance = _luminance(raster)

    assert luminance.values.dtype == np.dtype("<f8")
    assert luminance.values.shape == (3, 4)
    np.testing.assert_array_equal(luminance.values, np.arange(12).reshape(3, 4))


def test_image_residual_luminance_uses_fixed_bt601_rgb_weights():
    raster = np.asarray([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
    luminance = _luminance(raster)

    np.testing.assert_allclose(luminance.values, [[76.245, 149.685, 29.07]], rtol=0, atol=1e-12)
    assert np.all(luminance.values >= 0.0)
    assert np.all(luminance.values <= 255.0)


def test_image_residual_rgba_alpha_is_not_a_luminance_signal():
    rgb = np.asarray([[[12, 34, 56], [78, 90, 123]]], dtype=np.uint8)
    first = np.concatenate((rgb, np.zeros((1, 2, 1), dtype=np.uint8)), axis=2)
    second = np.concatenate((rgb, np.full((1, 2, 1), 255, dtype=np.uint8)), axis=2)

    first_values = _luminance(first).values
    second_values = _luminance(second).values

    np.testing.assert_array_equal(first_values, second_values)


def test_image_residual_tile_border_is_fixed_reflect101_and_core_shape_is_preserved():
    raster = np.asarray([[1, 2], [3, 4]], dtype=np.uint8)
    tile = _tile(raster, halo=1)

    np.testing.assert_array_equal(
        tile.pixels,
        np.asarray(
            [
                [4, 3, 4, 3],
                [2, 1, 2, 1],
                [4, 3, 4, 3],
                [2, 1, 2, 1],
            ],
            dtype=np.uint8,
        ),
    )
    assert tile.region == TileRegion(x=0, y=0, width=2, height=2)
    assert tile.halo == 1


def test_image_residual_tile_extraction_supports_noncontiguous_rasters():
    source = np.arange(36, dtype=np.uint8).reshape(6, 6)
    strided = source[::2, ::2]
    assert not strided.flags.c_contiguous

    actual = _tile(strided, region=TileRegion(x=1, y=1, width=2, height=2), halo=1)
    expected = _tile(
        np.ascontiguousarray(strided),
        region=TileRegion(x=1, y=1, width=2, height=2),
        halo=1,
    )

    np.testing.assert_array_equal(actual.pixels, expected.pixels)
    assert actual.pixels.flags.c_contiguous


@pytest.mark.parametrize("kernel_size,halo", [(3, 1), (5, 2)])
def test_image_residual_smoothing_has_fixed_binomial_kernel_and_core_coverage(kernel_size, halo):
    side = 7
    raster = np.add.outer(
        np.arange(side, dtype=np.uint8) * 10,
        np.arange(side, dtype=np.uint8),
    )
    region = TileRegion(x=2, y=2, width=3, height=3)
    smoothed = smooth_luminance(
        _luminance(raster, region=region, halo=halo),
        kernel_size=kernel_size,
    )

    assert smoothed.values.shape == (3, 3)
    assert smoothed.coverage == region
    assert smoothed.halo_used == halo
    np.testing.assert_array_equal(smoothed.values, raster[2:5, 2:5])


def test_image_residual_high_pass_residual_subtracts_smoothing_without_a_forensic_threshold():
    raster = np.zeros((3, 3), dtype=np.uint8)
    raster[1, 1] = 255
    residual = high_pass_residual(
        _luminance(raster, region=TileRegion(x=1, y=1, width=1, height=1), halo=1)
    )

    assert residual.values.shape == (1, 1)
    assert residual.coverage == TileRegion(x=1, y=1, width=1, height=1)
    assert residual.halo_used == 1
    np.testing.assert_array_equal(residual.values, [[191.25]])


def test_image_residual_high_pass_of_affine_ramp_is_zero_in_the_valid_core():
    raster = np.add.outer(
        np.arange(7, dtype=np.uint8) * 10,
        np.arange(7, dtype=np.uint8),
    )
    residual = high_pass_residual(
        _luminance(raster, region=TileRegion(x=2, y=2, width=3, height=3), halo=2),
        kernel_size=5,
    )

    np.testing.assert_array_equal(residual.values, np.zeros((3, 3), dtype=np.float64))


def test_image_residual_finite_differences_are_centered_and_cover_the_core():
    raster = np.add.outer(
        np.arange(5, dtype=np.uint8) * 10,
        np.arange(5, dtype=np.uint8),
    )
    region = TileRegion(x=1, y=1, width=3, height=3)
    gradients = finite_differences(_luminance(raster, region=region, halo=1))

    assert gradients.horizontal.coverage == region
    assert gradients.vertical.coverage == region
    np.testing.assert_array_equal(gradients.horizontal.values, np.ones((3, 3)))
    np.testing.assert_array_equal(gradients.vertical.values, np.full((3, 3), 10.0))


def test_image_residual_robust_local_statistics_are_unlabelled_numeric_observations():
    statistics = robust_local_statistics(_plane([[0.0, 1.0], [2.0, 100.0]]))

    assert statistics == RobustLocalStatistics(
        sample_count=4,
        median=1.5,
        median_absolute_deviation=1.0,
        lower_quartile=0.75,
        upper_quartile=26.5,
    )


def test_image_residual_identical_input_produces_bit_identical_results():
    raster = np.arange(8 * 9 * 4, dtype=np.uint8).reshape(8, 9, 4)
    region = TileRegion(x=2, y=2, width=5, height=4)

    def observe() -> tuple[np.ndarray, ...]:
        luminance = _luminance(raster, region=region, halo=2)
        gradients = finite_differences(luminance)
        return (
            luminance.values,
            smooth_luminance(luminance, kernel_size=5).values,
            high_pass_residual(luminance, kernel_size=5).values,
            gradients.horizontal.values,
            gradients.vertical.values,
        )

    first = observe()
    second = observe()
    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))


def test_image_residual_all_array_outputs_have_immutable_bytes_backing():
    tile = _tile(np.arange(25, dtype=np.uint8).reshape(5, 5), halo=2)
    luminance = to_luminance(tile)
    smoothed = smooth_luminance(luminance, kernel_size=5)
    residual = high_pass_residual(luminance, kernel_size=5)
    gradients = finite_differences(luminance)

    arrays = (
        tile.pixels,
        luminance.values,
        smoothed.values,
        residual.values,
        gradients.horizontal.values,
        gradients.vertical.values,
    )
    for array in arrays:
        assert not array.flags.writeable
        assert array.flags.c_contiguous
        with pytest.raises(ValueError):
            array.setflags(write=True)


@pytest.mark.parametrize(
    "raster",
    [
        np.zeros((1, 1), dtype=np.uint16),
        np.zeros((1, 1), dtype=np.float32),
        np.asarray([[np.nan]], dtype=np.float64),
        np.asarray([[np.inf]], dtype=np.float64),
        np.zeros((1, 1), dtype=np.bool_),
    ],
)
def test_image_residual_raster_rejects_every_dtype_except_uint8(raster):
    with pytest.raises(TypeError):
        _tile(raster)


@pytest.mark.parametrize(
    "raster",
    [
        np.empty((0, 1), dtype=np.uint8),
        np.empty((1, 0), dtype=np.uint8),
        np.empty((1,), dtype=np.uint8),
        np.empty((1, 1, 2), dtype=np.uint8),
        np.empty((1, 1, 5), dtype=np.uint8),
        np.empty((1, 1, 1, 1), dtype=np.uint8),
    ],
)
def test_image_residual_raster_rejects_empty_or_unsupported_shapes(raster):
    with pytest.raises(ValueError):
        extract_image_tiles(raster, (TileRegion(0, 0, 1, 1),), halo=0)


@pytest.mark.parametrize(
    "values",
    [
        (-1, 0, 1, 1),
        (0, -1, 1, 1),
        (0, 0, 0, 1),
        (0, 0, 1, 0),
        (True, 0, 1, 1),
        (0, 0, False, 1),
    ],
)
def test_image_residual_tile_region_rejects_invalid_coordinates_and_dimensions(values):
    with pytest.raises(ValueError):
        TileRegion(*values)


def test_image_residual_tile_request_rejects_invalid_collection_and_coverage():
    raster = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(TypeError):
        extract_image_tiles(raster, [TileRegion(0, 0, 1, 1)], halo=0)
    with pytest.raises(ValueError):
        extract_image_tiles(raster, (), halo=0)
    with pytest.raises(TypeError):
        extract_image_tiles(raster, (object(),), halo=0)
    with pytest.raises(ValueError):
        extract_image_tiles(raster, (TileRegion(3, 3, 2, 2),), halo=0)
    with pytest.raises(ValueError):
        extract_image_tiles(raster, (TileRegion(1 << 63, 0, 1, 1),), halo=0)


def test_image_residual_raster_pixel_limit_accepts_below_and_at_but_rejects_above():
    limit = 1 << 22
    scalar = np.zeros((1, 1), dtype=np.uint8)
    for width in (limit - 1, limit):
        raster = np.broadcast_to(scalar, (1, width))
        assert _tile(raster, region=TileRegion(0, 0, 1, 1)).pixels.shape == (1, 1)
    with pytest.raises(ValueError):
        _tile(
            np.broadcast_to(scalar, (1, limit + 1)),
            region=TileRegion(0, 0, 1, 1),
        )


def test_image_residual_tile_side_limit_accepts_below_and_at_but_rejects_above():
    raster = np.zeros((513, 513), dtype=np.uint8)
    for side in (511, 512):
        tile = _tile(raster, region=TileRegion(0, 0, side, side))
        assert tile.pixels.shape == (side, side)
    with pytest.raises(ValueError):
        _tile(raster, region=TileRegion(0, 0, 513, 513))


def test_image_residual_tile_count_and_halo_limits_are_enforced_at_the_boundary():
    raster = np.zeros((3, 3), dtype=np.uint8)
    region = TileRegion(1, 1, 1, 1)
    for count in (15, 16):
        assert len(extract_image_tiles(raster, (region,) * count, halo=2)) == count
    with pytest.raises(ValueError):
        extract_image_tiles(raster, (region,) * 17, halo=2)
    for halo in (0, 1, 2):
        assert _tile(raster, region=region, halo=halo).pixels.shape == (
            1 + 2 * halo,
            1 + 2 * halo,
        )
    with pytest.raises(ValueError):
        _tile(raster, region=region, halo=3)


def test_image_residual_workspace_preflight_happens_before_luminance_allocation():
    tile = _tile(np.zeros((1, 1), dtype=np.uint8))
    with pytest.raises(ValueError):
        to_luminance(tile, policy=ForensicResourcePolicy(residual_workspace_bytes=15))
    result = to_luminance(tile, policy=ForensicResourcePolicy(residual_workspace_bytes=16))
    assert result.values.shape == (1, 1)


def test_image_residual_tile_workspace_counts_retained_outputs_and_largest_temporary():
    raster = np.zeros((1, 1), dtype=np.uint8)
    region = TileRegion(0, 0, 1, 1)
    with pytest.raises(ValueError):
        extract_image_tiles(
            raster,
            (region,),
            halo=0,
            policy=ForensicResourcePolicy(residual_workspace_bytes=1),
        )
    result = extract_image_tiles(
        raster,
        (region,),
        halo=0,
        policy=ForensicResourcePolicy(residual_workspace_bytes=2),
    )
    assert result[0].pixels.shape == (1, 1)


@pytest.mark.parametrize("kernel_size", [True, 1, 4, 6])
def test_image_residual_smoothing_rejects_unsupported_kernel_sizes(kernel_size):
    tile = _luminance(np.zeros((5, 5), dtype=np.uint8), halo=2)
    with pytest.raises(ValueError):
        smooth_luminance(tile, kernel_size=kernel_size)


def test_image_residual_kernels_reject_insufficient_halo_and_wrong_input_types():
    luminance = _luminance(np.zeros((3, 3), dtype=np.uint8), halo=0)
    with pytest.raises(ValueError):
        smooth_luminance(luminance)
    with pytest.raises(ValueError):
        high_pass_residual(luminance)
    with pytest.raises(ValueError):
        finite_differences(luminance)
    with pytest.raises(TypeError):
        to_luminance(object())
    with pytest.raises(TypeError):
        smooth_luminance(object())
    with pytest.raises(TypeError):
        robust_local_statistics(object())


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_image_residual_numeric_planes_reject_nan_and_infinity(value):
    with pytest.raises(ValueError):
        LuminanceTile(
            values=_readonly_float64([[value]]),
            region=TileRegion(0, 0, 1, 1),
            halo=0,
        )


def test_image_residual_numeric_planes_reject_wrong_range_dtype_layout_and_mutable_backing():
    region = TileRegion(0, 0, 2, 2)
    with pytest.raises(ValueError):
        LuminanceTile(values=_readonly_float64([[-1.0, 0.0], [1.0, 2.0]]), region=region, halo=0)
    with pytest.raises(ValueError):
        LuminanceTile(values=_readonly_float64([[256.0, 0.0], [1.0, 2.0]]), region=region, halo=0)
    with pytest.raises(ValueError):
        LuminanceTile(values=np.zeros((2, 2), dtype=np.float32), region=region, halo=0)
    with pytest.raises(ValueError):
        LuminanceTile(values=np.zeros((2, 2), dtype=np.float64), region=region, halo=0)
    with pytest.raises(ValueError):
        LuminanceTile(values=_readonly_float64([[1.0, 2.0], [3.0, 4.0]]).T, region=region, halo=0)


def test_image_residual_internal_value_objects_reject_inconsistent_layouts():
    region = TileRegion(0, 0, 1, 1)
    pixels = np.frombuffer(b"\x00", dtype=np.uint8).reshape(1, 1)
    with pytest.raises(ValueError):
        ImageTile(pixels=pixels, region=region, halo=-1)
    with pytest.raises(ValueError):
        ImageTile(pixels=np.zeros((1, 1), dtype=np.uint8), region=region, halo=0)
    with pytest.raises(ValueError):
        KernelPlane(values=_readonly_float64([[1.0, 2.0]]), coverage=region, halo_used=0)
    plane = _plane([[1.0]], halo_used=1)
    with pytest.raises(ValueError):
        GradientPlanes(horizontal=plane, vertical=replace(plane, halo_used=0))


@pytest.mark.parametrize(
    "updates",
    [
        {"sample_count": 0},
        {"median": float("nan")},
        {"median_absolute_deviation": -1.0},
        {"lower_quartile": 2.0, "upper_quartile": 1.0},
    ],
)
def test_image_residual_robust_statistics_value_object_rejects_invalid_values(updates):
    values = {
        "sample_count": 1,
        "median": 0.0,
        "median_absolute_deviation": 0.0,
        "lower_quartile": 0.0,
        "upper_quartile": 0.0,
    }
    values.update(updates)
    with pytest.raises(ValueError):
        RobustLocalStatistics(**values)


def test_image_residual_policy_model_still_rejects_a_workspace_above_the_global_ceiling():
    with pytest.raises(ValidationError):
        ForensicResourcePolicy(residual_workspace_bytes=(32 << 20) + 1)


def test_prepared_media_rejects_source_mismatch_and_conflicting_artifact_ids(
    tmp_path: Path,
) -> None:
    prepared, artifact, accepted_source, registry = make_prepared_media(
        tmp_path / "temp",
        "b" * 32,
    )

    with pytest.raises(ValueError, match="source identity"):
        PreparedMedia(
            analysis_id="c" * 32,
            media_type=MediaType.IMAGE,
            source_file_ref=prepared.source_file_ref,
        )
    with pytest.raises(ValueError, match="conflicting IDs"):
        PreparedMedia(
            analysis_id=prepared.analysis_id,
            media_type=MediaType.IMAGE,
            source_file_ref=prepared.source_file_ref,
            artifacts=(artifact, artifact),
        )

    cleanup_prepared(accepted_source, registry)


@pytest.mark.parametrize(
    "unsafe_metadata",
    [Path("metadata.txt"), PurePath("metadata.txt"), b"binary", bytearray(b"binary")],
    ids=["path", "pure-path", "bytes", "bytearray"],
)
def test_prepared_media_rejects_path_and_binary_metadata(
    tmp_path: Path,
    unsafe_metadata: object,
) -> None:
    analysis_id = "c" * 32
    accepted_source = make_accepted_source(tmp_path / "temp", analysis_id)

    with pytest.raises(TypeError, match="paths or binary data"):
        PreparedMedia(
            analysis_id=analysis_id,
            media_type=MediaType.IMAGE,
            source_file_ref=PreparedSourceRef(accepted_source),
            metadata={"unsafe": unsafe_metadata},
        )

    accepted_source.cleanup()


def test_stage5_task_data_is_hidden_from_task_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    analysis_id = "d" * 32
    prepared, _artifact, accepted_source, registry = make_prepared_media(root, analysis_id)
    stage5_data = Stage5TaskData(prepared_media=prepared, analyzer_results=[])
    task = make_task(root, analysis_id, accepted_source, registry, stage5_data)

    snapshot = task.snapshot()

    assert task.stage5_data is stage5_data
    assert stage5_data.analyzer_results == ()
    assert "stage5_data" not in {model_field.name for model_field in fields(TaskSnapshot)}
    assert not hasattr(snapshot, "stage5_data")
    assert str(tmp_path) not in repr(snapshot)

    cleanup_prepared(accepted_source, registry)


def test_analysis_task_rejects_stage5_analysis_id_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    task_id = "e" * 32
    stage5_id = "f" * 32
    _task_prepared, _artifact, task_source, task_registry = make_prepared_media(root, task_id)
    stage5_prepared, _artifact, stage5_source, stage5_registry = make_prepared_media(
        root,
        stage5_id,
    )

    with pytest.raises(ValueError, match="Stage 5 identity"):
        make_task(
            root,
            task_id,
            task_source,
            task_registry,
            Stage5TaskData(prepared_media=stage5_prepared),
        )

    cleanup_prepared(task_source, task_registry)
    cleanup_prepared(stage5_source, stage5_registry)


def test_analysis_task_rejects_stage5_media_type_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    analysis_id = "1" * 32
    prepared, _artifact, accepted_source, registry = make_prepared_media(
        root,
        analysis_id,
        media_type=MediaType.AUDIO,
    )

    with pytest.raises(ValueError, match="Stage 5 media type"):
        make_task(
            root,
            analysis_id,
            accepted_source,
            registry,
            Stage5TaskData(prepared_media=prepared),
        )

    cleanup_prepared(accepted_source, registry)


def test_analysis_task_rejects_different_source_capability_with_same_analysis_id(
    tmp_path: Path,
) -> None:
    analysis_id = "2" * 32
    task_root = tmp_path / "task"
    _prepared, artifact, task_source, task_registry = make_prepared_media(
        task_root,
        analysis_id,
    )
    foreign_source = make_accepted_source(tmp_path / "foreign", analysis_id)
    foreign_prepared = PreparedMedia(
        analysis_id=analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=PreparedSourceRef(foreign_source),
        artifacts=(artifact,),
    )

    with pytest.raises(ValueError, match="source capability"):
        make_task(
            task_root,
            analysis_id,
            task_source,
            task_registry,
            Stage5TaskData(prepared_media=foreign_prepared),
        )

    cleanup_prepared(task_source, task_registry)
    foreign_source.cleanup()


def test_analysis_task_rejects_artifact_ref_from_foreign_registry(tmp_path: Path) -> None:
    analysis_id = "3" * 32
    task_root = tmp_path / "task"
    prepared, _artifact, accepted_source, task_registry = make_prepared_media(
        task_root,
        analysis_id,
    )
    foreign_registry = WorkspaceArtifactRegistry(tmp_path / "foreign")
    foreign_ref = foreign_registry.register("normalized_image", "normalized.png")
    foreign_artifact = PreparedArtifact(
        artifact_id="normalized_image",
        artifact_type="normalized_image",
        artifact_ref=foreign_ref,
        format="png",
    )
    foreign_prepared = PreparedMedia(
        analysis_id=analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=prepared.source_file_ref,
        artifacts=(foreign_artifact,),
    )

    with pytest.raises(ValueError, match="artifact capability"):
        make_task(
            task_root,
            analysis_id,
            accepted_source,
            task_registry,
            Stage5TaskData(prepared_media=foreign_prepared),
        )

    cleanup_prepared(accepted_source, task_registry)
    assert foreign_registry.cleanup_once().completed


def test_analysis_task_rejects_artifact_id_that_does_not_match_ref(tmp_path: Path) -> None:
    analysis_id = "4" * 32
    task_root = tmp_path / "task"
    prepared, artifact, accepted_source, registry = make_prepared_media(task_root, analysis_id)
    mismatched_artifact = PreparedArtifact(
        artifact_id="declared_other_artifact",
        artifact_type=artifact.artifact_type,
        artifact_ref=artifact.artifact_ref,
        format=artifact.format,
    )
    mismatched_prepared = PreparedMedia(
        analysis_id=analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=prepared.source_file_ref,
        artifacts=(mismatched_artifact,),
    )

    with pytest.raises(ValueError, match="artifact capability"):
        make_task(
            task_root,
            analysis_id,
            accepted_source,
            registry,
            Stage5TaskData(prepared_media=mismatched_prepared),
        )

    cleanup_prepared(accepted_source, registry)
