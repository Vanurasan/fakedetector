"""Canonical Pydantic models for the FakeDetector domain."""

from datetime import datetime, timedelta
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    field_validator,
    model_validator,
)

from fakedetector.domain.enums import MediaType, SourceChannel


class SourceContext(BaseModel):
    """Context describing how media entered the FakeDetector core."""

    model_config = ConfigDict(extra="forbid")

    channel: SourceChannel
    connector: str | None = None
    external_system: str | None = None
    external_reference: str | None = None


class InputFileDescriptor(BaseModel):
    """Metadata supplied when an input file is received."""

    model_config = ConfigDict(extra="forbid")

    original_name: str
    declared_content_type: str | None
    size_bytes: int
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def validate_received_at_is_utc(cls, value: datetime) -> datetime:
        """Require an aware UTC value without converting another timezone."""
        if value.utcoffset() != timedelta(0):
            raise ValueError("received_at must be a timezone-aware UTC datetime")
        return value

    @field_serializer("received_at", when_used="json")
    def serialize_received_at(self, value: datetime) -> str:
        """Serialize the validated UTC timestamp with the canonical Z suffix."""
        return value.isoformat().replace("+00:00", "Z")


class ImageTechnicalParameters(BaseModel):
    """Technical parameters extracted from a validated image."""

    model_config = ConfigDict(extra="forbid")

    width: int
    height: int
    format: str
    color_mode: str
    frame_count: int | None = None
    has_metadata: bool


class AudioTechnicalParameters(BaseModel):
    """Technical parameters extracted from validated audio."""

    model_config = ConfigDict(extra="forbid")

    duration_seconds: float
    sample_rate_hz: int
    channels: int
    codec: str
    bitrate_bps: int | None = None


class VideoTechnicalParameters(BaseModel):
    """Technical parameters extracted from validated video."""

    model_config = ConfigDict(extra="forbid")

    duration_seconds: float
    container: str
    video_codec: str
    audio_codec: str | None = None
    width: int
    height: int
    fps: float
    bitrate_bps: int | None = None
    has_audio: bool


class ValidatedFileDescriptor(BaseModel):
    """Validated file metadata and media-specific technical parameters."""

    model_config = ConfigDict(extra="forbid")

    original_name: str
    extension: str
    declared_mime_type: str | None
    detected_mime_type: str
    media_type: MediaType
    size_bytes: int
    sha256: str
    signature_match: bool
    safe_read: bool
    technical_parameters: (
        ImageTechnicalParameters | AudioTechnicalParameters | VideoTechnicalParameters
    )

    @model_validator(mode="after")
    def validate_technical_parameters_match_media_type(self) -> Self:
        """Require technical parameters for the descriptor's media type."""
        parameters_match = (
            self.media_type is MediaType.IMAGE
            and isinstance(self.technical_parameters, ImageTechnicalParameters)
            or self.media_type is MediaType.AUDIO
            and isinstance(self.technical_parameters, AudioTechnicalParameters)
            or self.media_type is MediaType.VIDEO
            and isinstance(self.technical_parameters, VideoTechnicalParameters)
        )
        if not parameters_match:
            raise ValueError("technical_parameters must match media_type")
        return self


class ValidationCheck(BaseModel):
    """Outcome of one primary file validation check."""

    model_config = ConfigDict(extra="forbid")

    code: str
    passed: bool
    message: str


class ErrorDetail(BaseModel):
    """Safe structured details describing a domain or processing error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    category: Literal[
        "authentication",
        "authorization",
        "validation",
        "unsupported_media",
        "resource_limit",
        "processing",
        "analyzer",
        "storage",
        "cleanup",
        "configuration",
        "internal",
    ]
    message: str
    retryable: bool
    field: str | None = None
    analyzer_id: str | None = None
    safe_details: dict[str, JsonValue] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Contract result of primary validation before specialized analysis."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    checks: list[ValidationCheck]
    errors: list[ErrorDetail]
    validated_file: ValidatedFileDescriptor | None
