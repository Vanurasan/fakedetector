"""Stage 6 real technical analyzers and candidate-to-Finding tests."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import wave
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest
import yaml
from PIL import Image, PngImagePlugin
from pydantic import BaseModel, ValidationError

from fakedetector.analyzers._audio_pcm import (
    AudioPcmQualityAnalyzer,
    AudioPcmQualitySettings,
)
from fakedetector.analyzers._catalog import (
    _real_analyzer_registrations,
    _resolve_worker_definition,
)
from fakedetector.analyzers._image_metadata import (
    ImageMetadataConsistencyAnalyzer,
    ImageMetadataConsistencySettings,
)
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.analyzers._transport import (
    _MAX_STAGE5_ANALYZER_RESULT_BYTES,
    _serialize_stage5_analyzer_result,
    _WorkerArtifact,
    _WorkerRequest,
)
from fakedetector.analyzers._video_frames import (
    VideoSampledFrameQualityAnalyzer,
    VideoSampledFrameQualitySettings,
)
from fakedetector.analyzers._worker import _SpawnedWorkerRunner, _WorkerRunKind
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalyzerResult,
    AnalyzerStatus,
    AudioTechnicalParameters,
    ImageTechnicalParameters,
    MediaType,
    VideoTechnicalParameters,
)
from fakedetector.lifecycle._stage6 import (
    Stage6FindingFormationError,
    Stage6FindingService,
)


def _request(
    source_path: Path,
    *,
    media_type: MediaType,
    technical_parameters: (
        ImageTechnicalParameters | AudioTechnicalParameters | VideoTechnicalParameters
    ),
    settings: BaseModel,
    artifacts: Sequence[AnalyzerArtifactInput] = (),
    metadata: Mapping[str, object] | None = None,
) -> AnalyzerRequest:
    extension_by_media = {
        MediaType.IMAGE: "png",
        MediaType.AUDIO: "wav",
        MediaType.VIDEO: "mp4",
    }
    mime_by_media = {
        MediaType.IMAGE: "image/png",
        MediaType.AUDIO: "audio/wav",
        MediaType.VIDEO: "video/mp4",
    }
    return AnalyzerRequest(
        analysis_id="a" * 32,
        media_type=media_type,
        file_facts=_AnalyzerFileFacts(
            extension=extension_by_media[media_type],
            declared_mime_type=mime_by_media[media_type],
            detected_mime_type=mime_by_media[media_type],
            media_type=media_type,
            size_bytes=source_path.stat().st_size,
            sha256="0" * 64,
            signature_match=True,
            safe_read=True,
            technical_parameters=technical_parameters,
        ),
        source=_ReadOnlyAnalyzerInput(source_path),
        settings=settings,
        timeout_seconds=5.0,
        artifacts=tuple(artifacts),
        metadata=metadata or {},
    )


def _image_parameters(path: Path) -> ImageTechnicalParameters:
    with Image.open(path) as image:
        return ImageTechnicalParameters(
            width=image.width,
            height=image.height,
            format=cast(str, image.format),
            color_mode=image.mode,
            frame_count=getattr(image, "n_frames", None),
            has_metadata=bool(image.info) or bool(image.getexif()),
        )


def _save_image(
    path: Path,
    *,
    size: tuple[int, int] = (8, 6),
    embedded_size: tuple[int, int] | None = None,
    orientation: int | None = None,
    software: str | None = None,
) -> None:
    image = Image.new("RGB", size, (20, 40, 60))
    kwargs: dict[str, object] = {}
    if embedded_size is not None or orientation is not None or software is not None:
        exif = Image.Exif()
        if embedded_size is not None:
            exif[0xA002], exif[0xA003] = embedded_size
        if orientation is not None:
            exif[0x0112] = orientation
        if software is not None:
            exif[0x0131] = software
        kwargs["exif"] = exif
    image.save(path, **kwargs)
    image.close()


def _image_result(path: Path) -> AnalyzerResult:
    request = _request(
        path,
        media_type=MediaType.IMAGE,
        technical_parameters=_image_parameters(path),
        settings=ImageMetadataConsistencySettings(),
    )
    analyzer = ImageMetadataConsistencyAnalyzer()
    assert analyzer.check_applicability(request).applicable
    return analyzer.analyze(request)


@pytest.mark.parametrize("suffix", [".jpg", ".png", ".webp"])
def test_image_analyzer_accepts_supported_formats_without_metadata(
    tmp_path: Path,
    suffix: str,
) -> None:
    source = tmp_path / f"source{suffix}"
    _save_image(source)

    result = _image_result(source)

    assert result.status is AnalyzerStatus.COMPLETED
    assert result.candidate_findings == []
    assert result.raw_metrics["metadata_present"] is False
    assert result.raw_metrics["embedded_dimensions_available"] is False
    assert result.score is result.score_name is None


@pytest.mark.parametrize("orientation", [1, 6, 8])
def test_image_analyzer_compares_embedded_coded_dimensions(
    tmp_path: Path,
    orientation: int,
) -> None:
    source = tmp_path / f"orientation-{orientation}.jpg"
    _save_image(source, embedded_size=(8, 6), orientation=orientation)

    result = _image_result(source)

    assert result.raw_metrics["orientation"] == orientation
    assert result.raw_metrics["embedded_dimensions_consistent"] is True
    assert result.candidate_findings == []


@pytest.mark.parametrize("orientation", [6, 8])
def test_image_analyzer_rejects_swapped_embedded_dimensions_for_display_orientation(
    tmp_path: Path,
    orientation: int,
) -> None:
    source = tmp_path / f"swapped-orientation-{orientation}.jpg"
    _save_image(source, embedded_size=(6, 8), orientation=orientation)

    result = _image_result(source)

    assert result.raw_metrics["orientation"] == orientation
    assert result.raw_metrics["embedded_dimensions_consistent"] is False
    assert result.candidate_findings[0]["type"] == "image_metadata_dimension_mismatch"


@pytest.mark.parametrize("orientation", [0, 9])
def test_image_analyzer_does_not_conclude_for_invalid_orientation(
    tmp_path: Path,
    orientation: int,
) -> None:
    source = tmp_path / f"invalid-orientation-{orientation}.jpg"
    _save_image(source, embedded_size=(6, 8), orientation=orientation)

    result = _image_result(source)

    assert result.raw_metrics["orientation"] is None
    assert result.raw_metrics["embedded_dimensions_available"] is True
    assert result.raw_metrics["embedded_dimensions_consistent"] is None
    assert result.candidate_findings == []


def test_image_analyzer_emits_only_confirmed_dimension_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "mismatch.jpg"
    _save_image(source, embedded_size=(9, 6), orientation=1)

    result = _image_result(source)

    assert result.raw_metrics["embedded_pixel_width"] == 9
    assert result.raw_metrics["embedded_pixel_height"] == 6
    assert result.raw_metrics["embedded_dimensions_consistent"] is False
    assert result.candidate_findings == [
        {
            "type": "image_metadata_dimension_mismatch",
            "localization": {"type": "file"},
            "correlation_group": "image_metadata_consistency",
            "evidence_refs": [],
        }
    ]


def test_image_software_and_long_xmp_values_do_not_leak_or_form_findings(
    tmp_path: Path,
) -> None:
    jpeg = tmp_path / "software.jpg"
    long_value = "private-value-" + "x" * 5000
    _save_image(jpeg, software=long_value)
    software_result = _image_result(jpeg)
    assert software_result.raw_metrics["software_tag_present"] is True
    assert software_result.candidate_findings == []
    assert long_value not in software_result.model_dump_json()

    png = tmp_path / "xmp.png"
    png_info = PngImagePlugin.PngInfo()
    png_info.add_itxt("XML:com.adobe.xmp", long_value)
    png_info.add_itxt("unknown_metadata", long_value[::-1])
    image = Image.new("RGB", (8, 6), (20, 40, 60))
    image.save(png, pnginfo=png_info)
    image.close()
    xmp_result = _image_result(png)
    assert xmp_result.raw_metrics["xmp_present"] is True
    assert xmp_result.candidate_findings == []
    assert long_value not in xmp_result.model_dump_json()
    assert long_value[::-1] not in xmp_result.model_dump_json()


def _write_wav(
    path: Path,
    samples: Iterable[int],
    *,
    channels: int = 1,
    sample_rate_hz: int = 8000,
) -> None:
    values = tuple(samples)
    payload = struct.pack(f"<{len(values)}h", *values)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(sample_rate_hz)
        target.writeframes(payload)


def _audio_artifact(
    path: Path,
    artifact_id: str,
    artifact_type: str,
    *,
    start: float | None = None,
    end: float | None = None,
) -> AnalyzerArtifactInput:
    return AnalyzerArtifactInput(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        content=_ReadOnlyAnalyzerInput(path),
        format="wav",
        start_time_seconds=start,
        end_time_seconds=end,
    )


def _audio_request(
    normalized: Path,
    fragments: Sequence[AnalyzerArtifactInput] = (),
    *,
    channels: int = 1,
    threshold: float = 0.001,
) -> AnalyzerRequest:
    return _request(
        normalized,
        media_type=MediaType.AUDIO,
        technical_parameters=AudioTechnicalParameters(
            duration_seconds=1.0,
            sample_rate_hz=8000,
            channels=channels,
            codec="pcm_s16le",
        ),
        settings=AudioPcmQualitySettings(full_scale_sample_ratio_threshold=threshold),
        artifacts=(
            _audio_artifact(normalized, "audio_normalized", "normalized_audio"),
            *fragments,
        ),
    )


def test_audio_silence_and_signed16_edge_metrics(tmp_path: Path) -> None:
    silence = tmp_path / "silence.wav"
    _write_wav(silence, [0] * 100)
    silence_result = AudioPcmQualityAnalyzer().analyze(_audio_request(silence))
    assert silence_result.raw_metrics["digital_silence_ratio"] == 1.0
    assert silence_result.raw_metrics["peak_abs_normalized"] == 0.0
    assert silence_result.raw_metrics["rms_normalized"] == 0.0

    edges = tmp_path / "edges.wav"
    _write_wav(edges, [-32768, 32767])
    edge_result = AudioPcmQualityAnalyzer().analyze(_audio_request(edges))
    assert edge_result.raw_metrics["peak_abs_normalized"] == 1.0
    assert edge_result.raw_metrics["rms_normalized"] == pytest.approx(
        math.sqrt((32768**2 + 32767**2) / 2) / 32768
    )
    assert edge_result.raw_metrics["dc_offset_abs_normalized"] == pytest.approx(0.5 / 32768)
    assert edge_result.raw_metrics["full_scale_sample_ratio"] == 1.0


def test_audio_clean_sine_rms_peak_and_stereo_sample_semantics(tmp_path: Path) -> None:
    sine = tmp_path / "sine.wav"
    samples = [int(12000 * math.sin(2 * math.pi * index / 100)) for index in range(1000)]
    _write_wav(sine, samples)
    result = AudioPcmQualityAnalyzer().analyze(_audio_request(sine))
    expected_rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768
    assert result.raw_metrics["sample_count"] == len(samples)
    assert result.raw_metrics["peak_abs_normalized"] == max(map(abs, samples)) / 32768
    assert result.raw_metrics["rms_normalized"] == pytest.approx(expected_rms)

    stereo = tmp_path / "stereo.wav"
    stereo_samples = [value for _ in range(20) for value in (32767, 0)]
    _write_wav(stereo, stereo_samples, channels=2)
    fragment = _audio_artifact(stereo, "fragment", "audio_fragment", start=2.0, end=3.0)
    stereo_result = AudioPcmQualityAnalyzer().analyze(
        _audio_request(stereo, (fragment,), channels=2)
    )
    assert stereo_result.raw_metrics["channels"] == 2
    assert stereo_result.raw_metrics["sample_count"] == 40
    assert stereo_result.raw_metrics["full_scale_sample_ratio"] == 0.5
    assert stereo_result.candidate_findings[0]["localization"] == {
        "type": "time_interval",
        "start_seconds": 2.0,
        "end_seconds": 3.0,
    }


@pytest.mark.parametrize(
    ("sample_count", "full_scale_count", "expected_candidate"),
    [(1001, 1, False), (1000, 1, True), (1000, 2, True)],
)
def test_audio_saturation_threshold_boundary(
    tmp_path: Path,
    sample_count: int,
    full_scale_count: int,
    expected_candidate: bool,
) -> None:
    source = tmp_path / f"boundary-{sample_count}-{full_scale_count}.wav"
    samples = [32767] * full_scale_count + [1] * (sample_count - full_scale_count)
    _write_wav(source, samples)
    fragment = _audio_artifact(source, "fragment", "audio_fragment", start=0.0, end=1.0)

    result = AudioPcmQualityAnalyzer().analyze(_audio_request(source, (fragment,)))

    assert bool(result.candidate_findings) is expected_candidate


def test_audio_selects_deterministic_top_16_fragments(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized.wav"
    _write_wav(normalized, [0] * 100)
    fragments: list[AnalyzerArtifactInput] = []
    for index in range(18):
        fragment_path = tmp_path / f"fragment-{index}.wav"
        _write_wav(fragment_path, [32767] + [1] * 99)
        fragments.append(
            _audio_artifact(
                fragment_path,
                f"fragment_{index:02d}",
                "audio_fragment",
                start=float(index),
                end=float(index + 1),
            )
        )

    result = AudioPcmQualityAnalyzer().analyze(_audio_request(normalized, fragments))

    assert result.raw_metrics["saturated_fragment_count"] == 18
    assert len(result.candidate_findings) == 16
    assert [candidate["evidence_refs"][0] for candidate in result.candidate_findings] == [
        f"fragment_{index:02d}" for index in range(16)
    ]
    assert len(_serialize_stage5_analyzer_result(result)) <= _MAX_STAGE5_ANALYZER_RESULT_BYTES


def test_audio_reads_waveform_in_bounded_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "long.wav"
    _write_wav(source, [1] * 10000)
    requested: list[int] = []
    original = wave.Wave_read.readframes

    def recording_readframes(reader: wave.Wave_read, count: int) -> bytes:
        requested.append(count)
        return original(reader, count)

    monkeypatch.setattr(wave.Wave_read, "readframes", recording_readframes)
    AudioPcmQualityAnalyzer().analyze(_audio_request(source))
    assert requested
    assert max(requested) == 4096
    assert len(requested) >= 3


def test_audio_and_video_applicability_require_existing_prepared_inputs(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    _write_wav(audio, [0])
    audio_request = _request(
        audio,
        media_type=MediaType.AUDIO,
        technical_parameters=AudioTechnicalParameters(
            duration_seconds=0.001,
            sample_rate_hz=8000,
            channels=1,
            codec="pcm_s16le",
        ),
        settings=AudioPcmQualitySettings(),
    )
    audio_applicability = AudioPcmQualityAnalyzer().check_applicability(audio_request)
    assert not audio_applicability.applicable
    assert audio_applicability.reason_code == "normalized_audio_missing"

    frame = tmp_path / "frame.png"
    _save_frame(frame, (1, 2, 3))
    video_request = _request(
        frame,
        media_type=MediaType.VIDEO,
        technical_parameters=VideoTechnicalParameters(
            duration_seconds=1.0,
            container="mp4",
            video_codec="h264",
            width=6,
            height=4,
            fps=25.0,
            has_audio=False,
        ),
        settings=VideoSampledFrameQualitySettings(),
    )
    video_applicability = VideoSampledFrameQualityAnalyzer().check_applicability(video_request)
    assert not video_applicability.applicable
    assert video_applicability.reason_code == "sampled_frames_missing"


def _save_frame(
    path: Path,
    color: tuple[int, int, int],
    *,
    size: tuple[int, int] = (6, 4),
    text: str | None = None,
) -> None:
    image = Image.new("RGB", size, color)
    png_info = None
    if text is not None:
        png_info = PngImagePlugin.PngInfo()
        png_info.add_text("note", text)
    image.save(path, pnginfo=png_info)
    image.close()


def _video_request(
    frame_paths: Sequence[Path],
    *,
    timestamps: Sequence[float] | None = None,
) -> AnalyzerRequest:
    target_times = timestamps or tuple(float(index * 2) for index in range(len(frame_paths)))
    artifacts = tuple(
        AnalyzerArtifactInput(
            artifact_id=f"frame_{index:04d}",
            artifact_type="sampled_frame",
            content=_ReadOnlyAnalyzerInput(path),
            format="png",
            start_time_seconds=target_times[index],
            frame_index=index,
        )
        for index, path in enumerate(frame_paths)
    )
    return _request(
        frame_paths[0],
        media_type=MediaType.VIDEO,
        technical_parameters=VideoTechnicalParameters(
            duration_seconds=max(target_times[-1], 0.1),
            container="mp4",
            video_codec="h264",
            width=6,
            height=4,
            fps=25.0,
            has_audio=False,
        ),
        settings=VideoSampledFrameQualitySettings(),
        artifacts=artifacts,
        metadata={"sampling_interval_seconds": 2.0, "audio_track_created": False},
    )


def test_video_one_and_distinct_samples_have_no_findings(tmp_path: Path) -> None:
    frames = [tmp_path / f"distinct-{index}.png" for index in range(3)]
    for index, path in enumerate(frames):
        _save_frame(path, (index, index + 1, index + 2))

    one = VideoSampledFrameQualityAnalyzer().analyze(_video_request(frames[:1]))
    assert one.raw_metrics["sampled_frame_count"] == 1
    assert one.raw_metrics["compared_adjacent_pair_count"] == 0
    assert one.raw_metrics["longest_exact_duplicate_run_samples"] == 1
    assert one.candidate_findings == []

    distinct = VideoSampledFrameQualityAnalyzer().analyze(_video_request(frames))
    assert distinct.raw_metrics["exact_duplicate_pair_count"] == 0
    assert distinct.candidate_findings == []


def test_video_requires_three_identical_samples_and_uses_target_times(tmp_path: Path) -> None:
    paths = [tmp_path / f"same-{index}.png" for index in range(3)]
    for path in paths:
        _save_frame(path, (10, 20, 30))

    two = VideoSampledFrameQualityAnalyzer().analyze(_video_request(paths[:2], timestamps=(1, 3)))
    assert two.raw_metrics["exact_duplicate_pair_count"] == 1
    assert two.candidate_findings == []

    three = VideoSampledFrameQualityAnalyzer().analyze(_video_request(paths, timestamps=(1, 3, 7)))
    assert three.raw_metrics["longest_exact_duplicate_run_samples"] == 3
    assert three.raw_metrics["longest_exact_duplicate_span_seconds"] == 6.0
    assert three.candidate_findings[0]["localization"] == {
        "type": "time_interval",
        "start_seconds": 1.0,
        "end_seconds": 7.0,
    }


def test_video_compares_decoded_pixels_not_png_bytes(tmp_path: Path) -> None:
    paths = [tmp_path / f"encoded-{index}.png" for index in range(3)]
    _save_frame(paths[0], (10, 20, 30), text="first encoding")
    _save_frame(paths[1], (10, 20, 30), text="second encoding")
    _save_frame(paths[2], (10, 20, 30), text="third encoding")
    assert len({path.read_bytes() for path in paths}) == 3

    result = VideoSampledFrameQualityAnalyzer().analyze(_video_request(paths))

    assert result.raw_metrics["exact_duplicate_pair_count"] == 2
    assert result.candidate_findings[0]["type"] == "repeated_sampled_video_frames"


def test_video_reports_dimension_variants_without_audio_dependency(tmp_path: Path) -> None:
    first = tmp_path / "small.png"
    second = tmp_path / "large.png"
    _save_frame(first, (1, 2, 3), size=(6, 4))
    _save_frame(second, (1, 2, 3), size=(7, 4))

    result = VideoSampledFrameQualityAnalyzer().analyze(
        _video_request((first, second), timestamps=(0.5, 4.5))
    )

    assert result.raw_metrics["dimension_variant_count"] == 2
    assert result.raw_metrics["first_target_timestamp_seconds"] == 0.5
    assert result.raw_metrics["last_target_timestamp_seconds"] == 4.5
    assert result.candidate_findings[0]["type"] == "video_sample_resolution_change"
    assert result.candidate_findings[0]["localization"] == {
        "type": "time_interval",
        "start_seconds": 0.5,
        "end_seconds": 4.5,
    }


def test_real_results_are_json_safe_finite_unscored_and_candidate_bounded(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "image.jpg"
    _save_image(image_path, embedded_size=(9, 6))
    image_result = _image_result(image_path)

    audio_path = tmp_path / "audio.wav"
    _write_wav(audio_path, [32767] + [0] * 999)
    audio_result = AudioPcmQualityAnalyzer().analyze(
        _audio_request(
            audio_path,
            (_audio_artifact(audio_path, "fragment", "audio_fragment", start=0.0, end=1.0),),
        )
    )

    frame_paths = [tmp_path / f"frame-{index}.png" for index in range(3)]
    for path in frame_paths:
        _save_frame(path, (1, 2, 3))
    video_result = VideoSampledFrameQualityAnalyzer().analyze(_video_request(frame_paths))

    for result in (image_result, audio_result, video_result):
        payload = result.model_dump(mode="json", warnings="error")
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        assert result.score is result.score_name is None
        assert len(result.candidate_findings) <= 16


def test_real_catalog_registration_and_settings_contracts() -> None:
    registrations = _real_analyzer_registrations()
    assert [registration.analyzer_id for registration in registrations] == [
        "image_metadata_consistency",
        "audio_pcm_quality",
        "video_sampled_frame_quality",
        "image_copy_move_correspondence",
    ]
    assert all(registration.analyzer_version == "1.0.0" for registration in registrations)
    assert [registration.group for registration in registrations] == [
        "metadata",
        "signal_quality",
        "sampled_frame_quality",
        "content",
    ]
    assert all(
        not registration.preprocessing_requirements.audio_spectrogram
        and not registration.preprocessing_requirements.video_audio_track
        for registration in registrations
    )
    for registration in registrations:
        definition = _resolve_worker_definition(registration.worker_key)
        assert definition is not None
        assert definition.registration() == registration
        with pytest.raises(ValidationError):
            registration.settings_model.model_validate({"unknown": True})


def test_real_catalog_builds_active_plans_through_existing_settings_mechanism() -> None:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    raw["analyzers"]["image"]["enabled"] = [
        "image_metadata_consistency",
        "image_copy_move_correspondence",
    ]
    raw["analyzers"]["audio"]["enabled"] = ["audio_pcm_quality"]
    raw["analyzers"]["video"]["enabled"] = ["video_sampled_frame_quality"]
    raw["analyzers"]["settings"] = {
        "audio_pcm_quality": {"full_scale_sample_ratio_threshold": 0.001}
    }
    registry = AnalyzerRegistry(
        AppConfig.model_validate(raw),
        _real_analyzer_registrations(),
    )

    assert [item.registration.analyzer_id for item in registry.active_plan(MediaType.IMAGE)] == [
        "image_metadata_consistency",
        "image_copy_move_correspondence",
    ]
    assert registry.active_plan(MediaType.AUDIO)[0].registration.analyzer_id == (
        "audio_pcm_quality"
    )
    assert registry.active_plan(MediaType.VIDEO)[0].registration.analyzer_id == (
        "video_sampled_frame_quality"
    )
    assert not registry.preprocessing_requirements(MediaType.AUDIO).audio_spectrogram
    assert not registry.preprocessing_requirements(MediaType.VIDEO).video_audio_track


def test_real_image_analyzer_resolves_inside_spawned_worker(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    _save_image(source)
    facts = _request(
        source,
        media_type=MediaType.IMAGE,
        technical_parameters=_image_parameters(source),
        settings=ImageMetadataConsistencySettings(),
    ).file_facts
    request = _WorkerRequest(
        worker_key="stage6.image_metadata_consistency.v1",
        analysis_id="a" * 32,
        media_type="image",
        file_facts_json=facts.model_dump_json(),
        source_path=str(source),
        artifacts=(),
        metadata_json="{}",
        warnings=(),
        settings_json="{}",
        timeout_seconds=5.0,
    )

    run = _SpawnedWorkerRunner().run(request, 5.0)

    assert run.kind is _WorkerRunKind.RESPONSE
    assert run.response is not None
    envelope = json.loads(run.response)
    assert envelope["kind"] == "result"
    assert envelope["result"]["analyzer_id"] == "image_metadata_consistency"


def test_real_audio_analyzer_reads_prepared_pcm_inside_spawned_worker(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized.wav"
    below_threshold = tmp_path / "below-threshold.wav"
    at_threshold = tmp_path / "at-threshold.wav"
    _write_wav(normalized, [0] * 8000)
    _write_wav(below_threshold, [32767] * 8 + [0] * 7992)
    _write_wav(at_threshold, [32767] * 16 + [0] * 7984)
    facts = _audio_request(normalized).file_facts
    settings = AudioPcmQualitySettings(full_scale_sample_ratio_threshold=0.002)
    request = _WorkerRequest(
        worker_key="stage6.audio_pcm_quality.v1",
        analysis_id="a" * 32,
        media_type="audio",
        file_facts_json=facts.model_dump_json(),
        source_path=str(normalized),
        artifacts=(
            _WorkerArtifact(
                artifact_id="audio_normalized",
                artifact_type="normalized_audio",
                local_path=str(normalized),
                format="wav",
            ),
            _WorkerArtifact(
                artifact_id="audio_fragment_0000",
                artifact_type="audio_fragment",
                local_path=str(below_threshold),
                format="wav",
                start_time_seconds=0.0,
                end_time_seconds=1.0,
            ),
            _WorkerArtifact(
                artifact_id="audio_fragment_0001",
                artifact_type="audio_fragment",
                local_path=str(at_threshold),
                format="wav",
                start_time_seconds=1.0,
                end_time_seconds=2.0,
            ),
        ),
        metadata_json="{}",
        warnings=(),
        settings_json=settings.model_dump_json(),
        timeout_seconds=5.0,
    )

    run = _SpawnedWorkerRunner().run(request, 5.0)

    assert run.kind is _WorkerRunKind.RESPONSE
    assert run.response is not None
    envelope = json.loads(run.response)
    result = envelope["result"]
    assert envelope["kind"] == "result"
    assert result["analyzer_id"] == "audio_pcm_quality"
    assert result["raw_metrics"]["sample_count"] == 8000
    assert result["raw_metrics"]["saturated_fragment_count"] == 1
    assert result["candidate_findings"][0]["evidence_refs"] == ["audio_fragment_0001"]
    assert result["candidate_findings"][0]["localization"] == {
        "type": "time_interval",
        "start_seconds": 1.0,
        "end_seconds": 2.0,
    }


def test_real_video_analyzer_reads_sampled_frames_inside_spawned_worker(tmp_path: Path) -> None:
    frame_paths = [tmp_path / f"spawned-frame-{index}.png" for index in range(3)]
    for index, path in enumerate(frame_paths):
        _save_frame(path, (10, 20, 30), text=f"encoding-{index}")
    timestamps = (1.5, 3.5, 5.5)
    facts = _video_request(frame_paths, timestamps=timestamps).file_facts
    request = _WorkerRequest(
        worker_key="stage6.video_sampled_frame_quality.v1",
        analysis_id="a" * 32,
        media_type="video",
        file_facts_json=facts.model_dump_json(),
        source_path=str(frame_paths[0]),
        artifacts=tuple(
            _WorkerArtifact(
                artifact_id=f"sampled_frame_{index:04d}",
                artifact_type="sampled_frame",
                local_path=str(path),
                format="png",
                start_time_seconds=timestamps[index],
                frame_index=(index + 1) * 10,
            )
            for index, path in enumerate(frame_paths)
        ),
        metadata_json=json.dumps({"sampling_interval_seconds": 2.0}),
        warnings=(),
        settings_json=VideoSampledFrameQualitySettings().model_dump_json(),
        timeout_seconds=5.0,
    )

    run = _SpawnedWorkerRunner().run(request, 5.0)

    assert run.kind is _WorkerRunKind.RESPONSE
    assert run.response is not None
    envelope = json.loads(run.response)
    result = envelope["result"]
    assert envelope["kind"] == "result"
    assert result["analyzer_id"] == "video_sampled_frame_quality"
    assert result["raw_metrics"]["sampled_frame_count"] == 3
    assert result["raw_metrics"]["exact_duplicate_pair_count"] == 2
    assert result["candidate_findings"][0]["localization"] == {
        "type": "time_interval",
        "start_seconds": 1.5,
        "end_seconds": 5.5,
    }


def test_converter_builds_owner_approved_content_addressed_id(tmp_path: Path) -> None:
    source = tmp_path / "mismatch.jpg"
    _save_image(source, embedded_size=(9, 6))
    result = _image_result(source)

    finding = Stage6FindingService().form_findings((result,))[0]

    identity = {
        "source_analyzer_id": "image_metadata_consistency",
        "source_analyzer_version": "1.0.0",
        "group": "metadata",
        "type": "image_metadata_dimension_mismatch",
        "localization": {"type": "file"},
        "correlation_group": "image_metadata_consistency",
        "duplicate_ordinal": 1,
    }
    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    assert finding.finding_id == "finding_" + hashlib.sha256(canonical).hexdigest()
    assert finding.severity.value == "weak"
    assert finding.source_score is finding.score_impact is None
    assert finding.critical_override_eligible is False


def test_converter_order_ids_and_duplicate_ordinals_are_deterministic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mismatch.jpg"
    _save_image(source, embedded_size=(9, 6))
    original = _image_result(source)
    candidate = cast(dict[str, object], original.candidate_findings[0])
    duplicate_a = {**candidate, "evidence_refs": ["b"]}
    duplicate_b = {**candidate, "evidence_refs": ["a"]}
    duplicated = original.model_copy(
        update={"candidate_findings": [duplicate_a, duplicate_b]}, deep=True
    )
    reversed_duplicates = original.model_copy(
        update={"candidate_findings": [duplicate_b, duplicate_a]}, deep=True
    )

    service = Stage6FindingService()
    findings = service.form_findings((duplicated,))
    reversed_findings = service.form_findings((reversed_duplicates,))

    assert [finding.finding_id for finding in findings] == [
        finding.finding_id for finding in reversed_findings
    ]
    assert len({finding.finding_id for finding in findings}) == 2


def test_finding_id_is_independent_of_worker_order_and_unrelated_findings(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mismatch.jpg"
    _save_image(source, embedded_size=(9, 6))
    image_result = _image_result(source)
    audio_result = AnalyzerResult(
        analyzer_id="audio_pcm_quality",
        analyzer_version="1.0.0",
        media_type=MediaType.AUDIO,
        group="signal_quality",
        status=AnalyzerStatus.COMPLETED,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=0,
        score=None,
        score_name=None,
        summary="Saturation observed.",
        raw_metrics={},
        candidate_findings=[
            {
                "type": "audio_full_scale_saturation",
                "localization": {
                    "type": "time_interval",
                    "start_seconds": 2.0,
                    "end_seconds": 3.0,
                },
                "correlation_group": "audio_signal_quality",
                "evidence_refs": ["audio_fragment_0001"],
            }
        ],
        warnings=[],
        errors=[],
    )
    service = Stage6FindingService()
    image_only_id = service.form_findings((image_result,))[0].finding_id

    forward = service.form_findings((image_result, audio_result))
    reverse = service.form_findings((audio_result, image_result))

    assert [finding.finding_id for finding in forward] == [
        finding.finding_id for finding in reverse
    ]
    assert (
        next(
            finding.finding_id
            for finding in forward
            if finding.type == "image_metadata_dimension_mismatch"
        )
        == image_only_id
    )


def test_converter_rejects_malformed_or_unknown_real_candidates_safely(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mismatch.jpg"
    _save_image(source, embedded_size=(9, 6))
    result = _image_result(source)
    service = Stage6FindingService()

    for candidate in (
        {"type": "unknown_candidate"},
        {
            "type": "image_metadata_dimension_mismatch",
            "localization": {"type": "file"},
            "correlation_group": "wrong",
            "evidence_refs": [],
        },
    ):
        malformed = result.model_copy(update={"candidate_findings": [candidate]}, deep=True)
        with pytest.raises(Stage6FindingFormationError) as captured:
            service.form_findings((malformed,))
        assert captured.value.reason_code == "candidate_validation"
        assert str(captured.value) == "Stage 6 finding formation failed."


@pytest.mark.parametrize(
    "status",
    [
        AnalyzerStatus.ERROR,
        AnalyzerStatus.TIMEOUT,
        AnalyzerStatus.SKIPPED,
        AnalyzerStatus.NOT_APPLICABLE,
    ],
)
def test_converter_ignores_non_completed_results(
    tmp_path: Path,
    status: AnalyzerStatus,
) -> None:
    source = tmp_path / "mismatch.jpg"
    _save_image(source, embedded_size=(9, 6))
    result = _image_result(source)
    errors = []
    applicable = True
    summary = "not completed"
    if status in {AnalyzerStatus.ERROR, AnalyzerStatus.TIMEOUT}:
        errors = [
            {
                "code": "analyzer_error",
                "category": "analyzer",
                "message": "Analyzer did not complete.",
                "retryable": False,
                "analyzer_id": result.analyzer_id,
            }
        ]
    if status is AnalyzerStatus.NOT_APPLICABLE:
        applicable = False
    changed = AnalyzerResult.model_validate(
        {
            **result.model_dump(mode="python"),
            "status": status,
            "applicable": applicable,
            "summary": summary,
            "errors": errors,
        }
    )
    assert Stage6FindingService().form_findings((changed,)) == ()
