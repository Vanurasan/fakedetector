"""Contract tests for validated file descriptor domain models."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import fakedetector.domain as domain
from fakedetector.domain import (
    AudioTechnicalParameters,
    ImageTechnicalParameters,
    MediaType,
    ValidatedFileDescriptor,
    VideoTechnicalParameters,
)
from fakedetector.domain.models import (
    AudioTechnicalParameters as ModelsAudioTechnicalParameters,
)
from fakedetector.domain.models import (
    ImageTechnicalParameters as ModelsImageTechnicalParameters,
)
from fakedetector.domain.models import ValidatedFileDescriptor as ModelsValidatedFileDescriptor
from fakedetector.domain.models import (
    VideoTechnicalParameters as ModelsVideoTechnicalParameters,
)

EXPECTED_DOMAIN_EXPORTS = [
    "AnalysisCompleteness",
    "AnalysisResult",
    "AnalysisResultSummary",
    "AnalysisStatus",
    "AnalyzerResult",
    "AnalyzerStatus",
    "AudioTechnicalParameters",
    "BoundingBoxLocalization",
    "CleanupResult",
    "CleanupStatus",
    "CompletenessStatus",
    "ErrorDetail",
    "FileLocalization",
    "Finding",
    "FindingSeverity",
    "FrameIntervalLocalization",
    "ImageTechnicalParameters",
    "InputFileDescriptor",
    "Localization",
    "MediaType",
    "ProcessingStage",
    "Recommendation",
    "RiskAssessment",
    "RiskLevel",
    "SourceChannel",
    "SourceContext",
    "TimeIntervalLocalization",
    "ValidatedFileDescriptor",
    "ValidationCheck",
    "ValidationResult",
    "VideoTechnicalParameters",
]

IMAGE_PARAMETERS: dict[str, Any] = {
    "width": 1920,
    "height": 1080,
    "format": "JPEG",
    "color_mode": "RGB",
    "has_metadata": True,
}
AUDIO_PARAMETERS: dict[str, Any] = {
    "duration_seconds": 12.5,
    "sample_rate_hz": 48_000,
    "channels": 2,
    "codec": "aac",
}
VIDEO_PARAMETERS: dict[str, Any] = {
    "duration_seconds": 45.25,
    "container": "mp4",
    "video_codec": "h264",
    "width": 1920,
    "height": 1080,
    "fps": 29.97,
    "has_audio": True,
}

TECHNICAL_PARAMETER_CASES: list[tuple[type[BaseModel], dict[str, Any], set[str]]] = [
    (
        ImageTechnicalParameters,
        IMAGE_PARAMETERS,
        {"width", "height", "format", "color_mode", "has_metadata"},
    ),
    (
        AudioTechnicalParameters,
        AUDIO_PARAMETERS,
        {"duration_seconds", "sample_rate_hz", "channels", "codec"},
    ),
    (
        VideoTechnicalParameters,
        VIDEO_PARAMETERS,
        {
            "duration_seconds",
            "container",
            "video_codec",
            "width",
            "height",
            "fps",
            "has_audio",
        },
    ),
]


def descriptor_data(
    media_type: MediaType | str,
    technical_parameters: BaseModel | dict[str, Any],
) -> dict[str, Any]:
    return {
        "original_name": "media.bin",
        "extension": "bin",
        "declared_mime_type": None,
        "detected_mime_type": "application/octet-stream",
        "media_type": media_type,
        "size_bytes": 1234,
        "sha256": "not-validated-by-this-contract",
        "signature_match": True,
        "safe_read": True,
        "technical_parameters": technical_parameters,
    }


@pytest.mark.parametrize(("model_type", "data", "required_fields"), TECHNICAL_PARAMETER_CASES)
def test_technical_parameters_accept_contract_fields(
    model_type: type[BaseModel],
    data: dict[str, Any],
    required_fields: set[str],
) -> None:
    parameters = model_type.model_validate(data)

    assert required_fields <= parameters.model_fields_set


@pytest.mark.parametrize(("model_type", "data", "required_fields"), TECHNICAL_PARAMETER_CASES)
def test_technical_parameters_require_each_main_field(
    model_type: type[BaseModel],
    data: dict[str, Any],
    required_fields: set[str],
) -> None:
    for missing_field in required_fields:
        incomplete_data = data.copy()
        del incomplete_data[missing_field]

        with pytest.raises(ValidationError):
            model_type.model_validate(incomplete_data)


def test_optional_technical_parameters_default_to_none() -> None:
    image = ImageTechnicalParameters.model_validate(IMAGE_PARAMETERS)
    audio = AudioTechnicalParameters.model_validate(AUDIO_PARAMETERS)
    video = VideoTechnicalParameters.model_validate(VIDEO_PARAMETERS)

    assert image.frame_count is None
    assert audio.bitrate_bps is None
    assert video.audio_codec is None
    assert video.bitrate_bps is None


@pytest.mark.parametrize(("model_type", "data", "_required_fields"), TECHNICAL_PARAMETER_CASES)
def test_technical_parameters_reject_unknown_fields(
    model_type: type[BaseModel],
    data: dict[str, Any],
    _required_fields: set[str],
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate({**data, "unknown_parameter": "invented"})


@pytest.mark.parametrize(
    ("media_type", "parameters_type", "parameters_data"),
    [
        (MediaType.IMAGE, ImageTechnicalParameters, IMAGE_PARAMETERS),
        (MediaType.AUDIO, AudioTechnicalParameters, AUDIO_PARAMETERS),
        (MediaType.VIDEO, VideoTechnicalParameters, VIDEO_PARAMETERS),
    ],
)
def test_validated_file_descriptor_accepts_each_media_type(
    media_type: MediaType,
    parameters_type: type[BaseModel],
    parameters_data: dict[str, Any],
) -> None:
    descriptor = ValidatedFileDescriptor.model_validate(
        descriptor_data(media_type, parameters_data)
    )

    assert descriptor.media_type is media_type
    assert isinstance(descriptor.technical_parameters, parameters_type)


def test_validated_file_descriptor_converts_media_type_string_to_enum() -> None:
    descriptor = ValidatedFileDescriptor.model_validate(
        descriptor_data("image", IMAGE_PARAMETERS)
    )

    assert descriptor.media_type is MediaType.IMAGE


def test_validated_file_descriptor_requires_each_field() -> None:
    complete_data = descriptor_data(MediaType.IMAGE, IMAGE_PARAMETERS)

    for missing_field in complete_data:
        incomplete_data = complete_data.copy()
        del incomplete_data[missing_field]

        with pytest.raises(ValidationError):
            ValidatedFileDescriptor.model_validate(incomplete_data)


def test_validated_file_descriptor_accepts_explicit_null_declared_mime_type() -> None:
    descriptor = ValidatedFileDescriptor.model_validate(
        descriptor_data(MediaType.IMAGE, IMAGE_PARAMETERS)
    )

    assert descriptor.declared_mime_type is None
    assert "declared_mime_type" in descriptor.model_fields_set


def test_validated_file_descriptor_requires_nullable_declared_mime_type() -> None:
    data = descriptor_data(MediaType.IMAGE, IMAGE_PARAMETERS)
    del data["declared_mime_type"]

    with pytest.raises(ValidationError):
        ValidatedFileDescriptor.model_validate(data)


def test_validated_file_descriptor_rejects_unknown_media_type() -> None:
    with pytest.raises(ValidationError):
        ValidatedFileDescriptor.model_validate(descriptor_data("document", IMAGE_PARAMETERS))


@pytest.mark.parametrize(
    ("media_type", "technical_parameters"),
    [
        (MediaType.IMAGE, AudioTechnicalParameters(**AUDIO_PARAMETERS)),
        (MediaType.IMAGE, VideoTechnicalParameters(**VIDEO_PARAMETERS)),
        (MediaType.AUDIO, ImageTechnicalParameters(**IMAGE_PARAMETERS)),
        (MediaType.AUDIO, VideoTechnicalParameters(**VIDEO_PARAMETERS)),
        (MediaType.VIDEO, ImageTechnicalParameters(**IMAGE_PARAMETERS)),
        (MediaType.VIDEO, AudioTechnicalParameters(**AUDIO_PARAMETERS)),
    ],
)
def test_validated_file_descriptor_rejects_media_parameter_mismatch(
    media_type: MediaType,
    technical_parameters: BaseModel,
) -> None:
    with pytest.raises(ValidationError):
        ValidatedFileDescriptor.model_validate(
            descriptor_data(media_type, technical_parameters)
        )


def test_validated_file_descriptor_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ValidatedFileDescriptor.model_validate(
            {**descriptor_data(MediaType.IMAGE, IMAGE_PARAMETERS), "system_path": "runtime/input"}
        )


def test_optional_parameters_remain_none_without_invented_values() -> None:
    descriptors = [
        ValidatedFileDescriptor.model_validate(
            descriptor_data(MediaType.IMAGE, IMAGE_PARAMETERS)
        ),
        ValidatedFileDescriptor.model_validate(
            descriptor_data(MediaType.AUDIO, AUDIO_PARAMETERS)
        ),
        ValidatedFileDescriptor.model_validate(
            descriptor_data(MediaType.VIDEO, VIDEO_PARAMETERS)
        ),
    ]

    dumped_parameters = [
        descriptor.model_dump(mode="json")["technical_parameters"]
        for descriptor in descriptors
    ]
    assert dumped_parameters[0]["frame_count"] is None
    assert dumped_parameters[1]["bitrate_bps"] is None
    assert dumped_parameters[2]["audio_codec"] is None
    assert dumped_parameters[2]["bitrate_bps"] is None


@pytest.mark.parametrize(
    ("media_type", "parameters_data"),
    [
        (MediaType.IMAGE, IMAGE_PARAMETERS),
        (MediaType.AUDIO, AUDIO_PARAMETERS),
        (MediaType.VIDEO, VIDEO_PARAMETERS),
    ],
)
def test_validated_file_descriptor_json_dump_and_round_trip(
    media_type: MediaType,
    parameters_data: dict[str, Any],
) -> None:
    descriptor = ValidatedFileDescriptor.model_validate(
        descriptor_data(media_type, parameters_data)
    )

    dumped = descriptor.model_dump(mode="json")
    restored = ValidatedFileDescriptor.model_validate_json(descriptor.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == descriptor
    assert restored.media_type is media_type


def test_new_models_are_available_by_direct_domain_import() -> None:
    assert AudioTechnicalParameters is ModelsAudioTechnicalParameters
    assert ImageTechnicalParameters is ModelsImageTechnicalParameters
    assert ValidatedFileDescriptor is ModelsValidatedFileDescriptor
    assert VideoTechnicalParameters is ModelsVideoTechnicalParameters
    assert domain.AudioTechnicalParameters is ModelsAudioTechnicalParameters
    assert domain.ImageTechnicalParameters is ModelsImageTechnicalParameters
    assert domain.ValidatedFileDescriptor is ModelsValidatedFileDescriptor
    assert domain.VideoTechnicalParameters is ModelsVideoTechnicalParameters


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
