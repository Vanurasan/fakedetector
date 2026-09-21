"""Stage 5 Increment 3 preprocessing behavior and capability invariants."""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import wave
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path, PurePath
from typing import BinaryIO, TypeVar, cast

import numpy as np
import pytest
import yaml
from PIL import Image, PngImagePlugin
from pydantic import BaseModel

import fakedetector.preprocessing as preprocessing
from fakedetector._generated_artifact_budget import _GeneratedArtifactBudget
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import (
    AppConfig,
    AudioPreprocessingConfig,
    ImagePreprocessingConfig,
    VideoPreprocessingConfig,
)
from fakedetector.core._bounded_process import (
    ProcessInfrastructureError,
    ProcessOutputLimitError,
    ProcessResult,
    ProcessTimeoutError,
)
from fakedetector.domain import (
    AudioTechnicalParameters,
    ImageTechnicalParameters,
    MediaType,
    ValidatedFileDescriptor,
    VideoTechnicalParameters,
)
from fakedetector.intake.media_tools import FFmpegMediaInspector, audio_parameters, video_parameters
from fakedetector.intake.temporary_input import (
    AcceptedSource,
    LocalTemporaryInputOwner,
    PreparedSourceRef,
)
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRef, WorkspaceArtifactRegistry
from fakedetector.preprocessing import _media_tools as decoder
from fakedetector.preprocessing._errors import PreprocessingError
from fakedetector.preprocessing._media_tools import (
    _FFmpegPreprocessingTool,
    _parse_jpeg,
    decode_audio_window,
    frame_audio,
    frequency_bins,
    periodic_hann,
    probe_audio,
    select_audio_windows,
    stft_batches,
)
from fakedetector.preprocessing._models import (
    AudioWindowDescriptor,
    ForensicManifest,
    ForensicRepresentation,
    IndexRange,
    JpegCoefficientsDescriptor,
    OriginalImageFacts,
    PreparedArtifact,
    PreparedMedia,
    RepresentationProvenance,
    SpectralWindowDescriptor,
    StreamTimingFacts,
    TimeBase,
    TimingInterval,
    TimingRate,
    TimingRecordsDescriptor,
)
from fakedetector.preprocessing._requirements import (
    ForensicCapability,
    ForensicResourcePolicy,
    PreprocessingRequirements,
)
from fakedetector.preprocessing._service import (
    AudioPreprocessor,
    ImagePreprocessor,
    PreprocessingDispatcher,
    PreprocessingRequest,
    VideoPreprocessor,
    _prepare_timing_forensic,
    _video_timestamps,
)

_OperationResult = TypeVar("_OperationResult")


class RecordingArtifactRegistry(WorkspaceArtifactRegistry):
    """Record capability ordering without widening production artifact access."""

    def __init__(self, workspace_path: Path) -> None:
        super().__init__(workspace_path)
        self.events: list[tuple[str, str, bool | None]] = []
        self._ids_by_ref: dict[int, str] = {}

    def register(self, artifact_id: str, relative_path: str) -> WorkspaceArtifactRef:
        artifact_ref = super().register(artifact_id, relative_path)
        self._ids_by_ref[id(artifact_ref)] = artifact_id
        self.events.append(("register", artifact_id, None))
        return artifact_ref

    def with_local_artifact_path(
        self,
        artifact_ref: WorkspaceArtifactRef,
        trusted_operation: Callable[[Path], _OperationResult],
    ) -> _OperationResult:
        artifact_id = self._ids_by_ref[id(artifact_ref)]

        def recorded(path: Path) -> _OperationResult:
            self.events.append(("access", artifact_id, path.exists()))
            return trusted_operation(path)

        return super().with_local_artifact_path(artifact_ref, recorded)


class _NoWriteMediaTool:
    def __init__(self) -> None:
        self.calls = 0

    def normalized_audio(self, *_args: object, **_kwargs: object) -> None:
        self.calls += 1

    def audio_fragment(self, *_args: object, **_kwargs: object) -> None:
        self.calls += 1

    def spectrogram(self, *_args: object, **_kwargs: object) -> None:
        self.calls += 1


@dataclass(slots=True)
class PreparedCase:
    request: PreprocessingRequest
    accepted_source: AcceptedSource
    registry: RecordingArtifactRegistry

    def cleanup(self) -> None:
        assert self.registry.cleanup_once().completed
        self.accepted_source.cleanup()


def _case(
    tmp_path: Path,
    source_path: Path,
    descriptor: ValidatedFileDescriptor,
    *,
    analysis_id: str = "a" * 32,
) -> PreparedCase:
    root = tmp_path / "temp"
    owner = LocalTemporaryInputOwner(root)
    owned_source = owner.create(analysis_id)
    with source_path.open("rb") as source:
        owner.ingest(owned_source, source, source_path.stat().st_size + 1)
    accepted_source = owner.transfer(owned_source)
    registry = RecordingArtifactRegistry(root / analysis_id)
    return PreparedCase(
        request=PreprocessingRequest(
            analysis_id=analysis_id,
            validated_file=descriptor,
            source_file_ref=PreparedSourceRef(accepted_source),
            artifact_registry=registry,
            artifact_budget=_artifact_budget(descriptor.media_type),
        ),
        accepted_source=accepted_source,
        registry=registry,
    )


def _image_descriptor(
    *,
    width: int,
    height: int,
    image_format: str,
    color_mode: str,
    frame_count: int = 1,
    has_metadata: bool = False,
    original_name: str = "image.png",
) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name=original_name,
        extension=original_name.rsplit(".", maxsplit=1)[-1],
        declared_mime_type=None,
        detected_mime_type=f"image/{image_format.lower()}",
        media_type=MediaType.IMAGE,
        size_bytes=1,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=ImageTechnicalParameters(
            width=width,
            height=height,
            format=image_format,
            color_mode=color_mode,
            frame_count=frame_count,
            has_metadata=has_metadata,
        ),
    )


def _audio_descriptor(
    *,
    duration_seconds: float,
    sample_rate_hz: int,
    channels: int,
    codec: str = "pcm_s16le",
) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name="audio.wav",
        extension="wav",
        declared_mime_type=None,
        detected_mime_type="audio/wav",
        media_type=MediaType.AUDIO,
        size_bytes=1,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=AudioTechnicalParameters(
            duration_seconds=duration_seconds,
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            codec=codec,
        ),
    )


def _video_descriptor(
    *,
    duration_seconds: float,
    width: int,
    height: int,
    fps: float,
    has_audio: bool,
) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name="video.mp4",
        extension="mp4",
        declared_mime_type=None,
        detected_mime_type="video/mp4",
        media_type=MediaType.VIDEO,
        size_bytes=1,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=VideoTechnicalParameters(
            duration_seconds=duration_seconds,
            container="mp4",
            video_codec="mpeg4",
            audio_codec="aac" if has_audio else None,
            width=width,
            height=height,
            fps=fps,
            has_audio=has_audio,
        ),
    )


def _artifact_path(
    registry: WorkspaceArtifactRegistry,
    artifact: PreparedArtifact,
) -> Path:
    return registry.with_local_artifact_path(artifact.artifact_ref, lambda path: path)


def _artifact_budget(
    media_type: MediaType,
    *,
    max_size_mb: int | None = None,
) -> _GeneratedArtifactBudget:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    if max_size_mb is not None:
        raw["limits"]["max_file_size_mb"][media_type.value] = max_size_mb
    config = AppConfig.model_validate(raw)
    return _GeneratedArtifactBudget(_ConfigSnapshot.capture(config), media_type)


def _assert_registered_before_first_access(
    prepared: PreparedMedia,
    registry: RecordingArtifactRegistry,
) -> None:
    for artifact in prepared.artifacts:
        registration = registry.events.index(("register", artifact.artifact_id, None))
        first_access = next(
            index
            for index, event in enumerate(registry.events)
            if event[0] == "access" and event[1] == artifact.artifact_id
        )
        assert registration < first_access
        assert registry.events[first_access][2] is False


def _png_chunk_types(path: Path) -> list[bytes]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    chunks = []
    while offset < len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunks.append(data[offset + 4 : offset + 8])
        offset += length + 12
    assert offset == len(data)
    return chunks


@pytest.mark.parametrize(
    ("mode", "pixel", "expected_mode"),
    [
        ("RGB", (10, 20, 30), "RGB"),
        ("RGBA", (10, 20, 30, 40), "RGBA"),
        ("RGBA", (10, 20, 30, 255), "RGB"),
    ],
)
def test_image_normalizes_png_without_resize_and_keeps_only_required_alpha(
    tmp_path: Path,
    mode: str,
    pixel: tuple[int, ...],
    expected_mode: str,
) -> None:
    source_path = tmp_path / "source.png"
    with Image.new(mode, (7, 5), pixel) as image:
        image.save(source_path, format="PNG")
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=7, height=5, image_format="PNG", color_mode=mode),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    assert prepared.analysis_id == case.request.analysis_id
    assert prepared.media_type is MediaType.IMAGE
    assert prepared.source_file_ref is case.request.source_file_ref
    assert len(prepared.artifacts) == 1
    normalized_path = _artifact_path(case.registry, prepared.artifacts[0])
    with Image.open(normalized_path) as normalized:
        normalized.load()
        assert normalized.format == "PNG"
        assert normalized.size == (7, 5)
        assert normalized.mode == expected_mode
        assert normalized.getpixel((0, 0)) == pixel[: len(expected_mode)]
    assert case.request.artifact_budget.used_bytes == normalized_path.stat().st_size
    assert prepared.metadata["normalized"] == {
        "format": "png",
        "mode": expected_mode,
        "width": 7,
        "height": 5,
        "scope": "first_frame",
    }
    _assert_registered_before_first_access(prepared, case.registry)
    case.cleanup()


@pytest.mark.parametrize(
    ("mode", "pixels", "transparency", "expected_pixels"),
    [
        (
            "RGB",
            [(10, 20, 30), (40, 50, 60)],
            (10, 20, 30),
            [(10, 20, 30, 0), (40, 50, 60, 255)],
        ),
        (
            "L",
            [10, 40],
            10,
            [(10, 10, 10, 0), (40, 40, 40, 255)],
        ),
    ],
)
def test_png_trns_is_materialized_as_rgba_pixels_without_raw_metadata(
    tmp_path: Path,
    mode: str,
    pixels: list[int] | list[tuple[int, int, int]],
    transparency: int | tuple[int, int, int],
    expected_pixels: list[tuple[int, int, int, int]],
) -> None:
    source_path = tmp_path / "source.png"
    with Image.new(mode, (2, 1)) as image:
        image.putdata(pixels)
        image.save(source_path, format="PNG", transparency=transparency)
    assert b"tRNS" in _png_chunk_types(source_path)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=2, height=1, image_format="PNG", color_mode=mode),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    normalized_path = _artifact_path(case.registry, prepared.artifacts[0])
    with Image.open(normalized_path) as normalized:
        normalized.load()
        assert normalized.mode == "RGBA"
        assert list(normalized.get_flattened_data()) == expected_pixels
        assert normalized.info == {}
    assert b"tRNS" not in _png_chunk_types(normalized_path)
    case.cleanup()


def test_palette_png_transparency_is_materialized_as_rgba_pixels(tmp_path: Path) -> None:
    source_path = tmp_path / "palette.png"
    palette = [255, 0, 0, 0, 255, 0] + [0] * (256 * 3 - 6)
    with Image.new("P", (2, 1)) as image:
        image.putpalette(palette)
        image.putdata([0, 1])
        image.save(source_path, format="PNG", transparency=0)
    assert b"tRNS" in _png_chunk_types(source_path)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=2, height=1, image_format="PNG", color_mode="P"),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    normalized_path = _artifact_path(case.registry, prepared.artifacts[0])
    with Image.open(normalized_path) as normalized:
        normalized.load()
        assert normalized.mode == "RGBA"
        assert list(normalized.get_flattened_data()) == [
            (255, 0, 0, 0),
            (0, 255, 0, 255),
        ]
        assert normalized.info == {}
    assert b"tRNS" not in _png_chunk_types(normalized_path)
    case.cleanup()


def test_image_applies_exif_orientation(tmp_path: Path) -> None:
    source_path = tmp_path / "oriented.jpg"
    exif = Image.Exif()
    exif[274] = 6
    with Image.new("RGB", (6, 4), (1, 2, 3)) as image:
        image.save(source_path, format="JPEG", exif=exif)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(
            width=6,
            height=4,
            image_format="JPEG",
            color_mode="RGB",
            original_name="image.jpg",
        ),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    with Image.open(_artifact_path(case.registry, prepared.artifacts[0])) as normalized:
        assert normalized.size == (4, 6)
    assert cast(dict[str, object], prepared.metadata["normalized"])["width"] == 4
    case.cleanup()


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_normalized_png_strips_raw_metadata_and_preserves_oriented_pixels_and_facts(
    tmp_path: Path, mode: str
) -> None:
    source_path = tmp_path / "metadata.png"
    icc = b"source-raw-icc-profile"
    xmp = "<x:xmpmeta>source-raw-xmp</x:xmpmeta>"
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "source-raw-exif-description"
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_itxt("XML:com.adobe.xmp", xmp)
    pixels = [(value, value + 1, value + 2) for value in range(10, 70, 10)]
    if mode == "RGBA":
        pixels = [(*pixel, 100) for pixel in pixels]
    with Image.new(mode, (3, 2)) as image:
        image.putdata(pixels)
        image.save(source_path, format="PNG", exif=exif, icc_profile=icc, pnginfo=pnginfo)

    with Image.open(source_path) as source:
        source.load()
        assert source.info["icc_profile"] == icc
        assert source.info["XML:com.adobe.xmp"] == xmp
        assert source.getexif()[270] == "source-raw-exif-description"
        assert source.getexif()[274] == 6
        descriptor = _image_descriptor(
            width=source.width,
            height=source.height,
            image_format=source.format,
            color_mode=source.mode,
            frame_count=source.n_frames,
            has_metadata=bool(source.info),
        )
    case = _case(tmp_path, source_path, descriptor)

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request, PreprocessingRequirements()
    )

    normalized_path = _artifact_path(case.registry, prepared.artifacts[0])
    with Image.open(normalized_path) as normalized:
        normalized.load()
        assert normalized.format == "PNG"
        assert normalized.mode == mode
        assert normalized.size == (2, 3)
        assert list(normalized.get_flattened_data()) == [pixels[i] for i in (3, 0, 4, 1, 5, 2)]
        assert normalized.info == {}
        assert not normalized.getexif()
        assert normalized.n_frames == 1
    chunks = _png_chunk_types(normalized_path)
    assert chunks[0] == b"IHDR"
    assert chunks[-1] == b"IEND"
    assert set(chunks) == {b"IHDR", b"IDAT", b"IEND"}
    assert prepared.metadata["source"] == {
        "width": 3,
        "height": 2,
        "frame_count": 1,
        "format": "PNG",
        "color_mode": mode,
        "has_metadata": True,
    }
    assert prepared.metadata["normalized"] == {
        "format": "png",
        "mode": mode,
        "width": 2,
        "height": 3,
        "scope": "first_frame",
    }
    assert prepared.warnings == ()
    _assert_registered_before_first_access(prepared, case.registry)
    case.cleanup()


def test_apng_with_separate_default_uses_first_animation_frame_and_warns(tmp_path: Path) -> None:
    source_path = tmp_path / "animated.png"
    with (
        Image.new("RGB", (5, 4), (255, 0, 0)) as default,
        Image.new("RGB", (5, 4), (0, 255, 0)) as first,
        Image.new("RGB", (5, 4), (0, 0, 255)) as second,
    ):
        default.save(
            source_path,
            format="PNG",
            save_all=True,
            append_images=[first, second],
            default_image=True,
            duration=[100, 100],
            loop=0,
        )
    with Image.open(source_path) as source:
        assert source.default_image is True
        assert source.n_frames == 3
        assert source.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
        source.seek(1)
        assert source.convert("RGB").getpixel((0, 0)) == (0, 255, 0)
        source.seek(2)
        assert source.convert("RGB").getpixel((0, 0)) == (0, 0, 255)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(
            width=5,
            height=4,
            image_format="PNG",
            color_mode="RGB",
            frame_count=3,
        ),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    with Image.open(_artifact_path(case.registry, prepared.artifacts[0])) as normalized:
        assert normalized.mode == "RGB"
        assert normalized.getpixel((0, 0)) == (0, 255, 0)
    assert cast(dict[str, object], prepared.metadata["source"])["frame_count"] == 3
    assert prepared.metadata["frame_scope"] == "first_frame"
    assert len(prepared.warnings) == 1
    case.cleanup()


def test_apng_without_separate_default_uses_first_animation_frame_and_warns(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "animated.png"
    with (
        Image.new("RGB", (5, 4), (255, 0, 0)) as first,
        Image.new("RGB", (5, 4), (0, 0, 255)) as second,
    ):
        first.save(
            source_path,
            format="PNG",
            save_all=True,
            append_images=[second],
            duration=100,
            loop=0,
        )
    with Image.open(source_path) as source:
        assert source.default_image is False
        assert source.n_frames == 2
        assert source.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(
            width=5,
            height=4,
            image_format="PNG",
            color_mode="RGB",
            frame_count=2,
        ),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    with Image.open(_artifact_path(case.registry, prepared.artifacts[0])) as normalized:
        assert normalized.mode == "RGB"
        assert normalized.getpixel((0, 0)) == (255, 0, 0)
    assert cast(dict[str, object], prepared.metadata["source"])["frame_count"] == 2
    assert prepared.metadata["frame_scope"] == "first_frame"
    assert len(prepared.warnings) == 1
    assert "temporal behavior" in prepared.warnings[0]
    case.cleanup()


def test_animated_gif_keeps_first_frame_semantics(tmp_path: Path) -> None:
    source_path = tmp_path / "animated.gif"
    with (
        Image.new("RGB", (5, 4), (255, 0, 0)) as first,
        Image.new("RGB", (5, 4), (0, 0, 255)) as second,
    ):
        first.save(
            source_path,
            format="GIF",
            save_all=True,
            append_images=[second],
            duration=100,
            loop=0,
        )
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(
            width=5,
            height=4,
            image_format="GIF",
            color_mode="P",
            frame_count=2,
            original_name="animated.gif",
        ),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    with Image.open(_artifact_path(case.registry, prepared.artifacts[0])) as normalized:
        assert normalized.mode == "RGB"
        assert normalized.getpixel((0, 0)) == (255, 0, 0)
    assert cast(dict[str, object], prepared.metadata["source"])["frame_count"] == 2
    assert len(prepared.warnings) == 1
    case.cleanup()


def test_corrupt_image_is_a_safe_controlled_failure(tmp_path: Path) -> None:
    source_path = tmp_path / "corrupt.png"
    source_path.write_bytes(b"not-an-image")
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=1, height=1, image_format="PNG", color_mode="RGB"),
    )

    with pytest.raises(PreprocessingError) as caught:
        ImagePreprocessor(ImagePreprocessingConfig()).prepare(
            case.request,
            PreprocessingRequirements(),
        )

    assert caught.value.kind == "decode"
    assert caught.value.phase == "image_decode"
    assert str(tmp_path) not in str(caught.value)
    assert case.registry.cleanup_obligations() == ()
    case.cleanup()


@pytest.mark.parametrize("extract_metadata", [True, False])
def test_image_normalization_is_created_with_optional_metadata_enabled_or_disabled(
    tmp_path: Path, extract_metadata: bool
) -> None:
    source_path = tmp_path / "source.png"
    with Image.new("RGB", (2, 2)) as image:
        image.save(source_path)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=2, height=2, image_format="PNG", color_mode="RGB"),
    )

    prepared = ImagePreprocessor(
        ImagePreprocessingConfig(normalize_for_analysis=True, extract_metadata=extract_metadata)
    ).prepare(case.request, PreprocessingRequirements())

    assert len(prepared.artifacts) == 1
    assert prepared.artifacts[0].artifact_type == "normalized_image"
    assert _artifact_path(case.registry, prepared.artifacts[0]).is_file()
    assert "normalized" in prepared.metadata
    assert prepared.metadata["frame_scope"] == "first_frame"
    assert ("has_metadata" in prepared.metadata["source"]) is extract_metadata
    _assert_registered_before_first_access(prepared, case.registry)
    case.cleanup()


def test_artifact_write_failure_keeps_registered_cleanup_obligation(tmp_path: Path) -> None:
    source_path = tmp_path / "source.png"
    with Image.new("RGB", (2, 2)) as image:
        image.save(source_path)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=2, height=2, image_format="PNG", color_mode="RGB"),
    )
    preexisting = tmp_path / "temp" / ("a" * 32) / "preprocessing" / "image"
    preexisting.mkdir(parents=True)
    (preexisting / "normalized.png").write_bytes(b"partial")

    with pytest.raises(PreprocessingError) as caught:
        ImagePreprocessor(ImagePreprocessingConfig()).prepare(
            case.request,
            PreprocessingRequirements(),
        )

    assert caught.value.kind == "artifact_write"
    assert len(case.registry.cleanup_obligations()) == 1
    case.cleanup()


def test_mandatory_normalized_image_respects_remaining_byte_budget(tmp_path: Path) -> None:
    source_path = tmp_path / "source.png"
    with Image.new("RGB", (2, 2)) as image:
        image.save(source_path)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=2, height=2, image_format="PNG", color_mode="RGB"),
    )
    budget = _artifact_budget(MediaType.IMAGE, max_size_mb=1)
    prior_ref = case.registry.register("prior_output", "preprocessing/prior.bin")

    def consume_budget(path: Path) -> None:
        with budget.open_output(path) as output:
            output.write(b"x" * (budget.max_bytes - 32))

    case.registry.with_local_artifact_path(prior_ref, consume_budget)
    request = PreprocessingRequest(
        analysis_id=case.request.analysis_id,
        validated_file=case.request.validated_file,
        source_file_ref=case.request.source_file_ref,
        artifact_registry=case.registry,
        artifact_budget=budget,
    )

    with pytest.raises(PreprocessingError) as caught:
        ImagePreprocessor(ImagePreprocessingConfig()).prepare(request, PreprocessingRequirements())

    assert caught.value.kind == "resource_limit"
    assert caught.value.phase == "image_normalize"
    assert len(case.registry.cleanup_obligations()) == 2
    partial, prior = case.registry.cleanup_obligations()
    assert partial.name == "normalized.png"
    assert 0 < partial.stat().st_size <= 32
    assert budget.used_bytes == partial.stat().st_size + prior.stat().st_size <= budget.max_bytes
    assert case.registry.events[-2:] == [
        ("register", "image_normalized", None),
        ("access", "image_normalized", False),
    ]
    case.cleanup()
    assert not partial.exists()
    assert not prior.exists()


def test_audio_wav_normalization_fragments_and_final_partial_are_factual(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.wav"
    sample_rate = 8000
    channels = 2
    frame_count = int(sample_rate * 2.25)
    with wave.open(str(source_path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * channels * frame_count)
    case = _case(
        tmp_path,
        source_path,
        _audio_descriptor(
            duration_seconds=2.25,
            sample_rate_hz=sample_rate,
            channels=channels,
        ),
    )
    media_tool = _media_tool()

    prepared = AudioPreprocessor(
        AudioPreprocessingConfig(fragment_duration_seconds=1),
        media_tool=media_tool,
    ).prepare(case.request, PreprocessingRequirements())

    assert [artifact.artifact_type for artifact in prepared.artifacts] == [
        "normalized_audio",
        "audio_fragment",
        "audio_fragment",
        "audio_fragment",
    ]
    for artifact in prepared.artifacts:
        with wave.open(str(_artifact_path(case.registry, artifact)), "rb") as decoded:
            assert decoded.getsampwidth() == 2
            assert decoded.getframerate() == sample_rate
            assert decoded.getnchannels() == channels
    fragments = prepared.artifacts[1:]
    assert [(item.start_time_seconds, item.end_time_seconds) for item in fragments] == [
        (0.0, 1.0),
        (1.0, 2.0),
        (2.0, 2.25),
    ]
    with wave.open(str(_artifact_path(case.registry, fragments[-1])), "rb") as final:
        assert final.getnframes() == sample_rate // 4
    assert prepared.metadata["sample_format"] == "pcm_s16le"
    assert prepared.metadata["sample_rate_hz"] == sample_rate
    assert prepared.metadata["channels"] == channels
    assert prepared.metadata["spectrogram_created"] is False
    _assert_registered_before_first_access(prepared, case.registry)
    case.cleanup()


def test_supported_compressed_audio_is_preprocessed_through_ffmpeg(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    source_path = media_files["mp3"]
    probe = audio_parameters(FFmpegMediaInspector().probe(source_path))
    case = _case(
        tmp_path,
        source_path,
        _audio_descriptor(
            duration_seconds=probe.duration_seconds,
            sample_rate_hz=probe.sample_rate_hz,
            channels=probe.channels,
            codec=probe.codec,
        ),
    )

    prepared = AudioPreprocessor(
        AudioPreprocessingConfig(fragment_duration_seconds=1),
        media_tool=_media_tool(),
    ).prepare(case.request, PreprocessingRequirements())

    with wave.open(str(_artifact_path(case.registry, prepared.artifacts[0])), "rb") as decoded:
        assert decoded.getsampwidth() == 2
        assert decoded.getframerate() == probe.sample_rate_hz
        assert decoded.getnchannels() == probe.channels
    case.cleanup()


def test_audio_media_tool_failure_is_controlled_and_obligation_remains(tmp_path: Path) -> None:
    source_path = tmp_path / "corrupt.wav"
    source_path.write_bytes(b"not-audio")
    case = _case(
        tmp_path,
        source_path,
        _audio_descriptor(
            duration_seconds=1.0,
            sample_rate_hz=8000,
            channels=1,
        ),
    )

    with pytest.raises(PreprocessingError) as caught:
        AudioPreprocessor(
            AudioPreprocessingConfig(fragment_duration_seconds=1),
            media_tool=_media_tool(),
        ).prepare(case.request, PreprocessingRequirements())

    assert caught.value.kind == "media_tool"
    assert caught.value.phase == "audio_normalize"
    assert str(tmp_path) not in str(caught.value)
    assert len(case.registry.cleanup_obligations()) == 1
    case.cleanup()


@pytest.mark.parametrize(
    ("config_enabled", "required", "expected"),
    [(False, False, False), (False, True, False), (True, False, False), (True, True, True)],
)
def test_audio_spectrogram_requires_both_config_and_explicit_requirement(
    tmp_path: Path,
    media_files: dict[str, Path],
    config_enabled: bool,
    required: bool,
    expected: bool,
) -> None:
    probe = audio_parameters(FFmpegMediaInspector().probe(media_files["wav"]))
    case = _case(
        tmp_path,
        media_files["wav"],
        _audio_descriptor(
            duration_seconds=probe.duration_seconds,
            sample_rate_hz=probe.sample_rate_hz,
            channels=probe.channels,
            codec=probe.codec,
        ),
        analysis_id=("b" if required else "c") * 32,
    )

    prepared = AudioPreprocessor(
        AudioPreprocessingConfig(
            fragment_duration_seconds=1,
            build_spectrogram=config_enabled,
        ),
        media_tool=_media_tool(),
    ).prepare(
        case.request,
        PreprocessingRequirements(audio_spectrogram=required),
    )

    spectrograms = [
        artifact for artifact in prepared.artifacts if artifact.artifact_type == "spectrogram"
    ]
    assert bool(spectrograms) is expected
    if spectrograms:
        with Image.open(_artifact_path(case.registry, spectrograms[0])) as image:
            assert image.format == "PNG"
            assert image.size == (640, 320)
    case.cleanup()


@pytest.mark.parametrize(
    ("fragment_count", "spectrogram"),
    [(255, False), (254, True)],
    ids=["without-spectrogram", "with-spectrogram"],
)
def test_audio_artifact_count_exact_256_is_accepted_preflight(
    tmp_path: Path,
    fragment_count: int,
    spectrogram: bool,
) -> None:
    source_path = tmp_path / "source.wav"
    source_path.write_bytes(b"source")
    case = _case(
        tmp_path,
        source_path,
        _audio_descriptor(
            duration_seconds=float(fragment_count * 10),
            sample_rate_hz=8_000,
            channels=1,
        ),
    )
    case.request = PreprocessingRequest(
        analysis_id=case.request.analysis_id,
        validated_file=case.request.validated_file,
        source_file_ref=case.request.source_file_ref,
        artifact_registry=case.request.artifact_registry,
        artifact_budget=_artifact_budget(MediaType.AUDIO, max_size_mb=100),
    )
    media_tool = _NoWriteMediaTool()

    prepared = AudioPreprocessor(
        AudioPreprocessingConfig(
            fragment_duration_seconds=10,
            build_spectrogram=spectrogram,
        ),
        media_tool=cast(_FFmpegPreprocessingTool, media_tool),
    ).prepare(
        case.request,
        PreprocessingRequirements(audio_spectrogram=spectrogram),
    )

    assert len(prepared.artifacts) == 256
    assert media_tool.calls == 256
    case.cleanup()


@pytest.mark.parametrize(
    ("fragment_count", "spectrogram"),
    [(256, False), (255, True)],
    ids=["without-spectrogram", "with-spectrogram"],
)
def test_audio_artifact_count_257_is_rejected_before_registration_or_write(
    tmp_path: Path,
    fragment_count: int,
    spectrogram: bool,
) -> None:
    source_path = tmp_path / "source.wav"
    source_path.write_bytes(b"source")
    case = _case(
        tmp_path,
        source_path,
        _audio_descriptor(
            duration_seconds=float(fragment_count * 10),
            sample_rate_hz=8_000,
            channels=1,
        ),
    )
    media_tool = _NoWriteMediaTool()

    with pytest.raises(PreprocessingError) as caught:
        AudioPreprocessor(
            AudioPreprocessingConfig(
                fragment_duration_seconds=10,
                build_spectrogram=spectrogram,
            ),
            media_tool=cast(_FFmpegPreprocessingTool, media_tool),
        ).prepare(
            case.request,
            PreprocessingRequirements(audio_spectrogram=spectrogram),
        )

    assert caught.value.kind == "resource_limit"
    assert caught.value.phase == "artifact_count"
    assert media_tool.calls == 0
    assert case.registry.cleanup_obligations() == ()
    case.cleanup()


def test_one_hour_audio_with_ten_second_fragments_is_rejected_prewrite(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.wav"
    source_path.write_bytes(b"source")
    case = _case(
        tmp_path,
        source_path,
        _audio_descriptor(
            duration_seconds=3_600.0,
            sample_rate_hz=8_000,
            channels=1,
        ),
    )
    media_tool = _NoWriteMediaTool()

    with pytest.raises(PreprocessingError, match="Media preprocessing failed") as caught:
        AudioPreprocessor(
            AudioPreprocessingConfig(fragment_duration_seconds=10),
            media_tool=cast(_FFmpegPreprocessingTool, media_tool),
        ).prepare(case.request, PreprocessingRequirements())

    assert caught.value.kind == "resource_limit"
    assert caught.value.phase == "artifact_count"
    assert media_tool.calls == 0
    assert case.registry.cleanup_obligations() == ()
    case.cleanup()


def test_audio_decoded_pcm_amplification_is_rejected_by_byte_preflight(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "compressed-input.m4a"
    source_path.write_bytes(b"small-compressed-source")
    case = _case(
        tmp_path,
        source_path,
        _audio_descriptor(
            duration_seconds=60.0,
            sample_rate_hz=48_000,
            channels=2,
            codec="aac",
        ),
    )
    case.request = PreprocessingRequest(
        analysis_id=case.request.analysis_id,
        validated_file=case.request.validated_file,
        source_file_ref=case.request.source_file_ref,
        artifact_registry=case.request.artifact_registry,
        artifact_budget=_artifact_budget(MediaType.AUDIO, max_size_mb=1),
    )
    media_tool = _NoWriteMediaTool()

    with pytest.raises(PreprocessingError) as caught:
        AudioPreprocessor(
            AudioPreprocessingConfig(fragment_duration_seconds=10),
            media_tool=cast(_FFmpegPreprocessingTool, media_tool),
        ).prepare(case.request, PreprocessingRequirements())

    assert caught.value.kind == "resource_limit"
    assert caught.value.phase == "audio_preflight"
    assert media_tool.calls == 0
    assert case.registry.cleanup_obligations() == ()
    case.cleanup()


def test_video_periodic_sampling_is_deterministic_bounded_png_without_resize(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "video.mp4"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=32x24:rate=2",
            "-t",
            "3",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            str(source_path),
        ]
    )
    probe = video_parameters(FFmpegMediaInspector().probe(source_path))
    case = _case(
        tmp_path,
        source_path,
        _video_descriptor(
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            has_audio=False,
        ),
    )

    prepared = VideoPreprocessor(
        VideoPreprocessingConfig(keyframe_interval_seconds=1),
        media_tool=_media_tool(),
    ).prepare(case.request, PreprocessingRequirements(video_audio_track=True))

    frames = [
        artifact for artifact in prepared.artifacts if artifact.artifact_type == "sampled_frame"
    ]
    assert [frame.start_time_seconds for frame in frames] == [0.0, 1.0, 2.0]
    assert [frame.frame_index for frame in frames] == [0, 1, 2]
    assert len(frames) <= 120
    assert prepared.metadata["sampling_scope"] == "periodic_representative_frames"
    assert "keyframe" not in " ".join(prepared.metadata.keys())
    assert prepared.metadata["audio_track_created"] is False
    for frame in frames:
        with Image.open(_artifact_path(case.registry, frame)) as image:
            assert image.format == "PNG"
            assert image.size == (probe.width, probe.height)
    _assert_registered_before_first_access(prepared, case.registry)
    case.cleanup()


def test_video_timestamp_plan_applies_internal_resource_cap() -> None:
    timestamps, truncated = _video_timestamps(1000.0, 1)

    assert len(timestamps) == 120
    assert timestamps[:3] == (0.0, 1.0, 2.0)
    assert timestamps[-1] == 119.0
    assert truncated is True


def test_video_with_audio_creates_flac_only_when_allowed_and_required(tmp_path: Path) -> None:
    source_path = tmp_path / "video-with-audio.mp4"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x24:r=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=8000",
            "-t",
            "1.2",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source_path),
        ]
    )
    probe = video_parameters(FFmpegMediaInspector().probe(source_path))
    case = _case(
        tmp_path,
        source_path,
        _video_descriptor(
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            has_audio=True,
        ),
    )

    prepared = VideoPreprocessor(
        VideoPreprocessingConfig(keyframe_interval_seconds=1, extract_audio_track=True),
        media_tool=_media_tool(),
    ).prepare(case.request, PreprocessingRequirements(video_audio_track=True))

    audio = [
        artifact
        for artifact in prepared.artifacts
        if artifact.artifact_type == "extracted_audio_track"
    ]
    assert len(audio) == 1
    assert audio[0].format == "flac"
    audio_probe = audio_parameters(
        FFmpegMediaInspector().probe(_artifact_path(case.registry, audio[0]))
    )
    assert audio_probe.codec == "flac"
    assert prepared.metadata["has_audio"] is True
    assert prepared.metadata["width"] == probe.width
    assert prepared.metadata["height"] == probe.height
    case.cleanup()


def test_video_with_audio_skips_track_without_explicit_requirement(tmp_path: Path) -> None:
    source_path = tmp_path / "video-with-audio.mp4"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x24:r=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=8000",
            "-t",
            "0.5",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-shortest",
            str(source_path),
        ]
    )
    probe = video_parameters(FFmpegMediaInspector().probe(source_path))
    case = _case(
        tmp_path,
        source_path,
        _video_descriptor(
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            has_audio=True,
        ),
    )

    prepared = VideoPreprocessor(
        VideoPreprocessingConfig(extract_audio_track=True),
        media_tool=_media_tool(),
    ).prepare(case.request, PreprocessingRequirements(video_audio_track=False))

    assert not any(
        artifact.artifact_type == "extracted_audio_track" for artifact in prepared.artifacts
    )
    assert prepared.metadata["audio_track_created"] is False
    case.cleanup()


def test_corrupt_video_decode_is_controlled_and_obligation_remains(tmp_path: Path) -> None:
    source_path = tmp_path / "corrupt.mp4"
    source_path.write_bytes(b"not-a-video")
    case = _case(
        tmp_path,
        source_path,
        _video_descriptor(
            duration_seconds=1.0,
            width=32,
            height=24,
            fps=1.0,
            has_audio=False,
        ),
    )

    with pytest.raises(PreprocessingError) as caught:
        VideoPreprocessor(
            VideoPreprocessingConfig(),
            media_tool=_media_tool(),
        ).prepare(case.request, PreprocessingRequirements())

    assert caught.value.kind == "media_tool"
    assert caught.value.phase == "video_frame"
    assert str(tmp_path) not in str(caught.value)
    assert len(case.registry.cleanup_obligations()) == 1
    case.cleanup()


def test_dispatcher_uses_validated_media_type_and_keeps_package_internal(tmp_path: Path) -> None:
    source_path = tmp_path / "renamed.mp4"
    with Image.new("RGB", (3, 2), (1, 2, 3)) as image:
        image.save(source_path, format="PNG")
    descriptor = _image_descriptor(
        width=3,
        height=2,
        image_format="PNG",
        color_mode="RGB",
        original_name="renamed.mp4",
    )
    case = _case(tmp_path, source_path, descriptor)
    raw_config = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    config = AppConfig.model_validate(raw_config)
    dispatcher = PreprocessingDispatcher(config)
    captured_snapshot = dispatcher._config_snapshot
    config.preprocessing.image.normalize_for_analysis = False
    config.limits.max_file_size_mb.image = 1
    case.request = PreprocessingRequest(
        analysis_id=case.request.analysis_id,
        validated_file=case.request.validated_file,
        source_file_ref=case.request.source_file_ref,
        artifact_registry=case.request.artifact_registry,
        artifact_budget=_GeneratedArtifactBudget(
            captured_snapshot,
            MediaType.IMAGE,
        ),
    )

    prepared = dispatcher.prepare(case.request)

    assert prepared.media_type is MediaType.IMAGE
    assert prepared.artifacts[0].artifact_type == "normalized_image"
    for public_name in (
        "Preprocessor",
        "ImagePreprocessor",
        "AudioPreprocessor",
        "VideoPreprocessor",
        "PreprocessingDispatcher",
    ):
        assert not hasattr(preprocessing, public_name)
    case.cleanup()


def test_dispatcher_rejects_budget_from_a_different_snapshot_before_io(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.png"
    with Image.new("RGB", (3, 2), (1, 2, 3)) as image:
        image.save(source_path, format="PNG")
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=3, height=2, image_format="PNG", color_mode="RGB"),
    )
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    config = AppConfig.model_validate(raw)
    different = config.model_copy(deep=True)
    different.server.port += 1
    dispatcher = PreprocessingDispatcher(config)
    case.request = PreprocessingRequest(
        analysis_id=case.request.analysis_id,
        validated_file=case.request.validated_file,
        source_file_ref=case.request.source_file_ref,
        artifact_registry=case.request.artifact_registry,
        artifact_budget=_GeneratedArtifactBudget(
            _ConfigSnapshot.capture(different),
            MediaType.IMAGE,
        ),
    )

    with pytest.raises(PreprocessingError) as caught:
        dispatcher.prepare(case.request)

    assert caught.value.kind == "invariant"
    assert caught.value.phase == "artifact_budget_snapshot"
    assert case.registry.cleanup_obligations() == ()
    case.cleanup()


@pytest.mark.parametrize(
    "capability,phase",
    [
        (ForensicCapability.RESIDUAL_RASTER, "forensic_producer_unavailable"),
        (ForensicCapability.AUDIO_SAMPLES, "forensic_media_type"),
    ],
)
def test_dispatcher_rejects_unimplemented_forensic_demand_before_io(tmp_path, capability, phase):
    source_path = tmp_path / "not_decodable.png"
    source_path.write_bytes(b"no decoder should read this")
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(
            width=3,
            height=2,
            image_format="PNG",
            color_mode="RGB",
        ),
    )
    config = AppConfig.model_validate(
        yaml.safe_load(
            Path("config/config.example.yaml").read_text(encoding="utf-8"),
        )
    )
    try:
        with pytest.raises(PreprocessingError) as error:
            PreprocessingDispatcher(config).prepare(
                case.request,
                PreprocessingRequirements(
                    forensic=frozenset({capability}),
                ),
            )
        assert error.value.phase == phase
        assert case.registry.cleanup_obligations() == ()
        assert case.request.artifact_budget.used_bytes == 0
    finally:
        case.cleanup()


def test_media_process_timeout_is_mapped_without_paths(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = audio_parameters(FFmpegMediaInspector().probe(media_files["wav"]))
    case = _case(
        tmp_path,
        media_files["wav"],
        _audio_descriptor(
            duration_seconds=probe.duration_seconds,
            sample_rate_hz=probe.sample_rate_hz,
            channels=probe.channels,
            codec=probe.codec,
        ),
    )

    def timeout(*_args: object, **_kwargs: object) -> None:
        raise ProcessTimeoutError

    monkeypatch.setattr(
        "fakedetector.preprocessing._media_tools.run_bounded_process",
        timeout,
    )

    with pytest.raises(PreprocessingError) as caught:
        AudioPreprocessor(
            AudioPreprocessingConfig(fragment_duration_seconds=1),
            media_tool=_media_tool(),
        ).prepare(case.request, PreprocessingRequirements())

    assert caught.value.kind == "media_tool"
    assert caught.value.phase == "audio_normalize_timeout"
    assert str(tmp_path) not in str(caught.value)
    assert len(case.registry.cleanup_obligations()) == 1
    case.cleanup()


@pytest.mark.parametrize(
    ("remaining_timeout", "expected_timeout"),
    [(2.5, 2.5), (20.0, 15.0)],
)
def test_media_process_timeout_is_capped_by_remaining_overall_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remaining_timeout: float,
    expected_timeout: float,
) -> None:
    captured_timeouts: list[float] = []
    captured_arguments: list[list[str]] = []

    def complete_process(arguments: list[str], **kwargs: object) -> ProcessResult:
        captured_arguments.append(arguments)
        captured_timeouts.append(cast(float, kwargs["timeout_seconds"]))
        output = cast(BinaryIO, kwargs["stdout_sink"])
        output.write(
            b"RIFF\xff\xff\xff\xffWAVE"
            b"fmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00"
            b"data\xff\xff\xff\xff"
        )
        return ProcessResult(return_code=0, stdout=None)

    monkeypatch.setattr(
        "fakedetector.preprocessing._media_tools.run_bounded_process",
        complete_process,
    )
    source = tmp_path / "source.wav"
    target = tmp_path / "prepared" / "normalized.wav"
    source.write_bytes(b"source")

    _media_tool().normalized_audio(
        source,
        target,
        sample_rate_hz=8_000,
        channels=1,
        artifact_budget=_artifact_budget(MediaType.AUDIO),
        timeout_seconds=remaining_timeout,
    )

    assert captured_timeouts == [expected_timeout]
    input_index = captured_arguments[0].index("-i")
    assert captured_arguments[0][input_index - 2 : input_index] == [
        "-protocol_whitelist",
        "file",
    ]
    assert captured_arguments[0][input_index + 1] == str(source.absolute())
    assert captured_arguments[0][-1] == "pipe:1"


def test_streamed_flac_finalization_restricts_input_to_file_protocol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_arguments: list[str] = []

    def complete_process(arguments: list[str], **_kwargs: object) -> ProcessResult:
        captured_arguments.extend(arguments)
        return ProcessResult(
            return_code=0,
            stdout=b"out_time_us=1000000\nprogress=end\n",
        )

    monkeypatch.setattr(
        "fakedetector.preprocessing._media_tools.run_bounded_process",
        complete_process,
    )
    target = tmp_path / "controlled.flac"
    header = bytearray(42)
    header[:4] = b"fLaC"
    header[5:8] = (34).to_bytes(3, "big")
    header[18:26] = (8_000 << 44).to_bytes(8, "big")
    target.write_bytes(header)

    _media_tool()._finalize_streamed_flac(target, timeout_seconds=1.0)

    input_index = captured_arguments.index("-i")
    assert captured_arguments[input_index - 2 : input_index] == [
        "-protocol_whitelist",
        "file",
    ]
    assert captured_arguments[input_index + 1] == str(target.absolute())


def test_prepared_media_contains_only_opaque_refs_and_bounded_values(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.png"
    with Image.new("RGB", (2, 2)) as image:
        image.save(source_path)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=2, height=2, image_format="PNG", color_mode="RGB"),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
        case.request,
        PreprocessingRequirements(),
    )

    assert isinstance(prepared.source_file_ref, PreparedSourceRef)
    assert all(isinstance(item.artifact_ref, WorkspaceArtifactRef) for item in prepared.artifacts)
    assert not _contains_path(prepared.metadata)
    assert str(tmp_path) not in repr(prepared)
    case.cleanup()


def _contains_path(value: object) -> bool:
    if isinstance(value, PurePath):
        return True
    if isinstance(value, dict):
        return any(_contains_path(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_contains_path(item) for item in value)
    return False


def _media_tool() -> _FFmpegPreprocessingTool:
    return _FFmpegPreprocessingTool(executable="ffmpeg", timeout_seconds=15)


def _run_ffmpeg(arguments: list[str]) -> None:
    executable = shutil.which("ffmpeg")
    assert executable is not None
    subprocess.run(
        [executable, "-v", "error", "-y", "-nostdin", *arguments],
        check=True,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )


def _jpeg_bytes(
    *,
    mode: str = "RGB",
    size: tuple[int, int] = (17, 17),
    progressive: bool = False,
    subsampling: int = 2,
) -> bytes:
    output = io.BytesIO()
    with Image.new(mode, size, 80 if mode == "L" else (40, 80, 120)) as image:
        image.save(output, "JPEG", progressive=progressive, subsampling=subsampling)
    return output.getvalue()


def _forensic_case(tmp_path: Path, data: bytes) -> PreparedCase:
    source = tmp_path / "изображение.jpg"
    source.write_bytes(data)
    descriptor = _image_descriptor(width=17, height=17, image_format="JPEG", color_mode="RGB")
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    )
    return _case(tmp_path, source, descriptor)


_JPEG_DEMAND = PreprocessingRequirements(forensic=frozenset({ForensicCapability.JPEG_COEFFICIENTS}))


@pytest.mark.parametrize(
    "mode,progressive,subsampling",
    [
        ("RGB", False, 0),
        ("RGB", False, 1),
        ("RGB", False, 2),
        ("RGB", True, 2),
        ("L", False, 0),
        ("L", True, 0),
    ],
)
def test_jpeg_native_representation(
    tmp_path: Path, mode: str, progressive: bool, subsampling: int
) -> None:
    data = _jpeg_bytes(mode=mode, progressive=progressive, subsampling=subsampling)
    structure = _parse_jpeg(data)
    case = _forensic_case(tmp_path, data)
    try:
        prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        manifest = prepared.forensic
        assert manifest is not None
        original = manifest.representations[0].facts
        coefficients = manifest.representations[1].facts
        assert isinstance(original, OriginalImageFacts)
        assert isinstance(coefficients, JpegCoefficientsDescriptor)
        assert original.jpeg == structure.header
        assert original.quantization_tables == structure.tables
        assert original.normalized_size == (17, 17)
        assert coefficients.decode_quality == "clean"
        for plane, artifact in zip(coefficients.planes, prepared.artifacts[1:], strict=True):
            raw = case.registry.with_local_artifact_path(artifact.artifact_ref, Path.read_bytes)
            assert len(raw) == plane.nbytes
            import numpy as np

            values = np.frombuffer(raw, dtype="<i4").reshape(plane.shape)
            assert np.count_nonzero(values[:, :, 0, 0]) > 0
            assert np.count_nonzero(values[:, :, 1:, :]) == 0
        assert not _contains_path(prepared.metadata)
    finally:
        case.cleanup()


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes((255, marker)) + (len(payload) + 2).to_bytes(2, "big") + payload


def test_jpeg_sparse_quantization_selectors(tmp_path):
    data = _jpeg_bytes()
    position = data.index(b"\xff\xdb", data.index(b"\xff\xdb") + 2)
    data = data[: position + 4] + b"\x03" + data[position + 5 :]
    data = _replace_segment(data, 0xC0, lambda p: p[:11] + b"\x03" + p[12:14] + b"\x03")
    structure = _parse_jpeg(data)
    assert tuple(t.table_id for t in structure.tables) == (0, 3)
    case = _forensic_case(tmp_path, data)
    try:
        prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        assert len(prepared.artifacts) == 4
    finally:
        case.cleanup()


def _replace_segment(data: bytes, marker: int, transform: Callable[[bytes], bytes]) -> bytes:
    start = data.index(bytes((255, marker)))
    length = int.from_bytes(data[start + 2 : start + 4], "big")
    return (
        data[:start]
        + _segment(marker, transform(data[start + 4 : start + 2 + length]))
        + data[start + 2 + length :]
    )


@pytest.mark.parametrize(
    "mutation,kind",
    [
        (lambda d: d[:1], "decode"),
        (lambda d: d[:-2], "decode"),
        (lambda d: d + b"trailing", "decode"),
        (lambda d: b"\xff\xd8\xff\xdb\x00", "decode"),
        (lambda d: b"\xff\xd8\xff\xdb\x00\x01", "decode"),
        (lambda d: _replace_segment(d, 0xC0, lambda p: p[:-1]), "decode"),
        (lambda d: _replace_segment(d, 0xDB, lambda p: p[:-1]), "decode"),
        (lambda d: _replace_segment(d, 0xDB, lambda p: bytes((2,)) + p[1:]) + b"x", "decode"),
        (lambda d: _replace_segment(d, 0xDB, lambda p: p[:1] + bytes(64)), "decode"),
        (lambda d: _replace_segment(d, 0xC0, lambda p: p[:7] + b"\x00" + p[8:]), "decode"),
        (lambda d: _replace_segment(d, 0xC0, lambda p: p[:9] + p[6:7] + p[10:]), "decode"),
        (lambda d: _replace_segment(d, 0xC0, lambda p: b"\x0c" + p[1:]), "decode"),
        (
            lambda d: _replace_segment(d, 0xC0, lambda p: p[:1] + b"\xff\xff\xff\xff" + p[5:]),
            "resource_limit",
        ),
        (lambda d: d[:2] + _segment(0xFE, b"") * 256 + d[2:], "resource_limit"),
        (lambda d: d[:2] + _segment(0xE1, bytes(65530)) * 17 + d[2:], "resource_limit"),
        (lambda d: d[:2] + _segment(0xDB, bytes((0,)) + bytes((1,)) * 64) + d[2:], "decode"),
    ],
)
def test_jpeg_malformed_preflight_never_invokes_child(tmp_path, monkeypatch, mutation, kind):
    invoked = []
    monkeypatch.setattr(
        "fakedetector.preprocessing._service._decode_jpeg_coefficients",
        lambda *a, **k: invoked.append(True),
    )
    case = _forensic_case(tmp_path, mutation(_jpeg_bytes()))
    try:
        with pytest.raises(PreprocessingError) as error:
            ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        assert error.value.kind == kind
        assert not invoked
        assert case.registry.cleanup_obligations() == ()
    finally:
        case.cleanup()


@pytest.mark.parametrize("width,accepted", [(2047, True), (2048, True), (2049, False)])
def test_jpeg_native_coefficient_policy_boundary(tmp_path, monkeypatch, width, accepted):
    data = _jpeg_bytes(mode="L", size=(width, 2048))
    if not accepted:
        invoked = []
        monkeypatch.setattr(
            "fakedetector.preprocessing._service._decode_jpeg_coefficients",
            lambda *a, **k: invoked.append(True),
        )
        case = _forensic_case(tmp_path, data)
        try:
            with pytest.raises(PreprocessingError) as error:
                ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
            assert error.value.phase == "jpeg_preflight"
            assert not invoked
        finally:
            case.cleanup()
        return
    estimate = _parse_jpeg(data).header.preflight(len(data))
    assert estimate.native_coefficients == 1 << 22
    case = _forensic_case(tmp_path, data)
    try:
        prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        assert prepared.forensic.representations[1].facts.planes[0].nbytes == 16 << 20
    finally:
        case.cleanup()


@pytest.mark.parametrize("orientation", [None, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_original_image_orientation_and_nonjpeg_demand(tmp_path, monkeypatch, orientation):
    invoked = []
    monkeypatch.setattr(
        "fakedetector.preprocessing._service._decode_jpeg_coefficients",
        lambda *a, **k: invoked.append(True),
    )
    buffer = io.BytesIO()
    with Image.new("RGB", (3, 2)) as image:
        image.putdata(
            [(255, 0, 0), (0, 255, 0), (0, 0, 255), (5, 10, 15), (20, 25, 30), (35, 40, 45)]
        )
        exif = Image.Exif()
        if orientation is not None:
            exif[274] = orientation
        image.save(buffer, "PNG", exif=exif)
    case = _forensic_case(tmp_path, buffer.getvalue())
    try:
        prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        facts = prepared.forensic.representations[0].facts
        assert facts.jpeg is None
        assert not invoked and len(prepared.artifacts) == 1
        expected_orientation = (
            1 if orientation is None else orientation if 1 <= orientation <= 8 else None
        )
        assert facts.coordinates.orientation == expected_orientation
        assert facts.exif_orientation == (orientation if orientation in range(1, 9) else None)
        assert facts.orientation_applied == (orientation in range(2, 9))
        assert facts.normalized_size == ((2, 3) if orientation in range(5, 9) else (3, 2))
        with Image.open(io.BytesIO(buffer.getvalue())) as source:
            from PIL import ImageOps

            expected = ImageOps.exif_transpose(source).convert("RGB")
            raw = case.registry.with_local_artifact_path(
                prepared.artifacts[0].artifact_ref, Path.read_bytes
            )
            with Image.open(io.BytesIO(raw)) as normalized:
                assert normalized.tobytes() == expected.tobytes()
        if expected_orientation is None:
            with pytest.raises(ValueError, match="unknown"):
                facts.coordinates.normalized_bbox(0, 0, 3, 2)
        else:
            assert facts.coordinates.normalized_bbox(0, 0, 3, 2) == (0, 0, 1, 1)
    finally:
        case.cleanup()


@pytest.mark.parametrize(
    "failure,kind,phase",
    [
        (ProcessResult(0, b"{}", b"native private path warning"), "decode", "jpeg_native_warning"),
        (ProcessResult(2, b"", b"private error"), "decode", "jpeg_native_error"),
        (ProcessResult(-11, b"", b""), "decode", "jpeg_native_error"),
        (ProcessResult(0, b"{}", b""), "infrastructure", "jpeg_native_protocol"),
        (ProcessTimeoutError(), "media_tool", "jpeg_native_timeout"),
    ],
)
def test_jpeg_native_failures_are_safe_and_owned(tmp_path, monkeypatch, failure, kind, phase):
    def failed_child(*args, **kwargs):
        assert kwargs["stdout_limit_bytes"] == kwargs["stderr_limit_bytes"] == 4096
        assert set(kwargs["environment"]) <= {
            "SystemRoot",
            "SYSTEMROOT",
            "WINDIR",
            "windir",
            "TEMP",
            "TMP",
            "__PYVENV_LAUNCHER__",
            "OPENBLAS_NUM_THREADS",
        }
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr("fakedetector.preprocessing._media_tools.run_bounded_process", failed_child)
    case = _forensic_case(tmp_path, _jpeg_bytes())
    try:
        with pytest.raises(PreprocessingError) as error:
            ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        assert (error.value.kind, error.value.phase) == (kind, phase)
        assert "private" not in str(error.value)
        assert len(case.registry.cleanup_obligations()) == 4
    finally:
        case.cleanup()
    assert not (tmp_path / "temp" / case.request.analysis_id).exists()


def test_jpeg_unicode_workspace(tmp_path):
    unicode_root = tmp_path / "кириллица 雪"
    unicode_root.mkdir()
    case = _forensic_case(unicode_root, _jpeg_bytes())
    before = Path.cwd()
    try:
        prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        assert len(prepared.artifacts) == 4
        assert Path.cwd() == before
    finally:
        case.cleanup()


def test_default_demand_never_invokes_jpeg_child(tmp_path, monkeypatch):
    invoked = []
    monkeypatch.setattr(
        "fakedetector.preprocessing._service._decode_jpeg_coefficients",
        lambda *a, **k: invoked.append(True),
    )
    case = _forensic_case(tmp_path, _jpeg_bytes())
    try:
        prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
            case.request, PreprocessingRequirements()
        )
        assert prepared.forensic is None and len(prepared.artifacts) == 1 and not invoked
    finally:
        case.cleanup()


@pytest.mark.parametrize(
    "script,phase",
    [
        ("import os; os._exit(7)", "jpeg_native_error"),
        ("import os; os.write(1,b'x'*8192)", "jpeg_native_output"),
        ("import os; os.write(2,b'x'*8192)", "jpeg_native_output"),
        ("import time; time.sleep(10)", "jpeg_native_timeout"),
    ],
)
def test_jpeg_real_child_crash_overflow_timeout_cleanup(tmp_path, monkeypatch, script, phase):
    from fakedetector.core._bounded_process import run_bounded_process

    def replacement(arguments, **kwargs):
        kwargs["timeout_seconds"] = 0.2 if phase == "jpeg_native_timeout" else 5
        return run_bounded_process([arguments[0], "-I", "-c", script], **kwargs)

    monkeypatch.setattr("fakedetector.preprocessing._media_tools.run_bounded_process", replacement)
    case = _forensic_case(tmp_path, _jpeg_bytes())
    try:
        with pytest.raises(PreprocessingError) as error:
            ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        assert error.value.phase == phase
        assert len(case.registry.cleanup_obligations()) == 4
    finally:
        case.cleanup()
    assert not (tmp_path / "temp" / case.request.analysis_id).exists()


def test_jpeg_corrupt_entropy_native_warning_is_rejected(tmp_path):
    from fakedetector.preprocessing._models import ImageCoordinates
    from fakedetector.preprocessing._service import _prepare_jpeg_planes

    data = _jpeg_bytes()
    sos = data.index(b"\xff\xda")
    entropy = sos + 2 + int.from_bytes(data[sos + 2 : sos + 4], "big")
    data = data[:entropy] + b"\x00\xff\xd9"
    structure = _parse_jpeg(data)  # Structurally valid; entropy is the decoder's job.
    case = _forensic_case(tmp_path, data)
    try:
        original = OriginalImageFacts(
            format="jpeg",
            jpeg=structure.header,
            coordinates=ImageCoordinates(native_width=17, native_height=17),
        )
        with pytest.raises(PreprocessingError) as error:
            _prepare_jpeg_planes(case.request, original, [], None)
        assert error.value.phase == "jpeg_native_warning"
        assert len(case.registry.cleanup_obligations()) == 3
    finally:
        case.cleanup()


def test_jpeg_budget_rejection_precedes_native_child(tmp_path, monkeypatch):
    from dataclasses import replace

    invoked = []
    monkeypatch.setattr(
        "fakedetector.preprocessing._service._decode_jpeg_coefficients",
        lambda *a, **k: invoked.append(True),
    )
    case = _forensic_case(tmp_path, _jpeg_bytes(mode="L", size=(1024, 1024)))
    request = replace(
        case.request, artifact_budget=_artifact_budget(MediaType.IMAGE, max_size_mb=1)
    )
    try:
        with pytest.raises(PreprocessingError) as error:
            ImagePreprocessor(ImagePreprocessingConfig()).prepare(request, _JPEG_DEMAND)
        assert error.value.phase == "jpeg_artifact_preflight"
        assert not invoked and len(case.registry.cleanup_obligations()) == 1
    finally:
        case.cleanup()


def test_jpeg_runner_owns_actual_decoder_pid_and_venv(tmp_path, monkeypatch):
    import json
    import sys

    import fakedetector.core._bounded_process as process_module
    from fakedetector.preprocessing._media_tools import _decode_jpeg_coefficients

    processes = []
    real_popen = subprocess.Popen

    def record(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        processes.append(child)
        return child

    monkeypatch.setattr(process_module.subprocess, "Popen", record)

    def probe(arguments, **kwargs):
        result = process_module.run_bounded_process(
            [
                arguments[0],
                "-I",
                "-c",
                "import os,sys,json,jpegio; "
                "print(json.dumps([os.getpid(),sys.prefix,jpegio.__file__]))",
            ],
            **kwargs,
        )
        pid, prefix, origin = json.loads(result.stdout)
        assert pid == processes[0].pid
        assert Path(prefix) == Path(sys.prefix)
        assert Path(origin).is_relative_to(Path(sys.prefix))
        assert processes[0].poll() == 0
        return ProcessResult(
            0, b'{"version":1,"status":"clean","source_sha256":"' + b"0" * 64 + b'"}', b""
        )

    monkeypatch.setattr("fakedetector.preprocessing._media_tools.run_bounded_process", probe)
    _decode_jpeg_coefficients(tmp_path / "source", "0" * 64, timeout_seconds=5)


@pytest.mark.parametrize(
    "variant", ["valid", "wide_integer", "overflow", "float", "shape", "component", "table"]
)
def test_jpeg_child_numeric_layout_and_lossless_cast(tmp_path, monkeypatch, capsys, variant):
    from types import SimpleNamespace

    import numpy as np

    import fakedetector.preprocessing._media_tools as media

    data = _jpeg_bytes(mode="L")
    (tmp_path / "source").write_bytes(data)
    target = tmp_path / "jpeg_component_0.raw"
    target.write_bytes(bytes(3 * 3 * 256))
    structure = _parse_jpeg(data)
    plane = np.arange(
        24 * 24, dtype=np.int64 if variant in {"wide_integer", "overflow"} else np.int32
    ).reshape(24, 24)
    if variant == "overflow":
        plane[-1, -1] = 1 << 32
    elif variant == "float":
        plane = plane.astype(float)
    elif variant == "shape":
        plane = plane[:-1]
    component = structure.header.components[0]
    native = SimpleNamespace(
        coef_arrays=[plane],
        comp_info=[
            SimpleNamespace(
                component_id=component.component_id,
                h_samp_factor=0 if variant == "component" else component.horizontal_sampling,
                v_samp_factor=component.vertical_sampling,
                quant_tbl_no=0,
            )
        ],
        quant_tables=[np.array(structure.tables[0].values).reshape(8, 8)],
    )
    if variant == "table":
        native.quant_tables[0][0, 0] += 1
    monkeypatch.setattr(media, "Path", lambda name: tmp_path / name)
    monkeypatch.setattr(
        media.importlib, "import_module", lambda name: SimpleNamespace(read=lambda source: native)
    )
    if variant not in {"valid", "wide_integer"}:
        with pytest.raises(ValueError):
            media._jpeg_child(hashlib.sha256(data).hexdigest())
        assert target.read_bytes() == bytes(3 * 3 * 256)
        return
    media._jpeg_child(hashlib.sha256(data).hexdigest())
    actual = np.frombuffer(target.read_bytes(), dtype="<i4").reshape(3, 3, 8, 8)
    for y in range(3):
        for x in range(3):
            np.testing.assert_array_equal(actual[y, x], plane[y * 8 : y * 8 + 8, x * 8 : x * 8 + 8])
    response = capsys.readouterr().out
    assert len(response) < 200 and "clean" in response and "coef_arrays" not in response


def test_jpeg_unresolved_ownership_preserves_cleanup_barrier(tmp_path, monkeypatch):
    from fakedetector.core._bounded_process import ProcessInfrastructureError
    from fakedetector.preprocessing._media_tools import _decode_jpeg_coefficients

    class Barrier:
        def try_confirm_safe(self):
            return False

    barrier = Barrier()

    def unresolved(*args, **kwargs):
        raise ProcessInfrastructureError("termination", _cleanup_safety_barrier=barrier)

    monkeypatch.setattr("fakedetector.preprocessing._media_tools.run_bounded_process", unresolved)
    with pytest.raises(PreprocessingError) as error:
        _decode_jpeg_coefficients(tmp_path / "source", "0" * 64, timeout_seconds=1)
    assert error.value.kind == "infrastructure"
    assert error.value._cleanup_safety_barrier is barrier
    assert not barrier.try_confirm_safe()


def test_jpeg_partial_artifact_failure_is_registered_and_cleaned(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from fakedetector._generated_artifact_budget import _GeneratedArtifactWriteError

    real_output = _GeneratedArtifactBudget.open_output

    @contextmanager
    def interrupted(budget, target):
        with real_output(budget, target) as output:
            if target.suffix == ".raw":
                output.write(b"partial")
                raise _GeneratedArtifactWriteError
            yield output

    monkeypatch.setattr(_GeneratedArtifactBudget, "open_output", interrupted)
    case = _forensic_case(tmp_path, _jpeg_bytes())
    try:
        with pytest.raises(PreprocessingError) as error:
            ImagePreprocessor(ImagePreprocessingConfig()).prepare(case.request, _JPEG_DEMAND)
        assert error.value.kind == "artifact_write"
        assert len(case.registry.cleanup_obligations()) == 2
        assert case.request.artifact_budget.used_bytes > 7
    finally:
        case.cleanup()
    assert not (tmp_path / "temp" / case.request.analysis_id).exists()


def immutable(values, dtype="<f8"):
    values = np.asarray(values, dtype=dtype)
    return np.frombuffer(values.tobytes(), dtype=dtype).reshape(values.shape)


def pcm(path, bits, channels=1, rate=8000, count=8000):
    codes = np.resize(
        np.array([0, 1, -1, (1 << (bits - 1)) - 1, -(1 << (bits - 1))], dtype="<i4"),
        count * channels,
    )
    if bits == 24:
        data = codes.view("u1").reshape(-1, 4)[:, :3].tobytes()
    else:
        data = codes.astype(f"<i{bits // 8}").tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setparams((channels, bits // 8, rate, 0, "NONE", "none"))
        stream.writeframes(data)
    return codes.reshape(count, channels)


@pytest.mark.parametrize("bits", [16, 24, 32])
@pytest.mark.parametrize("channels", [1, 2, 8])
def test_integer_codes_preserved(tmp_path, bits, channels):
    source = tmp_path / "precision.wav"
    expected = pcm(source, bits, channels)
    facts = probe_audio(source, executable="ffprobe", timeout=10)
    result = decode_audio_window(
        source, facts, IndexRange(start=0, stop=8000), executable="ffmpeg", timeout=10
    )
    np.testing.assert_array_equal(result.values, expected)
    assert result.facts.decoder_storage_bits == (16 if bits == 16 else 32)
    assert result.facts.source_bits == bits
    assert result.values.dtype.str == "<i4"
    assert result.first_pts == 0
    with pytest.raises(ValueError):
        result.values.setflags(write=True)


@pytest.mark.parametrize("encoding,dtype", [("pcm_f32le", "<f4"), ("pcm_f64le", "<f8")])
def test_float_not_clipped(tmp_path, encoding, dtype):
    raw = tmp_path / "input.raw"
    values = np.tile(np.array([-2.5, -0.123456789, 0.0, 1.5], dtype=dtype), 2000)
    raw.write_bytes(values.tobytes())
    source = tmp_path / "float.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "f32le" if dtype == "<f4" else "f64le",
            "-ar",
            "8000",
            "-ac",
            "1",
            "-i",
            str(raw),
            "-c:a",
            encoding,
            str(source),
        ],
        check=True,
        timeout=10,
    )
    facts = probe_audio(source, executable="ffprobe", timeout=10)
    result = decode_audio_window(
        source, facts, IndexRange(start=0, stop=8000), executable="ffmpeg", timeout=10
    )
    np.testing.assert_array_equal(result.values[:, 0], values.astype("<f8"))
    assert result.values.dtype.str == "<f8"


def test_lossy_and_seek_actual_coverage(tmp_path):
    source = tmp_path / "input.wav"
    pcm(source, 16, count=24000)
    lossy = tmp_path / "lossy.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), str(lossy)], check=True, timeout=10)
    facts = probe_audio(lossy, executable="ffprobe", timeout=10)
    first = decode_audio_window(
        lossy, facts, IndexRange(start=0, stop=8000), executable="ffmpeg", timeout=10
    )
    middle = decode_audio_window(
        lossy, facts, IndexRange(start=8000, stop=16000), executable="ffmpeg", timeout=10
    )
    assert first.facts.decoder_format in ("flt", "dbl")
    assert first.values.shape == middle.values.shape == (8000, 1)
    assert middle.first_pts - first.first_pts == 8000


@pytest.mark.parametrize("count", [1, 7999, 8000, 8001])
def test_incomplete_window_no_padding(tmp_path, count):
    source = tmp_path / "short.wav"
    expected = pcm(source, 16, count=count)
    facts = probe_audio(source, executable="ffprobe", timeout=10)
    decoded = decode_audio_window(
        source, facts, IndexRange(start=0, stop=count + 100), executable="ffmpeg", timeout=10
    )
    np.testing.assert_array_equal(decoded.values, expected)


@pytest.mark.parametrize(
    "total,expected",
    [
        (1, [(0, 1)]),
        (80000, [(0, 80000)]),
        (160000, [(0, 80000), (80000, 160000)]),
        (800000, [(0, 80000), (360000, 440000), (720000, 800000)]),
    ],
)
def test_window_selection(total, expected):
    assert [(r.start, r.stop) for r in select_audio_windows(total, 8000, 1)] == expected


@pytest.mark.parametrize("rate,channels", [(192000, 8), (1, 1), (192000, 1)])
def test_window_policy_limits(rate, channels):
    for window in select_audio_windows(rate * 100, rate, channels):
        ForensicResourcePolicy().check_audio(window.count, channels, rate)


@pytest.mark.parametrize("rate,channels", [(192001, 1), (0, 1), (8000, 9), (8000, 0)])
def test_window_policy_rejection(rate, channels):
    with pytest.raises(ValueError):
        select_audio_windows(800000, rate, channels)


@pytest.mark.parametrize("count,covered,tail", [(16, 16, 0), (17, 16, 1), (3, 0, 3)])
def test_frames(count, covered, tail):
    data = immutable(np.arange(count * 2).reshape(count, 2), "<i4")
    frames = frame_audio(data, sample_rate=8000, frame_length=8, hop=4)
    assert frames.covered_samples == covered
    assert frames.dropped_tail_samples == tail
    assert frames.values.shape == (max(0, 1 + (count - 8) // 4), 2, 8)
    if count >= 8:
        np.testing.assert_array_equal(frames.values[0], data[:8].T)
        assert np.shares_memory(frames.values, data)
    with pytest.raises(ValueError):
        frames.values.setflags(write=True)


@pytest.mark.parametrize("length,hop", [(0, 1), (4097, 1025), (8, 1), (8, 9), (8, 0), (True, 1)])
def test_invalid_framing(length, hop):
    with pytest.raises(ValueError):
        frame_audio(immutable(np.zeros((16, 1))), sample_rate=8000, frame_length=length, hop=hop)


def test_hann_exact_definition():
    np.testing.assert_allclose(periodic_hann(4), [0, 0.5, 1, 0.5], atol=1e-15)
    np.testing.assert_array_equal(periodic_hann(1), [0])
    np.testing.assert_array_equal(periodic_hann(2), [0, 1])
    assert periodic_hann(8)[-1] != 0
    with pytest.raises(ValueError):
        periodic_hann(4).setflags(write=True)


@pytest.mark.parametrize("scaling", ["complex", "magnitude", "power"])
def test_fft_dc_sine_multichannel_deterministic(scaling):
    n = 64
    data = immutable(
        np.column_stack((np.ones(n * 3), np.sin(2 * np.pi * 4 * np.arange(n * 3) / n)))
    )
    kwargs = {
        "sample_rate": 8000,
        "n_fft": n,
        "hop": n,
        "window": "rectangular",
        "scaling": scaling,
        "batch_size": 2,
    }
    batches = list(stft_batches(data, **kwargs))
    actual = np.concatenate([b.values for b in batches])
    assert [b.first_frame for b in batches] == [0, 2]
    assert actual.shape == (3, 2, 33)
    expected = np.fft.rfft(data[:n].T)
    if scaling != "complex":
        expected = np.abs(expected)
    if scaling == "power":
        expected **= 2
    np.testing.assert_allclose(actual[0], expected)
    assert np.argmax(np.abs(actual[0, 1])) == 4
    np.testing.assert_array_equal(
        actual, np.concatenate([b.values for b in stft_batches(data, **kwargs)])
    )
    np.testing.assert_array_equal(frequency_bins(8000, n), np.arange(33) * 125)
    with pytest.raises(ValueError):
        batches[0].values.setflags(write=True)


@pytest.mark.parametrize(
    "data",
    [
        np.zeros((16, 1)),
        immutable([[np.nan]]),
        immutable([[np.inf]]),
        immutable([[1]], ">i4"),
        immutable([[1]], "<f4"),
    ],
)
def test_invalid_numeric_input(data):
    with pytest.raises(ValueError):
        frame_audio(data, sample_rate=8000, frame_length=4, hop=1)


@pytest.mark.parametrize(
    "exception,kind,phase",
    [
        (ProcessTimeoutError(), "media_tool", "audio_precision_probe_timeout"),
        (ProcessOutputLimitError(), "resource_limit", "audio_precision_probe_overflow"),
        (ProcessInfrastructureError("start"), "infrastructure", "audio_precision_probe_process"),
    ],
)
def test_process_failures_safe(monkeypatch, tmp_path, exception, kind, phase):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(decoder, "run_bounded_process", fail)
    with pytest.raises(PreprocessingError) as caught:
        probe_audio(tmp_path / "secret.wav", executable="ffprobe", timeout=5)
    assert (caught.value.kind, caught.value.phase) == (kind, phase)
    assert "secret" not in str(caught.value)


def test_malformed_and_unsupported(tmp_path):
    source = tmp_path / "bad.wav"
    source.write_bytes(b"not audio")
    with pytest.raises(PreprocessingError, match="Media preprocessing failed"):
        probe_audio(source, executable="ffprobe", timeout=5)
    pcm(source, 16)
    facts = probe_audio(source, executable="ffprobe", timeout=5)
    facts = facts.model_copy(update={"declared_sample_format": "s64"})
    with pytest.raises(PreprocessingError) as error:
        decode_audio_window(
            source, facts, IndexRange(start=0, stop=8000), executable="ffmpeg", timeout=5
        )
    assert error.value.phase == "audio_precision_unsupported_format"


def test_producer_demand_and_legacy_regression(tmp_path):
    source = tmp_path / "pcm.wav"
    pcm(source, 24)
    descriptor = _audio_descriptor(
        duration_seconds=1.0, sample_rate_hz=8000, channels=1, codec="pcm_s24le"
    ).model_copy(
        update={
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "size_bytes": source.stat().st_size,
        }
    )
    tool = _FFmpegPreprocessingTool(executable="ffmpeg", timeout_seconds=10)
    processor = AudioPreprocessor(AudioPreprocessingConfig(), media_tool=tool)
    legacy = _case(tmp_path / "legacy", source, descriptor)
    expanded = _case(tmp_path / "expanded", source, descriptor)
    old = processor.prepare(legacy.request, PreprocessingRequirements(audio_spectrogram=True))
    new = processor.prepare(
        expanded.request,
        PreprocessingRequirements(
            audio_spectrogram=True, forensic=frozenset({ForensicCapability.AUDIO_SPECTRAL})
        ),
    )
    assert old.forensic is None
    assert new.forensic is not None
    facts = [r.facts for r in new.forensic.representations]
    windows = [f for f in facts if isinstance(f, AudioWindowDescriptor)]
    spectral = [f for f in facts if isinstance(f, SpectralWindowDescriptor)]
    assert len(windows) == len(spectral) == 1
    assert windows[0].samples == IndexRange(start=0, stop=8000)
    assert len(new.forensic.to_metadata()) < 16384
    for artifact in old.artifacts:
        matching = next(a for a in new.artifacts if a.artifact_id == artifact.artifact_id)
        old_bytes = legacy.registry.with_local_artifact_path(artifact.artifact_ref, Path.read_bytes)
        new_bytes = expanded.registry.with_local_artifact_path(
            matching.artifact_ref, Path.read_bytes
        )
        assert old_bytes == new_bytes
    for case in (legacy, expanded):
        for event in case.registry.events:
            if event[0] == "access":
                assert any(e[0] == "register" and e[1] == event[1] for e in case.registry.events)


def test_spectral_resource_and_finite_output():
    data = immutable(np.zeros((4096, 8)))
    with pytest.raises(ValueError, match="workspace"):
        stft_batches(data, sample_rate=8000, n_fft=4096, hop=1024, batch_size=32)
    with pytest.raises(ValueError, match="batch"):
        stft_batches(data, sample_rate=8000, n_fft=4096, hop=1024, batch_size=33)
    huge = immutable(np.full((8, 1), 1e308))
    with pytest.raises(ValueError, match="nonfinite"):
        list(stft_batches(huge, sample_rate=8000, n_fft=8, hop=8, scaling="power"))


def test_malformed_probe_json(monkeypatch, tmp_path):
    monkeypatch.setattr(decoder, "run_bounded_process", lambda *a, **k: ProcessResult(0, b"{}"))
    with pytest.raises(PreprocessingError) as caught:
        probe_audio(tmp_path / "x", executable="ffprobe", timeout=1)
    assert caught.value.phase == "audio_precision_malformed"


def test_u8_centering_and_high_rate(tmp_path):
    source = tmp_path / "u8.wav"
    values = bytes([0, 127, 128, 129, 255]) * 200
    with wave.open(str(source), "wb") as stream:
        stream.setparams((1, 1, 192000, 0, "NONE", "none"))
        stream.writeframes(values)
    facts = probe_audio(source, executable="ffprobe", timeout=5)
    result = decode_audio_window(
        source, facts, IndexRange(start=0, stop=1000), executable="ffmpeg", timeout=5
    )
    np.testing.assert_array_equal(
        result.values[:, 0], np.frombuffer(values, "u1").astype("<i4") - 128
    )
    assert result.facts.decoder_format == "u8"


def test_truncated_source_is_not_padded(tmp_path):
    source = tmp_path / "truncated.wav"
    pcm(source, 24)
    source.write_bytes(source.read_bytes()[:-1])
    facts = probe_audio(source, executable="ffprobe", timeout=5)
    with pytest.raises(PreprocessingError) as error:
        decode_audio_window(
            source, facts, IndexRange(start=0, stop=8000), executable="ffmpeg", timeout=5
        )
    assert error.value.phase == "audio_precision_window_malformed_media"


def test_unresolved_child_barrier_is_preserved(monkeypatch, tmp_path):
    class Barrier:
        def try_confirm_safe(self):
            return False

    barrier = Barrier()

    def fail(*args, **kwargs):
        raise ProcessInfrastructureError("termination", _cleanup_safety_barrier=barrier)

    monkeypatch.setattr(decoder, "run_bounded_process", fail)
    with pytest.raises(PreprocessingError) as caught:
        probe_audio(tmp_path / "x", executable="ffprobe", timeout=5)
    assert caught.value._cleanup_safety_barrier is barrier


@pytest.mark.parametrize(
    "change", ["format", "channels", "rate", "count", "pts", "length", "empty", "nonfinite"]
)
def test_decoder_sideband_mismatch_rejected(monkeypatch, tmp_path, change):
    from fakedetector.preprocessing._models import AudioPrecisionFacts

    facts = AudioPrecisionFacts(
        stream_index=0,
        codec="pcm_f64le",
        source_bits=64,
        decoder_format="unknown",
        sample_rate=8000,
        channels=1,
        declared_sample_format="dbl",
    )
    line = (
        b"[Parsed_ashowinfo_1 @ abc] n:0 pts:0 pts_time:0 fmt:dbl channels:1 "
        b"chlayout:mono rate:8000 nb_samples:4 checksum:0\n"
    )
    replacements = {
        "format": (b"fmt:dbl", b"fmt:s64"),
        "channels": (b"channels:1", b"channels:2"),
        "rate": (b"rate:8000", b"rate:16000"),
        "count": (b"nb_samples:4", b"nb_samples:5"),
    }
    if change in replacements:
        line = line.replace(*replacements[change])
    if change == "pts":
        line += line.replace(b"n:0 pts:0", b"n:1 pts:7")
    payload = np.full(4, np.nan if change == "nonfinite" else 1, dtype="<f8").tobytes()
    if change == "length":
        payload += b"x"
    if change == "empty":
        payload = b""
    monkeypatch.setattr(
        decoder, "run_bounded_process", lambda *a, **k: ProcessResult(0, payload, line)
    )
    with pytest.raises(PreprocessingError):
        decode_audio_window(
            tmp_path / "x", facts, IndexRange(start=0, stop=4), executable="ffmpeg", timeout=5
        )


@pytest.mark.parametrize("declared", ["s16p", "s32p", "u8p", "fltp", "dblp"])
def test_planar_decoder_format_is_retained(monkeypatch, tmp_path, declared):
    from fakedetector.preprocessing._models import AudioPrecisionFacts

    floating = declared in ("fltp", "dblp")
    facts = AudioPrecisionFacts(
        stream_index=0,
        codec="fixture",
        source_bits=None,
        decoder_format="unknown",
        sample_rate=8000,
        channels=2,
        declared_sample_format=declared,
    )
    line = (
        f"[Parsed_ashowinfo_1 @ abc] n:0 pts:0 pts_time:0 fmt:{declared} channels:2 "
        "chlayout:stereo rate:8000 nb_samples:4 checksum:0\n"
    ).encode()
    payload = bytes(4 * 2 * (8 if floating else 4))
    monkeypatch.setattr(
        decoder, "run_bounded_process", lambda *a, **k: ProcessResult(0, payload, line)
    )
    result = decode_audio_window(
        tmp_path / "x", facts, IndexRange(start=0, stop=4), executable="ffmpeg", timeout=5
    )
    assert result.facts.decoded_planar
    assert result.values.shape == (4, 2)


def test_precision_only_does_not_write_samples(tmp_path):
    from fakedetector.preprocessing._service import _prepare_audio_forensic

    source = tmp_path / "short.wav"
    pcm(source, 16, count=100)
    descriptor = _audio_descriptor(
        duration_seconds=0.0125, sample_rate_hz=8000, channels=1
    ).model_copy(update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    case = _case(tmp_path / "case", source, descriptor)
    artifacts = []
    manifest = _prepare_audio_forensic(
        case.request,
        PreprocessingRequirements(forensic=frozenset({ForensicCapability.AUDIO_PRECISION})),
        _FFmpegPreprocessingTool(executable="ffmpeg", timeout_seconds=5),
        artifacts,
        0.0125,
        None,
    )
    assert len(manifest.representations) == 1
    assert manifest.representations[0].facts.decoder_format == "s16"
    assert artifacts == []
    assert case.registry.events == []


@pytest.mark.parametrize("total", [100, 80000, 160000, 320000])
def test_window_values_and_coverage_match_source(tmp_path, total):
    source = tmp_path / "long.wav"
    expected = pcm(source, 24, count=total)
    facts = probe_audio(source, executable="ffprobe", timeout=5)
    for requested in select_audio_windows(total, 8000, 1):
        result = decode_audio_window(source, facts, requested, executable="ffmpeg", timeout=5)
        assert result.first_pts == requested.start
        np.testing.assert_array_equal(result.values, expected[requested.start : requested.stop])


def test_fft_aggregate_frames_and_tightened_policy():
    data = immutable(np.zeros((32773, 1)))
    with pytest.raises(ValueError):
        stft_batches(data, sample_rate=8000, n_fft=4, hop=4)
    data = immutable(np.zeros((64, 1)))
    with pytest.raises(ValueError):
        stft_batches(
            data, sample_rate=8000, n_fft=64, hop=16, policy=ForensicResourcePolicy(fft_size=32)
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_numeric_reader_rejects_nonfinite_audio(tmp_path, value):
    from pydantic import BaseModel
    from test_stage5_internal_models import _manifest

    from fakedetector.analyzers._models import (
        AnalyzerArtifactInput,
        AnalyzerRequest,
        _AnalyzerFileFacts,
        _ReadOnlyAnalyzerInput,
    )
    from fakedetector.domain import MediaType
    from fakedetector.preprocessing._models import AudioPrecisionFacts, NumericArtifact

    class EmptySettings(BaseModel):
        pass

    numeric = NumericArtifact(artifact_id="samples", shape=(1, 1), dtype="<f8")
    facts = AudioPrecisionFacts(
        stream_index=0,
        codec="pcm_f64le",
        source_bits=64,
        decoder_format="dbl",
        sample_rate=8000,
        channels=1,
    )
    manifest = _manifest(
        facts,
        AudioWindowDescriptor(stream_index=0, samples=IndexRange(start=0, stop=1), data=numeric),
        media_type=MediaType.AUDIO,
    )
    path = tmp_path / "samples.raw"
    path.write_bytes(np.array([value], dtype="<f8").tobytes())
    request = AnalyzerRequest(
        analysis_id="reader",
        media_type=MediaType.AUDIO,
        file_facts=_AnalyzerFileFacts.from_validated_file(
            _audio_descriptor(duration_seconds=1.0, sample_rate_hz=8000, channels=1)
        ),
        source=_ReadOnlyAnalyzerInput(tmp_path / "unused"),
        settings=EmptySettings(),
        timeout_seconds=1,
        metadata={"forensic": manifest.to_metadata()},
        artifacts=(
            AnalyzerArtifactInput(
                artifact_id="samples",
                artifact_type="audio_numeric",
                content=_ReadOnlyAnalyzerInput(path),
                format="forensic_raw",
            ),
        ),
    )
    with pytest.raises(ValueError, match="nonfinite"):
        request.read_numeric(numeric)


def test_audio_sample_provenance_identity():
    from pydantic import ValidationError
    from test_stage5_internal_models import _audio_facts, _manifest, _sample_window

    from fakedetector.preprocessing._models import ForensicManifest

    manifest = _manifest(_audio_facts(), _sample_window(), media_type=MediaType.AUDIO)
    payload = manifest.model_dump()
    payload["representations"][1]["provenance"]["profile"] = "unrelated"
    with pytest.raises(ValidationError, match="provenance"):
        ForensicManifest.model_validate(payload)


def test_audio_precision_budget_preflight_precedes_decode(tmp_path):
    from dataclasses import replace

    from fakedetector.preprocessing._service import _prepare_audio_forensic

    source = tmp_path / "long.wav"
    pcm(source, 16, count=800000)
    descriptor = _audio_descriptor(duration_seconds=100.0, sample_rate_hz=8000, channels=1)
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    )
    case = _case(tmp_path / "case", source, descriptor)
    request = replace(
        case.request, artifact_budget=_artifact_budget(MediaType.AUDIO, max_size_mb=1)
    )

    class NoDecode(_FFmpegPreprocessingTool):
        def precision_window(self, *args, **kwargs):
            pytest.fail("resource rejection must precede decode")

    with pytest.raises(PreprocessingError) as error:
        _prepare_audio_forensic(
            request,
            PreprocessingRequirements(forensic=frozenset({ForensicCapability.AUDIO_SAMPLES})),
            NoDecode(executable="ffmpeg", timeout_seconds=5),
            [],
            100.0,
            None,
        )
    assert error.value.kind == "resource_limit"
    assert case.registry.events == []


def test_audio_producer_retains_incomplete_requested_coverage(tmp_path):
    from fakedetector.preprocessing._service import _prepare_audio_forensic

    source = tmp_path / "partial.wav"
    pcm(source, 16)
    descriptor = _audio_descriptor(duration_seconds=1.0, sample_rate_hz=8000, channels=1)
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    )
    case = _case(tmp_path / "case", source, descriptor)

    class OverstatedDuration(_FFmpegPreprocessingTool):
        def audio_precision(self, source, *, timeout_seconds):
            facts = super().audio_precision(source, timeout_seconds=timeout_seconds)
            return facts.model_copy(update={"declared_duration_seconds": 2.0})

    manifest = _prepare_audio_forensic(
        case.request,
        PreprocessingRequirements(forensic=frozenset({ForensicCapability.AUDIO_SAMPLES})),
        OverstatedDuration(executable="ffmpeg", timeout_seconds=5),
        [],
        1.0,
        None,
    )
    window = manifest.representations[1].facts
    assert window.requested_samples == IndexRange(start=0, stop=16000)
    assert window.samples == IndexRange(start=0, stop=8000)
    assert window.first_sample_pts == 0


def test_dispatcher_numeric_audio_demand(tmp_path, monkeypatch):
    raw_config = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    source = tmp_path / "multichannel.wav"
    pcm(source, 32, channels=8, rate=192000, count=4096)
    descriptor = _audio_descriptor(
        duration_seconds=4096 / 192000, sample_rate_hz=192000, channels=8
    )
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    )
    case = _case(tmp_path / "case", source, descriptor)
    processor = PreprocessingDispatcher(AppConfig.model_validate(raw_config))
    prepared = processor.prepare(
        case.request,
        PreprocessingRequirements(forensic=frozenset({ForensicCapability.AUDIO_SPECTRAL})),
    )
    spectra = [
        r.facts
        for r in prepared.forensic.representations
        if isinstance(r.facts, SpectralWindowDescriptor)
    ]
    assert len(spectra) == 1
    assert spectra[0].data.shape == (1, 8, 2049)

    def forbidden(*args, **kwargs):
        pytest.fail("production legacy demand must not invoke precision producers")

    monkeypatch.setattr(_FFmpegPreprocessingTool, "audio_precision", forbidden)
    legacy = _case(tmp_path / "legacy", source, descriptor)
    assert processor.prepare(legacy.request).forensic is None


@pytest.mark.parametrize(
    "stderr,suffix",
    [
        (b"private path: Invalid data found when processing input", "malformed_media"),
        (b"private decoder details", "decoder"),
    ],
)
def test_audio_malformed_media_distinct_from_decoder_failure(monkeypatch, tmp_path, stderr, suffix):
    monkeypatch.setattr(
        decoder, "run_bounded_process", lambda *a, **k: ProcessResult(1, b"", stderr)
    )
    with pytest.raises(PreprocessingError) as caught:
        probe_audio(tmp_path / "input", executable="ffprobe", timeout=1)
    assert caught.value.phase == f"audio_precision_probe_{suffix}"
    assert "private" not in str(caught.value)


class TimingSettings(BaseModel):
    pass


def _timing_facts(**updates):
    return StreamTimingFacts(
        **{
            "stream_index": 0,
            "stream_kind": "video",
            "time_base": TimeBase(numerator=1, denominator=1000),
            "start_tick": 0,
            "duration_ticks": 20_000,
        }
        | updates
    )


def _mock_timing_probe(monkeypatch, payload):
    monkeypatch.setattr(decoder, "_probe_timing", lambda *args, **kwargs: payload)


def _packet_timing(monkeypatch, rows):
    _mock_timing_probe(monkeypatch, {"packets": rows})
    return decoder.probe_timing_records(
        Path("source"),
        _timing_facts(),
        TimingInterval(start=0, stop=2000),
        0,
        "packet",
        timeout=5,
    )


@pytest.mark.parametrize("base", ["1/25", "1/90000", "1001/30000"])
def test_exact_ticks_do_not_depend_on_float(base):
    time_base = decoder._timing_base(base)
    ticks = (1 << 62) + 1
    num, den = map(int, base.split("/"))
    assert time_base.seconds(ticks) == Fraction(ticks * num, den)
    assert time_base.seconds(ticks + 1) - time_base.seconds(ticks) == Fraction(num, den)


@pytest.mark.parametrize(
    "value",
    ["1/0", "0/1", "-1/25", "1/-25", "1/2147483648", "NaN", "inf", "1/2/raw", True, 0.5, None],
)
def test_malformed_time_base_is_sanitized(value):
    with pytest.raises(PreprocessingError) as error:
        decoder._timing_base(value)
    assert error.value.phase == "timing_malformed_rational"


@pytest.mark.parametrize("value", [True, 1.0, 1 << 63, -(1 << 63), "1.2", "x", "9" * 30])
def test_invalid_ticks_rejected(value):
    with pytest.raises(ValueError):
        decoder._timing_integer(value)


def test_packet_order_missing_fields_duration_and_large_ticks(monkeypatch):
    huge = (1 << 60) + 1
    descriptor, values = _packet_timing(
        monkeypatch,
        [
            {"stream_index": 0, "pts": huge, "dts": huge - 2, "duration": 2},
            {"stream_index": 0, "pts": huge - 1, "dts": huge - 1, "duration": 1},
            {"stream_index": 0, "pts": "N/A", "dts": huge},
            {"stream_index": 0, "pts": huge + 2},
        ],
    )
    assert values[:, 0].tolist() == [huge, huge - 1, 0, huge + 2]
    assert values[:, 1].tolist() == [huge - 2, huge - 1, huge, 0]
    assert values[:, 3].tolist() == [0, 1, 2, 3]
    assert values[:, 4].tolist() == [7, 7, 2, 1]
    assert descriptor.coverage == "unknown"
    assert descriptor.decode_operation_id is None
    with pytest.raises(ValueError):
        values.setflags(write=True)


def test_frame_facts_keep_best_effort_and_packet_duration_separate(monkeypatch):
    _mock_timing_probe(
        monkeypatch,
        {
            "frames": [
                {
                    "stream_index": 0,
                    "best_effort_timestamp": 12,
                    "pkt_dts": 10,
                    "duration": 3,
                    "pkt_duration": 2,
                    "key_frame": 0,
                    "pict_type": "B",
                },
                {
                    "stream_index": 0,
                    "pts": 13,
                    "best_effort_timestamp": 14,
                    "key_frame": 1,
                    "pict_type": "UNRECOGNIZED",
                },
            ]
        },
    )
    descriptor, values = decoder.probe_timing_records(
        Path("x"),
        _timing_facts(),
        TimingInterval(start=0, stop=20),
        0,
        "frame",
        timeout=5,
    )
    assert values[0].tolist() == [0, 10, 3, 0, 126, 12, 2, 0, 3]
    assert values[1, 0] == 13 and values[1, 5] == 14
    assert not values[1, 4] & 64
    assert descriptor.first_tick is None and descriptor.last_tick == 13
    assert descriptor.decode_operation_id is not None
    assert descriptor.coverage == "unknown"


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (1000, [(0, 1000)]),
        (3000, [(0, 3000)]),
        (20000, [(0, 2000), (9000, 11000), (18000, 20000)]),
        (None, [(0, 2000)]),
    ],
)
@pytest.mark.parametrize("start", [0, -1000, 7000])
def test_regions_bound_short_overlap_and_long_unsampled_gaps(duration, expected, start):
    regions = decoder.select_timing_regions(
        _timing_facts(duration_ticks=duration, start_tick=start)
    )
    assert [(r.start, r.stop) for r in regions] == [(a + start, b + start) for a, b in expected]


def test_nonzero_and_negative_starts_are_preserved():
    regions = decoder.select_timing_regions(_timing_facts(start_tick=-100, duration_ticks=1000))
    assert regions == (TimingInterval(start=-100, stop=900),)
    assert decoder._timing_seek(-1, TimeBase(numerator=1, denominator=3)) == "-0.333334"


@pytest.mark.parametrize(
    ("rows", "status", "first", "last"),
    [
        ([], "empty", None, None),
        ([{"pts": 500, "duration": 10}], "partial", 500, 500),
        ([{"pts": -10, "duration": 2010}], "envelope", -10, -10),
        ([{"dts": 10}], "unknown", None, None),
    ],
)
def test_requested_vs_observed_coverage(monkeypatch, rows, status, first, last):
    descriptor, _ = _packet_timing(monkeypatch, [{"stream_index": 0, **r} for r in rows])
    assert descriptor.coverage == status
    assert (descriptor.first_tick, descriptor.last_tick) == (first, last)
    assert descriptor.requested == TimingInterval(start=0, stop=2000)
    assert descriptor.stop_reason == "packet_budget_or_eof"
    assert descriptor.record_count == len(rows)
    assert (descriptor.data is None) == (not rows)


@pytest.mark.parametrize("count", [256, 257])
def test_packet_record_ceiling(monkeypatch, count):
    rows = [{"stream_index": 0, "pts": i} for i in range(count)]
    if count == 257:
        with pytest.raises(PreprocessingError) as error:
            _packet_timing(monkeypatch, rows)
        assert error.value.phase == "timing_record_count"
    else:
        assert _packet_timing(monkeypatch, rows)[0].record_count == count


@pytest.mark.parametrize(
    "rows",
    [
        None,
        {},
        [1],
        [{"stream_index": 1}],
        [{"stream_index": 0, "duration": -1}],
        [{"stream_index": 0, "pts": True}],
    ],
)
def test_malformed_probe_records(monkeypatch, rows):
    with pytest.raises(PreprocessingError) as error:
        _packet_timing(monkeypatch, rows)
    assert error.value.phase == "timing_malformed_records"


@pytest.mark.parametrize(
    ("error", "kind", "phase"),
    [
        (ProcessTimeoutError(), "media_tool", "timing_probe_timeout"),
        (ProcessOutputLimitError(), "resource_limit", "timing_probe_overflow"),
        (
            ProcessInfrastructureError("termination", _cleanup_safety_barrier=True),
            "infrastructure",
            "timing_probe_process",
        ),
    ],
)
def test_existing_process_failure_mapping_and_cleanup_barrier(
    monkeypatch, tmp_path, error, kind, phase
):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(decoder, "run_bounded_process", fail)
    with pytest.raises(PreprocessingError) as raised:
        decoder.probe_timing_stream(tmp_path / "private", "video", frames=False, timeout=5)
    assert (raised.value.kind, raised.value.phase) == (kind, phase)
    assert raised.value._cleanup_safety_barrier == getattr(error, "_cleanup_safety_barrier", None)
    assert "private" not in str(raised.value)


@pytest.mark.parametrize(
    ("stdout", "stderr", "code", "phase"),
    [
        (b"{", b"", 0, "timing_malformed_probe"),
        (b"[]", b"", 0, "timing_malformed_probe"),
        (b"{}", b"private warning", 0, "timing_probe_diagnostic"),
        (
            b"",
            b"Invalid data found when processing input private",
            1,
            "timing_probe_malformed_media",
        ),
        (b"", b"private", 1, "timing_probe_decoder"),
    ],
)
def test_probe_failure_payload_never_escapes(monkeypatch, tmp_path, stdout, stderr, code, phase):
    monkeypatch.setattr(
        decoder, "run_bounded_process", lambda *args, **kwargs: ProcessResult(code, stdout, stderr)
    )
    with pytest.raises(PreprocessingError) as error:
        decoder.probe_timing_stream(tmp_path / "private", "video", frames=False, timeout=5)
    assert error.value.phase == phase
    assert "private" not in str(error.value)


def test_probe_uses_only_allowlisted_fields_and_bounds(monkeypatch, tmp_path):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return ProcessResult(0, b'{"packets": []}', b"")

    monkeypatch.setattr(decoder, "run_bounded_process", run)
    decoder.probe_timing_records(
        tmp_path / "x",
        _timing_facts(),
        TimingInterval(start=9000, stop=11000),
        1,
        "packet",
        timeout=0.5,
    )
    args, kwargs = calls[0]
    assert args[args.index("-read_intervals") + 1] == "9.000000%+#256"
    assert args[args.index("-show_entries") + 1] == (
        "packet=stream_index,pts,dts,duration:frame_side_data="
    )
    assert "-show_streams" not in args and "-show_format" not in args
    assert kwargs["timeout_seconds"] == 0.5
    assert kwargs["stdout_limit_bytes"] == kwargs["stderr_limit_bytes"] == 256 * 1024


def _timing_fixture_video(path, *, duration=1, bframes=0, variable=False, audio=False, offset=0):
    arguments = ["-f", "lavfi", "-i", f"testsrc2=size=64x48:rate=25:duration={duration}"]
    if audio:
        arguments += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=8000:duration={duration}",
        ]
    if variable:
        arguments += ["-vf", "select='if(lt(t,0.5),1,not(mod(n,3)))'", "-fps_mode", "vfr"]
    arguments += ["-c:v", "mpeg4", "-bf", str(bframes), "-g", "25"]
    if audio:
        arguments += ["-c:a", "aac"]
    if offset:
        arguments += ["-output_ts_offset", str(offset)]
    _run_ffmpeg([*arguments, str(path)])


@pytest.mark.parametrize(
    ("bframes", "variable", "audio", "offset", "duration"),
    [
        (0, False, False, 0, 1),
        (2, False, False, 0, 1),
        (0, True, False, 0, 1),
        (0, False, True, 0, 1),
        (0, False, False, 5, 1),
        (0, False, False, 0, 0.08),
    ],
)
def test_generated_video_packet_and_decoded_frame_observations(
    tmp_path, bframes, variable, audio, offset, duration
):
    path = tmp_path / "video.mp4"
    _timing_fixture_video(
        path, bframes=bframes, variable=variable, audio=audio, offset=offset, duration=duration
    )
    stream = decoder.probe_timing_stream(path, "video", frames=True, timeout=5)
    requested = decoder.select_timing_regions(stream)[0]
    packet, pv = decoder.probe_timing_records(path, stream, requested, 0, "packet", timeout=5)
    frame, fv = decoder.probe_timing_records(path, stream, requested, 0, "frame", timeout=5)
    assert packet.record_count == frame.record_count > 0
    assert len(pv) <= 256 and len(fv) <= 512
    assert np.all(pv[:, 4] & 3 == 3)
    assert np.any(pv[:, 0] != pv[:, 1]) if bframes else np.all(pv[:, 0] == pv[:, 1])
    assert np.any(fv[:, 8] == 3) if bframes else np.all(fv[:, 8] != 3)
    if variable:
        assert len(set(np.diff(fv[:, 0]))) > 1
    elif duration > 0.1:
        assert len(set(np.diff(fv[:, 0]))) == 1
    if offset:
        assert stream.time_base.seconds(stream.start_tick) == offset
        assert frame.first_tick == stream.start_tick
    observed_audio = decoder.probe_timing_stream(path, "audio", frames=False, timeout=5)
    assert (observed_audio is not None) == audio
    if observed_audio:
        _, av = decoder.probe_timing_records(
            path,
            observed_audio,
            decoder.select_timing_regions(observed_audio)[0],
            0,
            "packet",
            timeout=5,
        )
        assert len(av) > 0


def test_real_middle_seek_is_not_claimed_as_exact_and_long_media_is_bounded(tmp_path):
    path = tmp_path / "long.mp4"
    _timing_fixture_video(path, duration=15, bframes=2)
    stream = decoder.probe_timing_stream(path, "video", frames=True, timeout=5)
    regions = decoder.select_timing_regions(stream)
    assert len(regions) == 3
    observed = []
    for region, interval in enumerate(regions):
        descriptor, values = decoder.probe_timing_records(
            path, stream, interval, region, "packet", timeout=5
        )
        assert descriptor.record_count <= 256
        observed.append(descriptor)
        assert descriptor.first_tick == values[0, 0]
    assert observed[1].requested.start != observed[1].first_tick
    assert observed[0].record_count == 256


@pytest.mark.parametrize("truncated", [False, True])
def test_real_malformed_truncated_media(tmp_path, truncated):
    path = tmp_path / "bad.mp4"
    if truncated:
        _timing_fixture_video(path)
        path.write_bytes(path.read_bytes()[:100])
    else:
        path.write_bytes(b"not media")
    with pytest.raises(PreprocessingError) as error:
        decoder.probe_timing_stream(path, "video", frames=True, timeout=5)
    assert error.value.kind == "decode"


@pytest.mark.parametrize("audio", [True, False])
def test_timing_only_dispatch_never_decodes_precision_audio_and_legacy_unchanged(
    tmp_path, monkeypatch, audio
):
    source = tmp_path / "video.mp4"
    _timing_fixture_video(source, audio=audio)
    descriptor = _video_descriptor(duration_seconds=1, width=64, height=48, fps=25, has_audio=audio)
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    )
    config = AppConfig.model_validate(
        yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    )
    dispatcher = PreprocessingDispatcher(config)

    def forbidden(*args, **kwargs):
        pytest.fail("timing-only request must not decode source-precision audio")

    monkeypatch.setattr(decoder._FFmpegPreprocessingTool, "audio_precision", forbidden)
    monkeypatch.setattr(decoder._FFmpegPreprocessingTool, "precision_window", forbidden)
    case = _case(tmp_path / "timing", source, descriptor)
    prepared = dispatcher.prepare(
        case.request,
        PreprocessingRequirements(forensic=frozenset({ForensicCapability.TIMING_RECORDS})),
    )
    assert prepared.forensic is not None
    assert len(prepared.forensic.representations) == (5 if audio else 3)
    assert all(
        r.facts.kind in ("stream_timing", "timing_records")
        for r in prepared.forensic.representations
    )
    for r in prepared.forensic.representations:
        if isinstance(r.facts, TimingRecordsDescriptor) and r.facts.data:
            artifact = next(
                a for a in prepared.artifacts if a.artifact_id == r.facts.data.artifact_id
            )
            payload = _artifact_path(case.registry, artifact).read_bytes()
            values = np.frombuffer(payload, dtype="<i8").reshape(r.facts.data.shape)
            decoder.validate_timing_values(r.facts, values)
    monkeypatch.setattr(decoder._FFmpegPreprocessingTool, "timing_stream", forbidden)
    legacy_case = _case(tmp_path / "legacy", source, descriptor)
    legacy = dispatcher.prepare(legacy_case.request)
    assert legacy.forensic is None
    assert legacy.metadata == {k: v for k, v in prepared.metadata.items() if k != "forensic"}
    old_frames = [a for a in legacy.artifacts if a.artifact_type == "sampled_frame"]
    new_frames = [a for a in prepared.artifacts if a.artifact_type == "sampled_frame"]
    assert len(old_frames) == len(new_frames)
    for old, new in zip(old_frames, new_frames, strict=True):
        assert (
            _artifact_path(legacy_case.registry, old).read_bytes()
            == _artifact_path(case.registry, new).read_bytes()
        )
    case.cleanup()
    legacy_case.cleanup()


@pytest.mark.parametrize(("column", "value"), [(3, 2), (4, 128), (5, 1), (2, -1), (7, 2)])
def test_analyzer_reader_rejects_malformed_timing_artifact(tmp_path, monkeypatch, column, value):
    descriptor, values = _packet_timing(
        monkeypatch, [{"stream_index": 0, "pts": 0, "dts": 0, "duration": 2}]
    )
    provenance = RepresentationProvenance(
        producer="ffprobe_timing",
        producer_version="1",
        profile="bounded_packets_frames",
        profile_version="1",
    )
    file = _video_descriptor(duration_seconds=1, width=64, height=48, fps=25, has_audio=False)
    manifest = ForensicManifest(
        source_sha256=file.sha256,
        media_type=MediaType.VIDEO,
        representations=tuple(
            ForensicRepresentation(provenance=provenance, facts=f)
            for f in (_timing_facts(), descriptor)
        ),
    )
    path = tmp_path / "decoder.raw"
    broken = values.copy()
    broken[0, column] = value
    path.write_bytes(broken.tobytes())
    request = AnalyzerRequest(
        analysis_id="timing",
        media_type=MediaType.VIDEO,
        file_facts=_AnalyzerFileFacts.from_validated_file(file),
        source=_ReadOnlyAnalyzerInput(tmp_path / "unused"),
        settings=TimingSettings(),
        timeout_seconds=1,
        metadata={"forensic": manifest.to_metadata()},
        artifacts=(
            AnalyzerArtifactInput(
                artifact_id=descriptor.data.artifact_id,
                artifact_type="timing_numeric",
                content=_ReadOnlyAnalyzerInput(path),
                format="forensic_raw",
            ),
        ),
    )
    with pytest.raises(ValueError):
        request.read_numeric(descriptor.data)


def test_preflight_rejects_budget_before_packet_decode(tmp_path):
    source = tmp_path / "video.mp4"
    _timing_fixture_video(source)
    descriptor = _video_descriptor(duration_seconds=1, width=64, height=48, fps=25, has_audio=False)
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    )
    case = _case(tmp_path / "case", source, descriptor)
    budget = _artifact_budget(MediaType.VIDEO, max_size_mb=1)
    with budget.open_output(tmp_path / "spent") as target:
        target.write(bytes(1_048_576 - 100))
    request = replace(case.request, artifact_budget=budget)

    class NoRecords(decoder._FFmpegPreprocessingTool):
        def timing_records(self, *args, **kwargs):
            pytest.fail("budget preflight must precede packet/frame decode")

    with pytest.raises(PreprocessingError) as error:
        _prepare_timing_forensic(
            request,
            PreprocessingRequirements(forensic=frozenset({ForensicCapability.TIMING_RECORDS})),
            NoRecords(executable="ffmpeg", timeout_seconds=5),
            [],
            None,
        )
    assert error.value.kind == "resource_limit"
    assert case.registry.events == []
    case.cleanup()


@pytest.mark.parametrize(
    "updates",
    [
        {"time_base": "1/0"},
        {"duration_ts": "-1"},
        {"start_pts": 1.5},
        {"duration": "-0.1"},
        {"start_time": "NaN"},
        {"index": True},
    ],
)
def test_stream_rejects_invalid_timing_fields(monkeypatch, updates):
    _mock_timing_probe(
        monkeypatch,
        {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "time_base": "1/25",
                    "start_pts": 0,
                    "duration_ts": 25,
                }
                | updates
            ]
        },
    )
    with pytest.raises(PreprocessingError):
        decoder.probe_timing_stream(Path("source"), "video", frames=False, timeout=5)


def test_stream_preserves_exact_declared_times_without_promoting_them_to_ticks(monkeypatch):
    _mock_timing_probe(
        monkeypatch,
        {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "time_base": "1/90000",
                    "start_time": "-0.123456",
                    "duration": "10.000001",
                    "avg_frame_rate": "30000/1001",
                    "r_frame_rate": "0/0",
                    "tags": {"private": "discarded"},
                }
            ]
        },
    )
    stream = decoder.probe_timing_stream(Path("source"), "video", frames=False, timeout=5)
    assert stream.start_tick is None and stream.duration_ticks is None
    assert Fraction(stream.declared_start.numerator, stream.declared_start.denominator) == Fraction(
        "-0.123456"
    )
    assert Fraction(
        stream.declared_duration.numerator, stream.declared_duration.denominator
    ) == Fraction("10.000001")
    assert stream.avg_frame_rate == TimingRate(numerator=30000, denominator=1001)
    assert stream.r_frame_rate is None
    assert "private" not in stream.model_dump_json()


@pytest.mark.parametrize(
    ("payload", "phase"),
    [
        ({"streams": []}, None),
        ({"streams": [{"index": 0, "codec_type": "video"}]}, "timing_unsupported_time_base"),
        ({"streams": [1]}, "timing_malformed_stream"),
        ({}, "timing_malformed_stream"),
    ],
)
def test_unsupported_or_missing_stream(monkeypatch, payload, phase):
    _mock_timing_probe(monkeypatch, payload)
    if phase:
        with pytest.raises(PreprocessingError) as error:
            decoder.probe_timing_stream(Path("x"), "video", frames=False, timeout=5)
        assert error.value.phase == phase
    else:
        assert decoder.probe_timing_stream(Path("x"), "video", frames=False, timeout=5) is None


@pytest.mark.parametrize("count", [512, 513])
def test_frame_record_count_independent_of_input_packet_bound(monkeypatch, count):
    _mock_timing_probe(
        monkeypatch, {"frames": [{"stream_index": 0, "pts": i} for i in range(count)]}
    )

    def probe():
        return decoder.probe_timing_records(
            Path("x"), _timing_facts(), TimingInterval(start=0, stop=2000), 0, "frame", timeout=5
        )

    if count == 513:
        with pytest.raises(PreprocessingError) as error:
            probe()
        assert error.value.kind == "resource_limit"
    else:
        assert probe()[0].record_count == 512


@pytest.mark.parametrize("pipe", [1, 2])
def test_timing_real_pipe_overflow_reaps_child(tmp_path, monkeypatch, pipe):
    import subprocess

    from test_bounded_process import python_child

    from fakedetector.core import _bounded_process as bounded

    real_runner = decoder.run_bounded_process
    real_popen = subprocess.Popen
    children = []

    def record(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    def run(args, **kwargs):
        return real_runner(
            python_child(f'import os,time; os.write({pipe}, b"x"*300000); time.sleep(5)'), **kwargs
        )

    monkeypatch.setattr(bounded.subprocess, "Popen", record)
    monkeypatch.setattr(decoder, "run_bounded_process", run)
    with pytest.raises(PreprocessingError) as error:
        decoder.probe_timing_stream(tmp_path / "x", "video", frames=False, timeout=2)
    assert error.value.phase == "timing_probe_overflow"
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdout.closed and children[0].stderr.closed


def test_stream_only_demand_does_not_enumerate_packets(tmp_path):
    source = tmp_path / "source.mp4"
    _timing_fixture_video(source)
    descriptor = _video_descriptor(duration_seconds=1, width=64, height=48, fps=25, has_audio=False)
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    )
    case = _case(tmp_path / "case", source, descriptor)

    class StreamsOnly(decoder._FFmpegPreprocessingTool):
        def timing_records(self, *args, **kwargs):
            pytest.fail("stream-only demand must not enumerate records")

    result = _prepare_timing_forensic(
        case.request,
        PreprocessingRequirements(forensic=frozenset({ForensicCapability.STREAM_TIMING})),
        StreamsOnly(executable="ffmpeg", timeout_seconds=5),
        [],
        None,
    )
    assert len(result) == 1 and isinstance(result[0].facts, StreamTimingFacts)
    assert case.registry.events == []
    case.cleanup()


def test_dense_pixel_reference_requires_same_decode_operation():
    from test_stage5_internal_models import _manifest, _video_facts

    stream, records, dense = _video_facts()
    other_decode = dense.model_copy(update={"decode_operation_id": "other_decode"})
    with pytest.raises(ValueError):
        _manifest(stream, records, other_decode, media_type=MediaType.VIDEO)


@pytest.mark.parametrize("field", ["avg_frame_rate", "r_frame_rate"])
def test_frame_rate_is_semantically_distinct_from_time_base(monkeypatch, field):
    _mock_timing_probe(
        monkeypatch,
        {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "time_base": "1/90000",
                    field: "30000/1001",
                }
            ]
        },
    )
    stream = decoder.probe_timing_stream(Path("source"), "video", frames=False, timeout=5)
    rate = getattr(stream, field)
    assert type(rate) is TimingRate
    assert not isinstance(rate, TimeBase) and not hasattr(rate, "seconds")
    assert Fraction(rate.numerator, rate.denominator) == Fraction(30000, 1001)
    assert type(stream.time_base) is TimeBase
    assert stream.time_base.seconds(90000) == 1
    assert StreamTimingFacts.model_validate_json(stream.model_dump_json()) == stream
    with pytest.raises(ValueError):
        _timing_facts(**{field: TimeBase(numerator=30000, denominator=1001)})
    with pytest.raises(ValueError):
        _timing_facts(time_base=rate)


@pytest.mark.parametrize("value", [None, "N/A", "0/0", "0/1"])
def test_unspecified_frame_rate_is_missing(value):
    assert decoder._timing_rate(value) is None


@pytest.mark.parametrize(
    "value",
    ["1/0", "-25/1", "25/-1", "-25/-1", "NaN", "25.0", "2147483648/1", "1/2147483648", True, 25],
)
def test_invalid_frame_rates_are_rejected(value):
    with pytest.raises(PreprocessingError) as error:
        decoder._timing_rate(value)
    assert error.value.phase == "timing_malformed_rational"


@pytest.mark.parametrize("component", ["numerator", "denominator"])
@pytest.mark.parametrize("value", [0, -1, 1 << 31, True, 1.0])
def test_frame_rate_model_preserves_strict_positive_integer_bounds(component, value):
    with pytest.raises(ValueError):
        TimingRate(**({"numerator": 25, "denominator": 1} | {component: value}))


def test_frame_rate_accepts_existing_maximum_integer_bounds():
    rate = decoder._timing_rate("2147483647/2147483647")
    assert rate == TimingRate(numerator=(1 << 31) - 1, denominator=(1 << 31) - 1)


def test_merged_timing_region_has_one_packet_and_one_frame_probe(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    _timing_fixture_video(source, duration=3)
    descriptor = _video_descriptor(duration_seconds=3, width=64, height=48, fps=25, has_audio=False)
    descriptor = descriptor.model_copy(
        update={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    )
    case = _case(tmp_path / "case", source, descriptor)
    calls = []
    original = decoder._FFmpegPreprocessingTool.timing_records

    def observed(self, source, facts, requested, region, kind, *, timeout_seconds):
        calls.append((requested, region, kind))
        return original(
            self, source, facts, requested, region, kind, timeout_seconds=timeout_seconds
        )

    monkeypatch.setattr(decoder._FFmpegPreprocessingTool, "timing_records", observed)
    artifacts = []
    result = _prepare_timing_forensic(
        case.request,
        PreprocessingRequirements(forensic=frozenset({ForensicCapability.TIMING_RECORDS})),
        decoder._FFmpegPreprocessingTool(executable="ffmpeg", timeout_seconds=5),
        artifacts,
        None,
    )
    assert len(result) == 3
    stream = result[0].facts
    requested = TimingInterval(
        start=stream.start_tick, stop=stream.start_tick + stream.duration_ticks
    )
    assert calls == [(requested, 0, "packet"), (requested, 0, "frame")]
    assert len(artifacts) == 2
    case.cleanup()
