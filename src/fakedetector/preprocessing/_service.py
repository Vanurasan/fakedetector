"""Internal image, audio, and video preprocessing with opaque capabilities."""

from __future__ import annotations

import hashlib
import math
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Literal, Protocol, cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError

from fakedetector._generated_artifact_budget import (
    _MAX_GENERATED_ARTIFACTS,
    _GeneratedArtifactBudget,
    _GeneratedArtifactLimitError,
    _GeneratedArtifactWriteError,
)
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import (
    AppConfig,
    AudioPreprocessingConfig,
    ImagePreprocessingConfig,
    VideoPreprocessingConfig,
)
from fakedetector.domain import (
    AudioTechnicalParameters,
    ImageTechnicalParameters,
    MediaType,
    ValidatedFileDescriptor,
    VideoTechnicalParameters,
)
from fakedetector.intake.temporary_input import IntakeSystemError, PreparedSourceRef
from fakedetector.lifecycle.artifacts import (
    ArtifactRegistrationError,
    WorkspaceArtifactRef,
    WorkspaceArtifactRegistry,
)
from fakedetector.preprocessing._errors import PreprocessingError
from fakedetector.preprocessing._media_tools import (
    DecodedAudioWindow,
    _decode_jpeg_coefficients,
    _FFmpegPreprocessingTool,
    _parse_jpeg,
    select_audio_windows,
    select_timing_regions,
    stft_batches,
)
from fakedetector.preprocessing._models import (
    AudioWindowDescriptor,
    ForensicManifest,
    ForensicRepresentation,
    ImageCoordinates,
    IndexRange,
    JpegCoefficientsDescriptor,
    NumericArtifact,
    OriginalImageFacts,
    PreparedArtifact,
    PreparedMedia,
    RepresentationProvenance,
    SpectralWindowDescriptor,
    StreamTimingFacts,
    TimingInterval,
)
from fakedetector.preprocessing._requirements import (
    _FORENSIC_POLICY,
    _MAX_FORENSIC_REPRESENTATIONS,
    ForensicCapability,
    PreprocessingRequirements,
)

_MULTI_FRAME_WARNING = (
    "Normalized image represents only the first displayed frame and does not cover "
    "the source's temporal behavior."
)
_MAX_VIDEO_SAMPLED_FRAMES = 120
_WAV_CONTAINER_OVERHEAD_BYTES = 4_096
_SPECTROGRAM_MAX_BYTES = 640 * 320 * 4 + 320 + 64 * 1024


@dataclass(frozen=True, slots=True)
class PreprocessingRequest:
    """Minimal capabilities and validated facts needed by one preprocessor."""

    analysis_id: str
    validated_file: ValidatedFileDescriptor
    source_file_ref: PreparedSourceRef = field(repr=False)
    artifact_registry: WorkspaceArtifactRegistry = field(repr=False)
    artifact_budget: _GeneratedArtifactBudget = field(repr=False)

    def __post_init__(self) -> None:
        if not self.analysis_id:
            raise ValueError("analysis_id must not be empty")
        if not isinstance(self.validated_file, ValidatedFileDescriptor):
            raise TypeError("validated_file must be a ValidatedFileDescriptor")
        if not isinstance(self.source_file_ref, PreparedSourceRef):
            raise TypeError("source_file_ref must be a PreparedSourceRef")
        if not isinstance(self.artifact_registry, WorkspaceArtifactRegistry):
            raise TypeError("artifact_registry must be a WorkspaceArtifactRegistry")
        if not isinstance(self.artifact_budget, _GeneratedArtifactBudget):
            raise TypeError("artifact_budget must be a generated-artifact budget")
        if self.source_file_ref.analysis_id != self.analysis_id:
            raise ValueError("preprocessing source identity does not match request")
        if self.artifact_budget.media_type is not self.validated_file.media_type:
            raise ValueError("artifact budget media type does not match request")


class Preprocessor(Protocol):
    """Narrow internal contract implemented by each media preprocessor."""

    media_type: MediaType

    def prepare(
        self,
        request: PreprocessingRequest,
        requirements: PreprocessingRequirements,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
    ) -> PreparedMedia:
        """Create registered representations for one validated controlled source."""
        ...


class ImagePreprocessor:
    """Build a first-displayed-frame, orientation-normalized PNG representation."""

    media_type = MediaType.IMAGE

    def __init__(self, config: ImagePreprocessingConfig) -> None:
        self._config = config

    def prepare(
        self,
        request: PreprocessingRequest,
        requirements: PreprocessingRequirements,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
    ) -> PreparedMedia:
        parameters = _parameters(request, ImageTechnicalParameters, self.media_type)
        original = None
        if requirements.forensic:
            _check_remaining(remaining_timeout_seconds)
            original = _original_image_facts(request)
            _check_remaining(remaining_timeout_seconds)
        normalized: Image.Image | None = None
        artifacts: list[PreparedArtifact] = []
        try:
            _ensure_artifact_count(1)
            _check_remaining(remaining_timeout_seconds)
            normalized = _decode_normalized_image(request.source_file_ref)
            _check_remaining(remaining_timeout_seconds)
            normalized_facts = {
                "format": "png",
                "mode": normalized.mode,
                "width": normalized.width,
                "height": normalized.height,
                "scope": "first_frame",
            }
            artifact_ref = _register(
                request.artifact_registry,
                "image_normalized",
                "preprocessing/image/normalized.png",
            )
            _with_artifact_path(
                request.artifact_registry,
                artifact_ref,
                lambda target: _save_png(
                    normalized,
                    target,
                    request.artifact_budget,
                    "image_normalize",
                ),
            )
            _check_remaining(remaining_timeout_seconds)
            artifacts.append(
                PreparedArtifact(
                    artifact_id="image_normalized",
                    artifact_type="normalized_image",
                    artifact_ref=artifact_ref,
                    format="png",
                )
            )
        finally:
            if normalized is not None:
                normalized.close()

        metadata: dict[str, object] = {
            "source": _image_source_metadata(parameters, self._config.extract_metadata),
            "normalized": normalized_facts,
            "frame_scope": "first_frame",
        }
        if original is not None:
            original = OriginalImageFacts.model_validate(
                {
                    **original.model_dump(),
                    "normalized_size": (normalized_facts["width"], normalized_facts["height"]),
                    "orientation_applied": original.coordinates.orientation not in (None, 1),
                }
            )
            representations = [
                ForensicRepresentation(
                    provenance=RepresentationProvenance(
                        producer="fakedetector",
                        producer_version="1",
                        profile="original_image",
                        profile_version="1",
                    ),
                    facts=original,
                )
            ]
            if (
                original.jpeg is not None
                and ForensicCapability.JPEG_COEFFICIENTS in requirements.forensic
            ):
                planes = _prepare_jpeg_planes(
                    request, original, artifacts, remaining_timeout_seconds
                )
                representations.append(
                    ForensicRepresentation(
                        provenance=RepresentationProvenance(
                            producer="pyjpegio",
                            producer_version="0.3.0",
                            profile="jpeg_coefficients",
                            profile_version="1",
                        ),
                        facts=JpegCoefficientsDescriptor(header=original.jpeg, planes=planes),
                    )
                )
            metadata["forensic"] = ForensicManifest(
                source_sha256=request.validated_file.sha256,
                media_type=self.media_type,
                representations=tuple(representations),
            ).to_metadata()
        frame_count = parameters.frame_count or 1
        image_warnings = (_MULTI_FRAME_WARNING,) if frame_count > 1 else ()
        return _prepared_media(request, self.media_type, artifacts, metadata, image_warnings)


class AudioPreprocessor:
    """Create canonical PCM WAV, deterministic fragments, and optional spectrogram."""

    media_type = MediaType.AUDIO

    def __init__(
        self,
        config: AudioPreprocessingConfig,
        *,
        media_tool: _FFmpegPreprocessingTool,
    ) -> None:
        self._config = config
        self._media_tool = media_tool

    def prepare(
        self,
        request: PreprocessingRequest,
        requirements: PreprocessingRequirements,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
    ) -> PreparedMedia:
        parameters = _parameters(request, AudioTechnicalParameters, self.media_type)
        spectrogram_created = self._config.build_spectrogram and requirements.audio_spectrogram
        fragment_count = _audio_fragment_count(
            parameters.duration_seconds,
            self._config.fragment_duration_seconds,
        )
        _ensure_artifact_count(1 + fragment_count + int(spectrogram_created))
        _check_remaining(remaining_timeout_seconds)
        try:
            request.artifact_budget.ensure_feasible(
                _audio_generated_bytes_estimate(
                    duration_seconds=parameters.duration_seconds,
                    sample_rate_hz=parameters.sample_rate_hz,
                    channels=parameters.channels,
                    fragment_seconds=self._config.fragment_duration_seconds,
                    fragment_count=fragment_count,
                    spectrogram=spectrogram_created,
                )
            )
        except _GeneratedArtifactLimitError:
            raise PreprocessingError("resource_limit", "audio_preflight") from None

        normalized_ref = _register(
            request.artifact_registry,
            "audio_normalized",
            "preprocessing/audio/normalized.wav",
        )
        _with_source_and_artifact(
            request,
            normalized_ref,
            lambda source, target: self._media_tool.normalized_audio(
                source,
                target,
                sample_rate_hz=parameters.sample_rate_hz,
                channels=parameters.channels,
                artifact_budget=request.artifact_budget,
                timeout_seconds=_operation_timeout(remaining_timeout_seconds),
            ),
        )
        artifacts = [
            PreparedArtifact(
                artifact_id="audio_normalized",
                artifact_type="normalized_audio",
                artifact_ref=normalized_ref,
                format="wav",
            )
        ]

        for fragment_index in range(fragment_count):
            start = fragment_index * float(self._config.fragment_duration_seconds)
            end = min(
                parameters.duration_seconds,
                (fragment_index + 1) * float(self._config.fragment_duration_seconds),
            )

            def write_fragment(
                source: Path,
                target: Path,
                start_seconds: float = start,
                end_seconds: float = end,
            ) -> None:
                self._media_tool.audio_fragment(
                    source,
                    target,
                    start_seconds=start_seconds,
                    duration_seconds=end_seconds - start_seconds,
                    sample_rate_hz=parameters.sample_rate_hz,
                    channels=parameters.channels,
                    artifact_budget=request.artifact_budget,
                    timeout_seconds=_operation_timeout(remaining_timeout_seconds),
                )

            artifact_id = f"audio_fragment_{fragment_index:04d}"
            fragment_ref = _register(
                request.artifact_registry,
                artifact_id,
                f"preprocessing/audio/fragments/{fragment_index:04d}.wav",
            )
            _with_two_artifacts(
                request.artifact_registry,
                normalized_ref,
                fragment_ref,
                write_fragment,
            )
            artifacts.append(
                PreparedArtifact(
                    artifact_id=artifact_id,
                    artifact_type="audio_fragment",
                    artifact_ref=fragment_ref,
                    format="wav",
                    start_time_seconds=start,
                    end_time_seconds=end,
                )
            )

        if spectrogram_created:
            spectrogram_ref = _register(
                request.artifact_registry,
                "audio_spectrogram",
                "preprocessing/audio/spectrogram.png",
            )
            _with_two_artifacts(
                request.artifact_registry,
                normalized_ref,
                spectrogram_ref,
                lambda source, target: self._media_tool.spectrogram(
                    source,
                    target,
                    artifact_budget=request.artifact_budget,
                    timeout_seconds=_operation_timeout(remaining_timeout_seconds),
                ),
            )
            artifacts.append(
                PreparedArtifact(
                    artifact_id="audio_spectrogram",
                    artifact_type="spectrogram",
                    artifact_ref=spectrogram_ref,
                    format="png",
                )
            )

        metadata: dict[str, object] = {
            "duration_seconds": parameters.duration_seconds,
            "sample_rate_hz": parameters.sample_rate_hz,
            "channels": parameters.channels,
            "normalized_format": "wav",
            "sample_format": "pcm_s16le",
            "fragment_duration_seconds": self._config.fragment_duration_seconds,
            "fragment_count": fragment_count,
            "spectrogram_created": spectrogram_created,
        }
        if self._config.extract_metadata:
            metadata["source_codec"] = parameters.codec
            metadata["source_bitrate_bps"] = parameters.bitrate_bps
        if requirements.forensic:
            metadata["forensic"] = _prepare_av_forensic(
                request,
                requirements,
                self._media_tool,
                artifacts,
                parameters.duration_seconds,
                remaining_timeout_seconds,
            ).to_metadata()
        return _prepared_media(request, self.media_type, artifacts, metadata)


class VideoPreprocessor:
    """Create bounded periodic representative frames and optional lossless audio."""

    media_type = MediaType.VIDEO

    def __init__(
        self,
        config: VideoPreprocessingConfig,
        *,
        media_tool: _FFmpegPreprocessingTool,
    ) -> None:
        self._config = config
        self._media_tool = media_tool

    def prepare(
        self,
        request: PreprocessingRequest,
        requirements: PreprocessingRequirements,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
    ) -> PreparedMedia:
        parameters = _parameters(request, VideoTechnicalParameters, self.media_type)
        timestamps, truncated = _video_timestamps(
            parameters.duration_seconds,
            self._config.keyframe_interval_seconds,
        )
        audio_created = (
            parameters.has_audio
            and self._config.extract_audio_track
            and requirements.video_audio_track
        )
        _ensure_artifact_count(len(timestamps) + int(audio_created))
        _check_remaining(remaining_timeout_seconds)
        artifacts: list[PreparedArtifact] = []
        for frame_index, timestamp in enumerate(timestamps):

            def write_frame(
                source: Path,
                target: Path,
                target_timestamp: float = timestamp,
            ) -> None:
                self._media_tool.sampled_frame(
                    source,
                    target,
                    timestamp_seconds=target_timestamp,
                    artifact_budget=request.artifact_budget,
                    timeout_seconds=_operation_timeout(remaining_timeout_seconds),
                )

            artifact_id = f"video_frame_{frame_index:04d}"
            frame_ref = _register(
                request.artifact_registry,
                artifact_id,
                f"preprocessing/video/frames/{frame_index:04d}.png",
            )
            _with_source_and_artifact(
                request,
                frame_ref,
                write_frame,
            )
            artifacts.append(
                PreparedArtifact(
                    artifact_id=artifact_id,
                    artifact_type="sampled_frame",
                    artifact_ref=frame_ref,
                    format="png",
                    start_time_seconds=timestamp,
                    frame_index=frame_index,
                )
            )

        if audio_created:
            audio_ref = _register(
                request.artifact_registry,
                "video_audio_track",
                "preprocessing/video/audio.flac",
            )
            _with_source_and_artifact(
                request,
                audio_ref,
                lambda source, target: self._media_tool.extracted_audio(
                    source,
                    target,
                    artifact_budget=request.artifact_budget,
                    timeout_seconds=_operation_timeout(remaining_timeout_seconds),
                ),
            )
            artifacts.append(
                PreparedArtifact(
                    artifact_id="video_audio_track",
                    artifact_type="extracted_audio_track",
                    artifact_ref=audio_ref,
                    format="flac",
                )
            )

        metadata: dict[str, object] = {
            "duration_seconds": parameters.duration_seconds,
            "width": parameters.width,
            "height": parameters.height,
            "fps": parameters.fps,
            "has_audio": parameters.has_audio,
            "sampling_scope": "periodic_representative_frames",
            "sampling_interval_seconds": self._config.keyframe_interval_seconds,
            "sampled_frame_count": len(timestamps),
            "target_timestamps_seconds": timestamps,
            "timestamp_semantics": "deterministic_target",
            "audio_track_created": audio_created,
        }
        if self._config.extract_metadata:
            metadata.update(
                {
                    "source_container": parameters.container,
                    "source_video_codec": parameters.video_codec,
                    "source_audio_codec": parameters.audio_codec,
                    "source_bitrate_bps": parameters.bitrate_bps,
                }
            )
        video_warnings = (
            (
                (
                    "Representative frame sampling was capped at the internal resource limit; "
                    "later source timestamps are not represented."
                ),
            )
            if truncated
            else ()
        )
        if requirements.forensic:
            metadata["forensic"] = _prepare_av_forensic(
                request,
                requirements,
                self._media_tool,
                artifacts,
                parameters.duration_seconds,
                remaining_timeout_seconds,
            ).to_metadata()
        return _prepared_media(request, self.media_type, artifacts, metadata, video_warnings)


class PreprocessingDispatcher:
    """Select exactly one concrete preprocessor by validated MediaType."""

    def __init__(
        self,
        config: AppConfig,
        *,
        ffmpeg_executable: str = "ffmpeg",
    ) -> None:
        self._config_snapshot = _ConfigSnapshot.capture(config)
        captured_config = self._config_snapshot.materialize()
        preprocessing_config = captured_config.preprocessing
        media_tool = _FFmpegPreprocessingTool(
            executable=ffmpeg_executable,
            timeout_seconds=float(captured_config.limits.processing_timeout_seconds),
        )
        self._preprocessors: dict[MediaType, Preprocessor] = {
            MediaType.IMAGE: ImagePreprocessor(preprocessing_config.image),
            MediaType.AUDIO: AudioPreprocessor(preprocessing_config.audio, media_tool=media_tool),
            MediaType.VIDEO: VideoPreprocessor(preprocessing_config.video, media_tool=media_tool),
        }

    def _uses_config_snapshot(self, snapshot: _ConfigSnapshot) -> bool:
        return self._config_snapshot == snapshot

    def prepare(
        self,
        request: PreprocessingRequest,
        requirements: PreprocessingRequirements | None = None,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
    ) -> PreparedMedia:
        """Dispatch without extension guessing, analyzer execution, or lifecycle mutation."""
        active_requirements = requirements or PreprocessingRequirements()
        try:
            active_requirements.validate_media(request.validated_file.media_type)
        except ValueError:
            raise PreprocessingError("invariant", "forensic_media_type") from None
        if active_requirements.forensic - {
            ForensicCapability.ORIGINAL_IMAGE,
            ForensicCapability.IMAGE_COORDINATES,
            ForensicCapability.JPEG_STRUCTURE,
            ForensicCapability.JPEG_COEFFICIENTS,
            ForensicCapability.AUDIO_PRECISION,
            ForensicCapability.AUDIO_SAMPLES,
            ForensicCapability.AUDIO_SPECTRAL,
            ForensicCapability.STREAM_TIMING,
            ForensicCapability.TIMING_RECORDS,
        }:
            raise PreprocessingError("invariant", "forensic_producer_unavailable")
        if not request.artifact_budget.matches(
            self._config_snapshot,
            request.validated_file.media_type,
        ):
            raise PreprocessingError("invariant", "artifact_budget_snapshot")
        try:
            preprocessor = self._preprocessors[request.validated_file.media_type]
        except KeyError:
            raise PreprocessingError("invariant", "media_type") from None
        _check_remaining(remaining_timeout_seconds)
        prepared_media = preprocessor.prepare(
            request,
            active_requirements,
            remaining_timeout_seconds=remaining_timeout_seconds,
        )
        _check_remaining(remaining_timeout_seconds)
        return prepared_media


def _parameters[Parameter](
    request: PreprocessingRequest,
    expected_type: type[Parameter],
    expected_media_type: MediaType,
) -> Parameter:
    if request.validated_file.media_type is not expected_media_type:
        raise PreprocessingError("invariant", "media_type")
    parameters = request.validated_file.technical_parameters
    if not isinstance(parameters, expected_type):
        raise PreprocessingError("invariant", "technical_parameters")
    return parameters


def _operation_timeout(
    remaining_timeout_seconds: Callable[[], float] | None,
) -> float | None:
    if remaining_timeout_seconds is None:
        return None
    remaining = remaining_timeout_seconds()
    if (
        not isinstance(remaining, (int, float))
        or isinstance(remaining, bool)
        or not math.isfinite(float(remaining))
        or remaining <= 0
    ):
        raise PreprocessingError("invariant", "execution_budget")
    return float(remaining)


def _check_remaining(remaining_timeout_seconds: Callable[[], float] | None) -> None:
    _operation_timeout(remaining_timeout_seconds)


def _prepare_av_forensic(
    request: PreprocessingRequest,
    requirements: PreprocessingRequirements,
    tool: _FFmpegPreprocessingTool,
    artifacts: list[PreparedArtifact],
    duration: float,
    remaining: Callable[[], float] | None,
) -> ForensicManifest:
    representations: list[ForensicRepresentation] = []
    if requirements.forensic & {
        ForensicCapability.AUDIO_PRECISION,
        ForensicCapability.AUDIO_SAMPLES,
        ForensicCapability.AUDIO_SPECTRAL,
    }:
        representations.extend(
            _prepare_audio_forensic(
                request, requirements, tool, artifacts, duration, remaining
            ).representations
        )
    if ForensicCapability.STREAM_TIMING in requirements.forensic:
        representations.extend(
            _prepare_timing_forensic(
                request,
                requirements,
                tool,
                artifacts,
                remaining,
                existing_representations=len(representations),
            )
        )
    try:
        return ForensicManifest(
            source_sha256=request.validated_file.sha256,
            media_type=request.validated_file.media_type,
            representations=tuple(representations),
        )
    except ValueError:
        raise PreprocessingError("resource_limit", "forensic_manifest_limit") from None


def _prepare_timing_forensic(
    request: PreprocessingRequest,
    requirements: PreprocessingRequirements,
    tool: _FFmpegPreprocessingTool,
    artifacts: list[PreparedArtifact],
    remaining: Callable[[], float] | None,
    *,
    existing_representations: int = 0,
) -> tuple[ForensicRepresentation, ...]:
    provenance = RepresentationProvenance(
        producer="ffprobe_timing",
        producer_version="1",
        profile="bounded_packets_frames",
        profile_version="1",
    )
    records_demand = ForensicCapability.TIMING_RECORDS in requirements.forensic
    representations: list[ForensicRepresentation] = []
    plan: list[tuple[StreamTimingFacts, TimingInterval, int, Literal["packet", "frame"]]] = []
    try:
        with request.source_file_ref.open_for_read() as stream:
            hasher = hashlib.sha256()
            while chunk := stream.read(65536):
                _check_remaining(remaining)
                hasher.update(chunk)
        if hasher.hexdigest() != request.validated_file.sha256:
            raise PreprocessingError("invariant", "forensic_source_identity")
        kinds: tuple[Literal["audio", "video"], ...] = (
            ("video", "audio")
            if request.validated_file.media_type is MediaType.VIDEO
            else ("audio",)
        )
        for kind in kinds[: _FORENSIC_POLICY.timing_streams]:
            facts = request.source_file_ref.with_local_source_path(
                partial(
                    tool.timing_stream,
                    kind=kind,
                    frames=records_demand,
                    timeout_seconds=_operation_timeout(remaining),
                )
            )
            if facts is None:
                continue
            representations.append(ForensicRepresentation(provenance=provenance, facts=facts))
            if records_demand:
                for region, interval in enumerate(select_timing_regions(facts)):
                    plan.append((facts, interval, region, "packet"))
                    if kind == "video":
                        plan.append((facts, interval, region, "frame"))
        if not representations:
            raise PreprocessingError("decode", "timing_unsupported_streams")
        count = sum(
            _FORENSIC_POLICY.timing_packets
            if item[3] == "packet"
            else _FORENSIC_POLICY.timing_frames
            for item in plan
        )
        if (
            count > _FORENSIC_POLICY.timing_records
            or count * 72 > _FORENSIC_POLICY.timing_artifact_bytes
            or existing_representations + len(representations) + len(plan)
            > _MAX_FORENSIC_REPRESENTATIONS
        ):
            raise PreprocessingError("resource_limit", "timing_preflight")
        _FORENSIC_POLICY.check_artifacts(
            request.artifact_budget,
            total_count=len(artifacts) + len(plan),
            additional_bytes=count * 72,
        )
        for facts, interval, region, record_kind in plan:
            descriptor, values = request.source_file_ref.with_local_source_path(
                partial(
                    tool.timing_records,
                    facts=facts,
                    requested=interval,
                    region=region,
                    kind=record_kind,
                    timeout_seconds=_operation_timeout(remaining),
                )
            )
            if descriptor.data is not None:
                _write_numeric(
                    request,
                    artifacts,
                    descriptor.data,
                    (values,),
                    remaining,
                    artifact_type="timing_numeric",
                )
            representations.append(ForensicRepresentation(provenance=provenance, facts=descriptor))
        return tuple(representations)
    except IntakeSystemError:
        raise PreprocessingError("source_read", "timing_source") from None
    except _GeneratedArtifactLimitError:
        raise PreprocessingError("resource_limit", "timing_artifacts") from None
    except _GeneratedArtifactWriteError:
        raise PreprocessingError("artifact_write", "timing_artifacts") from None
    except ValueError:
        raise PreprocessingError("decode", "timing_malformed_artifact") from None


def _prepare_audio_forensic(
    request: PreprocessingRequest,
    requirements: PreprocessingRequirements,
    tool: _FFmpegPreprocessingTool,
    artifacts: list[PreparedArtifact],
    duration: float,
    remaining: Callable[[], float] | None,
) -> ForensicManifest:
    provenance = RepresentationProvenance(
        producer="ffmpeg_audio",
        producer_version="1",
        profile="precision_windows",
        profile_version="1",
    )
    spectral_provenance = RepresentationProvenance(
        producer="numpy_stft", producer_version="1", profile="hann4096_hop1024", profile_version="1"
    )
    representations: list[ForensicRepresentation] = []
    try:
        with request.source_file_ref.open_for_read() as stream:
            hasher = hashlib.sha256()
            while chunk := stream.read(65536):
                _check_remaining(remaining)
                hasher.update(chunk)
        if hasher.hexdigest() != request.validated_file.sha256:
            raise PreprocessingError("invariant", "forensic_source_identity")
        facts = request.source_file_ref.with_local_source_path(
            lambda source: tool.audio_precision(
                source, timeout_seconds=_operation_timeout(remaining)
            )
        )
        windows = select_audio_windows(
            max(1, math.ceil((facts.declared_duration_seconds or duration) * facts.sample_rate)),
            facts.sample_rate,
            facts.channels,
        )
        samples_demand = ForensicCapability.AUDIO_SAMPLES in requirements.forensic
        spectral_demand = ForensicCapability.AUDIO_SPECTRAL in requirements.forensic
        if not samples_demand:
            windows = (IndexRange(start=0, stop=1),)
        # Worst-case float64 samples and magnitude spectra; one shared artifact budget.
        sample_bytes = sum(w.count * facts.channels * 8 for w in windows) if samples_demand else 0
        frame_counts = [max(0, 1 + (w.count - 4096) // 1024) for w in windows]
        spectral_bytes = sum(frame_counts) * facts.channels * 2049 * 8 if spectral_demand else 0
        if (
            spectral_demand
            and sum(frame_counts) * facts.channels > _FORENSIC_POLICY.spectral_frames
        ):
            raise ValueError("aggregate spectral frames exceed policy")
        _FORENSIC_POLICY.check_artifacts(
            request.artifact_budget,
            total_count=len(artifacts)
            + (len(windows) if samples_demand else 0)
            + (sum(count > 0 for count in frame_counts) if spectral_demand else 0),
            additional_bytes=sample_bytes + spectral_bytes,
        )
        origin = 0
        observed_facts = None
        previous_stop = 0
        for ordinal, window in enumerate(windows):

            def decode(source: Path, selected: IndexRange = window) -> DecodedAudioWindow:
                return tool.precision_window(
                    source, facts, selected, timeout_seconds=_operation_timeout(remaining)
                )

            decoded = request.source_file_ref.with_local_source_path(decode)
            if ordinal == 0:
                origin = decoded.first_pts
                observed_facts = decoded.facts
                representations.append(
                    ForensicRepresentation(provenance=provenance, facts=observed_facts)
                )
            elif decoded.facts != observed_facts:
                raise PreprocessingError("decode", "audio_precision_changed_format")
            if not samples_demand:
                break
            start = decoded.first_pts - origin
            if start < previous_stop:
                raise PreprocessingError("decode", "audio_precision_overlapping_coverage")
            previous_stop = start + decoded.values.shape[0]
            descriptor = NumericArtifact(
                artifact_id=f"audio_samples_{ordinal}",
                shape=decoded.values.shape,
                dtype="<i4" if decoded.values.dtype.kind == "i" else "<f8",
            )
            _write_numeric(request, artifacts, descriptor, (decoded.values,), remaining)
            representations.append(
                ForensicRepresentation(
                    provenance=provenance,
                    facts=AudioWindowDescriptor(
                        stream_index=facts.stream_index,
                        samples=IndexRange(start=start, stop=previous_stop),
                        requested_samples=window,
                        first_sample_pts=decoded.first_pts,
                        data=descriptor,
                    ),
                )
            )
            frames = max(0, 1 + (decoded.values.shape[0] - 4096) // 1024)
            if spectral_demand and frames:
                spectral = NumericArtifact(
                    artifact_id=f"audio_spectral_{ordinal}",
                    shape=(frames, facts.channels, 2049),
                    dtype="<f8",
                )
                batches = stft_batches(
                    decoded.values,
                    sample_rate=facts.sample_rate,
                    n_fft=4096,
                    hop=1024,
                    batch_size=16,
                )
                _write_numeric(request, artifacts, spectral, (b.values for b in batches), remaining)
                representations.append(
                    ForensicRepresentation(
                        provenance=spectral_provenance,
                        facts=SpectralWindowDescriptor(
                            samples_artifact_id=descriptor.artifact_id,
                            frames=IndexRange(start=0, stop=frames),
                            n_fft=4096,
                            hop=1024,
                            window="hann",
                            scaling="magnitude",
                            data=spectral,
                        ),
                    )
                )
        return ForensicManifest(
            source_sha256=request.validated_file.sha256,
            media_type=request.validated_file.media_type,
            representations=tuple(representations),
        )
    except IntakeSystemError:
        raise PreprocessingError("source_read", "audio_precision_source") from None
    except _GeneratedArtifactLimitError:
        raise PreprocessingError("resource_limit", "audio_precision_artifacts") from None
    except _GeneratedArtifactWriteError:
        raise PreprocessingError("artifact_write", "audio_precision_artifacts") from None
    except ValueError:
        raise PreprocessingError("resource_limit", "audio_precision_preflight") from None


def _write_numeric(
    request: PreprocessingRequest,
    artifacts: list[PreparedArtifact],
    descriptor: NumericArtifact,
    batches: Iterable[NDArray[np.generic]],
    remaining: Callable[[], float] | None,
    *,
    artifact_type: str = "audio_numeric",
) -> None:
    reference = _register(
        request.artifact_registry, descriptor.artifact_id, f"{descriptor.artifact_id}.raw"
    )

    def write(target: Path) -> None:
        size = 0
        with request.artifact_budget.open_output(target) as output:
            for batch in batches:
                _check_remaining(remaining)
                size += batch.nbytes
                if size > descriptor.nbytes:
                    raise PreprocessingError("invariant", "numeric_extent")
                output.write(batch.tobytes(order="C"))
        if size != descriptor.nbytes:
            raise PreprocessingError("invariant", "numeric_extent")

    _with_artifact_path(request.artifact_registry, reference, write)
    artifacts.append(
        PreparedArtifact(
            artifact_id=descriptor.artifact_id,
            artifact_type=artifact_type,
            artifact_ref=reference,
            format="forensic_raw",
        )
    )


def _original_image_facts(request: PreprocessingRequest) -> OriginalImageFacts:
    """Observe the controlled source without copying arbitrary metadata into facts."""
    try:
        with request.source_file_ref.open_for_read() as stream:
            signature = stream.read(2)
            stream.seek(0)
            structure = None
            if signature == b"\xff\xd8":
                data = stream.read(_FORENSIC_POLICY.jpeg_input_bytes + 1)
                structure = _parse_jpeg(data)
                digest = hashlib.sha256(data).hexdigest()
                del data
            else:
                hasher = hashlib.sha256()
                while chunk := stream.read(65536):
                    hasher.update(chunk)
                digest = hasher.hexdigest()
            if digest != request.validated_file.sha256:
                raise PreprocessingError("invariant", "forensic_source_identity")
            stream.seek(0)
            with Image.open(stream) as image:
                frame = 1 if image.format == "PNG" and getattr(image, "default_image", False) else 0
                image.seek(frame)
                orientation: int | None = 1
                valid_exif: int | None = None
                try:
                    with warnings.catch_warnings(record=True) as observed:
                        warnings.simplefilter("always")
                        value = image.getexif().get(274)
                    if observed or (
                        value is not None and (type(value) is not int or not 1 <= value <= 8)
                    ):
                        orientation = None
                    elif type(value) is int:
                        orientation = valid_exif = value
                except (OSError, ValueError, SyntaxError):
                    orientation = None
                return OriginalImageFacts(
                    format=(image.format or "unknown").lower(),
                    source_mode=image.mode,
                    source_frame=frame,
                    exif_orientation=valid_exif,
                    coordinates=ImageCoordinates(
                        native_width=image.width,
                        native_height=image.height,
                        orientation=orientation,
                    ),
                    jpeg=structure.header if structure else None,
                    quantization_tables=structure.tables if structure else (),
                )
    except IntakeSystemError:
        raise PreprocessingError("source_read", "image_source") from None
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise PreprocessingError("decode", "image_original") from None


def _prepare_jpeg_planes(
    request: PreprocessingRequest,
    original: OriginalImageFacts,
    artifacts: list[PreparedArtifact],
    remaining_timeout_seconds: Callable[[], float] | None,
) -> tuple[NumericArtifact, ...]:
    assert original.jpeg is not None
    allocation = original.jpeg.preflight(request.validated_file.size_bytes)
    planes = tuple(
        NumericArtifact(artifact_id=f"jpeg_component_{i}", shape=(*shape, 8, 8), dtype="<i4")
        for i, shape in enumerate(allocation.block_shapes)
    )
    try:
        _FORENSIC_POLICY.check_artifacts(
            request.artifact_budget,
            total_count=len(artifacts) + len(planes),
            additional_bytes=allocation.output_bytes,
        )
        for plane in planes:
            reference = _register(
                request.artifact_registry, plane.artifact_id, f"{plane.artifact_id}.raw"
            )

            def reserve(target: Path, size: int = plane.nbytes) -> None:
                # The child can overwrite only this existing mmap extent. Charge all
                # physical bytes through the shared budget before native execution.
                with request.artifact_budget.open_output(target) as output:
                    while size:
                        count = min(size, 65536)
                        output.write(bytes(count))
                        size -= count

            _with_artifact_path(request.artifact_registry, reference, reserve)
            artifacts.append(
                PreparedArtifact(
                    artifact_id=plane.artifact_id,
                    artifact_type="jpeg_coefficients",
                    artifact_ref=reference,
                    format="forensic_raw",
                )
            )
        _check_remaining(remaining_timeout_seconds)
        request.source_file_ref.with_local_source_path(
            lambda source: _decode_jpeg_coefficients(
                source,
                request.validated_file.sha256,
                timeout_seconds=_operation_timeout(remaining_timeout_seconds),
            )
        )
        for plane, artifact in zip(planes, artifacts[-len(planes) :], strict=True):

            def validate_extent(target: Path, descriptor: NumericArtifact = plane) -> None:
                descriptor.validate_byte_length(target.stat().st_size)

            _with_artifact_path(
                request.artifact_registry,
                artifact.artifact_ref,
                validate_extent,
            )
    except _GeneratedArtifactLimitError:
        raise PreprocessingError("resource_limit", "jpeg_artifact_preflight") from None
    except (OSError, _GeneratedArtifactWriteError):
        raise PreprocessingError("artifact_write", "jpeg_coefficients") from None
    except ValueError:
        raise PreprocessingError("invariant", "jpeg_artifact_extent") from None
    except IntakeSystemError:
        raise PreprocessingError("source_read", "jpeg_source") from None
    return planes


def _decode_normalized_image(source_ref: PreparedSourceRef) -> Image.Image:
    try:
        with source_ref.open_for_read() as source, warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as image:
                first_frame = (
                    1 if image.format == "PNG" and getattr(image, "default_image", False) else 0
                )
                image.seek(first_frame)
                image.load()
                oriented = ImageOps.exif_transpose(image)
                try:
                    normalized = oriented.convert("RGBA" if _requires_alpha(oriented) else "RGB")
                    normalized.info.clear()
                    return normalized
                finally:
                    if oriented is not image:
                        oriented.close()
    except IntakeSystemError:
        raise PreprocessingError("source_read", "image_source") from None
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        EOFError,
    ):
        raise PreprocessingError("decode", "image_decode") from None


def _requires_alpha(image: Image.Image) -> bool:
    if "A" not in image.getbands() and "transparency" not in image.info:
        return False
    rgba = image.convert("RGBA")
    try:
        alpha = rgba.getchannel("A")
        try:
            minimum, _maximum = cast(tuple[int, int], alpha.getextrema())
            return minimum < 255
        finally:
            alpha.close()
    finally:
        rgba.close()


def _save_png(
    image: Image.Image,
    target: Path,
    artifact_budget: _GeneratedArtifactBudget,
    phase: str,
) -> None:
    try:
        with artifact_budget.open_output(target) as output:
            image.save(output, format="PNG")
    except _GeneratedArtifactLimitError:
        raise PreprocessingError("resource_limit", phase) from None
    except (OSError, _GeneratedArtifactWriteError):
        raise PreprocessingError("artifact_write", phase) from None


def _image_source_metadata(
    parameters: ImageTechnicalParameters,
    include_optional: bool,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "width": parameters.width,
        "height": parameters.height,
        "frame_count": parameters.frame_count or 1,
    }
    if include_optional:
        metadata.update(
            {
                "format": parameters.format,
                "color_mode": parameters.color_mode,
                "has_metadata": parameters.has_metadata,
            }
        )
    return metadata


def _audio_fragment_count(
    duration_seconds: float,
    fragment_seconds: int,
) -> int:
    return max(1, math.ceil(duration_seconds / fragment_seconds))


def _audio_generated_bytes_estimate(
    *,
    duration_seconds: float,
    sample_rate_hz: int,
    channels: int,
    fragment_seconds: int,
    fragment_count: int,
    spectrogram: bool,
) -> int:
    bytes_per_frame = channels * 2
    normalized_frames = math.ceil(duration_seconds * sample_rate_hz)
    complete_fragments = max(0, fragment_count - 1)
    final_duration = max(0.0, duration_seconds - complete_fragments * fragment_seconds)
    fragment_frames = complete_fragments * fragment_seconds * sample_rate_hz + math.ceil(
        final_duration * sample_rate_hz
    )
    wav_count = 1 + fragment_count
    return (
        (normalized_frames + fragment_frames) * bytes_per_frame
        + wav_count * _WAV_CONTAINER_OVERHEAD_BYTES
        + (_SPECTROGRAM_MAX_BYTES if spectrogram else 0)
    )


def _ensure_artifact_count(count: int) -> None:
    if count > _MAX_GENERATED_ARTIFACTS:
        raise PreprocessingError("resource_limit", "artifact_count")


def _video_timestamps(
    duration_seconds: float,
    interval_seconds: int,
) -> tuple[tuple[float, ...], bool]:
    requested_count = max(1, math.ceil(duration_seconds / interval_seconds))
    count = min(requested_count, _MAX_VIDEO_SAMPLED_FRAMES)
    return tuple(frame_index * float(interval_seconds) for frame_index in range(count)), (
        requested_count > count
    )


def _register(
    registry: WorkspaceArtifactRegistry,
    artifact_id: str,
    relative_path: str,
) -> WorkspaceArtifactRef:
    try:
        return registry.register(artifact_id, relative_path)
    except ArtifactRegistrationError:
        raise PreprocessingError("invariant", "artifact_registration") from None


def _with_artifact_path[OperationResult](
    registry: WorkspaceArtifactRegistry,
    artifact_ref: WorkspaceArtifactRef,
    operation: Callable[[Path], OperationResult],
) -> OperationResult:
    try:
        return registry.with_local_artifact_path(artifact_ref, operation)
    except ArtifactRegistrationError:
        raise PreprocessingError("invariant", "artifact_capability") from None


def _with_source_and_artifact[OperationResult](
    request: PreprocessingRequest,
    artifact_ref: WorkspaceArtifactRef,
    operation: Callable[[Path, Path], OperationResult],
) -> OperationResult:
    try:
        return request.source_file_ref.with_local_source_path(
            lambda source: _with_artifact_path(
                request.artifact_registry,
                artifact_ref,
                lambda target: operation(source, target),
            )
        )
    except IntakeSystemError:
        raise PreprocessingError("source_read", "controlled_source") from None


def _with_two_artifacts[OperationResult](
    registry: WorkspaceArtifactRegistry,
    source_ref: WorkspaceArtifactRef,
    target_ref: WorkspaceArtifactRef,
    operation: Callable[[Path, Path], OperationResult],
) -> OperationResult:
    return _with_artifact_path(
        registry,
        source_ref,
        lambda source: _with_artifact_path(
            registry,
            target_ref,
            lambda target: operation(source, target),
        ),
    )


def _prepared_media(
    request: PreprocessingRequest,
    media_type: MediaType,
    artifacts: list[PreparedArtifact],
    metadata: dict[str, object],
    media_warnings: tuple[str, ...] = (),
) -> PreparedMedia:
    return PreparedMedia(
        analysis_id=request.analysis_id,
        media_type=media_type,
        source_file_ref=request.source_file_ref,
        artifacts=tuple(artifacts),
        metadata=metadata,
        warnings=media_warnings,
    )
