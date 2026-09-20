"""Stage 5 Increment 3 preprocessing behavior and capability invariants."""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import BinaryIO, TypeVar, cast

import pytest
import yaml
from PIL import Image, PngImagePlugin

import fakedetector.preprocessing as preprocessing
from fakedetector._generated_artifact_budget import _GeneratedArtifactBudget
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import (
    AppConfig,
    AudioPreprocessingConfig,
    ImagePreprocessingConfig,
    VideoPreprocessingConfig,
)
from fakedetector.core._bounded_process import ProcessResult, ProcessTimeoutError
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
from fakedetector.preprocessing._errors import PreprocessingError
from fakedetector.preprocessing._media_tools import _FFmpegPreprocessingTool, _parse_jpeg
from fakedetector.preprocessing._models import (
    JpegCoefficientsDescriptor,
    OriginalImageFacts,
    PreparedArtifact,
    PreparedMedia,
)
from fakedetector.preprocessing._requirements import ForensicCapability, PreprocessingRequirements
from fakedetector.preprocessing._service import (
    AudioPreprocessor,
    ImagePreprocessor,
    PreprocessingDispatcher,
    PreprocessingRequest,
    VideoPreprocessor,
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
