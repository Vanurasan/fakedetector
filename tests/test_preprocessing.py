"""Stage 5 Increment 3 preprocessing behavior and capability invariants."""

from __future__ import annotations

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
from fakedetector._stage5_resources import _GeneratedArtifactBudget
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
from fakedetector.preprocessing._media_tools import _FFmpegPreprocessingTool
from fakedetector.preprocessing._models import PreparedArtifact, PreparedMedia
from fakedetector.preprocessing._requirements import PreprocessingRequirements
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
    data = normalized_path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    chunks = []
    while offset < len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunks.append(data[offset + 4 : offset + 8])
        offset += length + 12
    assert offset == len(data)
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


def test_multiframe_image_uses_first_displayed_frame_and_warns(tmp_path: Path) -> None:
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
        assert normalized.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
    assert cast(dict[str, object], prepared.metadata["source"])["frame_count"] == 2
    assert prepared.metadata["frame_scope"] == "first_frame"
    assert len(prepared.warnings) == 1
    assert "temporal behavior" in prepared.warnings[0]
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

    def complete_process(*_args: object, **kwargs: object) -> ProcessResult:
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
