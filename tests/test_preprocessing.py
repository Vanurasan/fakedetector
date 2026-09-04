"""Stage 5 Increment 3 preprocessing behavior and capability invariants."""

from __future__ import annotations

import shutil
import subprocess
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import TypeVar, cast

import pytest
from PIL import Image

import fakedetector.preprocessing as preprocessing
from fakedetector.config.models import (
    AudioPreprocessingConfig,
    ImagePreprocessingConfig,
    PreprocessingConfig,
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
            has_metadata=False,
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


def test_image_normalization_can_be_disabled_by_existing_config(tmp_path: Path) -> None:
    source_path = tmp_path / "source.png"
    with Image.new("RGB", (2, 2)) as image:
        image.save(source_path)
    case = _case(
        tmp_path,
        source_path,
        _image_descriptor(width=2, height=2, image_format="PNG", color_mode="RGB"),
    )

    prepared = ImagePreprocessor(ImagePreprocessingConfig(normalize_for_analysis=False)).prepare(
        case.request, PreprocessingRequirements()
    )

    assert prepared.artifacts == ()
    assert "normalized" not in prepared.metadata
    assert "frame_scope" not in prepared.metadata
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
    dispatcher = PreprocessingDispatcher(
        PreprocessingConfig(),
        process_timeout_seconds=10,
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
