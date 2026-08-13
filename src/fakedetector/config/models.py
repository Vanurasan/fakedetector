"""Pydantic models for application configuration.

Schema is defined in CONTRACTS.md, section 16.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LoggingLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
_IMAGE_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"]
_AUDIO_EXTENSIONS = ["wav", "mp3", "flac", "m4a"]
_AUDIO_MIME_TYPES = ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
_VIDEO_EXTENSIONS = ["mp4", "mov", "avi", "mkv"]
_VIDEO_MIME_TYPES = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]


class ServerConfig(BaseModel):
    """Server network settings."""

    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    request_timeout_seconds: int = Field(default=600, ge=1)
    application_version: str = "0.1.0"


class WebUIConfig(BaseModel):
    """WebUI access channel settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    require_authentication: bool = True


class APIConfig(BaseModel):
    """API access channel settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    require_token: bool = True
    token_env_var: str = Field(
        default="MEDIA_ANALYZER_API_TOKEN",
        min_length=1,
        pattern=r"^[A-Z_][A-Z0-9_]*$",
        description="Name of the environment variable containing the API token",
    )


class AccessChannelsConfig(BaseModel):
    """Access channel configuration."""

    model_config = ConfigDict(extra="forbid")

    webui: WebUIConfig = Field(default_factory=WebUIConfig)
    api: APIConfig = Field(default_factory=APIConfig)


class MediaSizeLimits(BaseModel):
    """Per-media file size limits in megabytes."""

    model_config = ConfigDict(extra="forbid")

    image: int = Field(default=20, ge=1)
    audio: int = Field(default=50, ge=1)
    video: int = Field(default=200, ge=1)


class ParallelLimits(BaseModel):
    """Per-media parallel task limits."""

    model_config = ConfigDict(extra="forbid")

    image: int = Field(default=4, ge=1)
    audio: int = Field(default=2, ge=1)
    video: int = Field(default=1, ge=1)


class LimitsConfig(BaseModel):
    """Resource limits configuration."""

    model_config = ConfigDict(extra="forbid")

    max_file_size_mb: MediaSizeLimits = Field(default_factory=MediaSizeLimits)
    max_parallel_tasks: ParallelLimits = Field(default_factory=ParallelLimits)
    processing_timeout_seconds: int = Field(default=600, ge=1)


class FormatGroup(BaseModel):
    """Allowed extensions and MIME types for a media group."""

    model_config = ConfigDict(extra="forbid")

    extensions: list[str] = Field(default_factory=list)
    mime_types: list[str] = Field(default_factory=list)


class AllowedFormatsConfig(BaseModel):
    """Allowed formats per media type."""

    model_config = ConfigDict(extra="forbid")

    image: FormatGroup = Field(
        default_factory=lambda: FormatGroup(
            extensions=_IMAGE_EXTENSIONS.copy(),
            mime_types=_IMAGE_MIME_TYPES.copy(),
        )
    )
    audio: FormatGroup = Field(
        default_factory=lambda: FormatGroup(
            extensions=_AUDIO_EXTENSIONS.copy(),
            mime_types=_AUDIO_MIME_TYPES.copy(),
        )
    )
    video: FormatGroup = Field(
        default_factory=lambda: FormatGroup(
            extensions=_VIDEO_EXTENSIONS.copy(),
            mime_types=_VIDEO_MIME_TYPES.copy(),
        )
    )

    @model_validator(mode="after")
    def require_canonical_mvp_matrix(self) -> AllowedFormatsConfig:
        """Reject configuration that diverges from the fixed MVP format matrix."""
        expected = (
            (self.image, _IMAGE_EXTENSIONS, _IMAGE_MIME_TYPES),
            (self.audio, _AUDIO_EXTENSIONS, _AUDIO_MIME_TYPES),
            (self.video, _VIDEO_EXTENSIONS, _VIDEO_MIME_TYPES),
        )
        if any(
            len(group.extensions) != len(extensions)
            or set(group.extensions) != set(extensions)
            or len(group.mime_types) != len(mime_types)
            or set(group.mime_types) != set(mime_types)
            for group, extensions, mime_types in expected
        ):
            raise ValueError("allowed_formats must match the canonical MVP matrix")
        return self


class ValidationConfig(BaseModel):
    """File validation settings."""

    model_config = ConfigDict(extra="forbid")

    check_extension: bool = True
    check_mime_type: bool = True
    check_file_signature: bool = True
    reject_if_type_mismatch: bool = True
    calculate_sha256: bool = True
    safe_decode: bool = True

    @model_validator(mode="after")
    def require_primary_validation_checks(self) -> ValidationConfig:
        """Keep every mandatory Stage 3 primary-validation check enabled."""
        if not all(
            (
                self.check_extension,
                self.check_mime_type,
                self.check_file_signature,
                self.reject_if_type_mismatch,
                self.calculate_sha256,
                self.safe_decode,
            )
        ):
            raise ValueError("all primary validation checks must be enabled")
        return self


class TemporaryStorageConfig(BaseModel):
    """Temporary storage settings."""

    model_config = ConfigDict(extra="forbid")

    root_path: str = "runtime/temp"
    ttl_minutes: int = Field(default=60, ge=1)
    cleanup_retries: int = Field(default=3, ge=0)
    quarantine_enabled: bool = True
    quarantine_ttl_hours: int = Field(default=24, ge=1)


class ImagePreprocessingConfig(BaseModel):
    """Image preprocessing settings."""

    model_config = ConfigDict(extra="forbid")

    extract_metadata: bool = True
    normalize_for_analysis: bool = True


class AudioPreprocessingConfig(BaseModel):
    """Audio preprocessing settings."""

    model_config = ConfigDict(extra="forbid")

    extract_metadata: bool = True
    fragment_duration_seconds: int = Field(default=10, ge=1)
    build_spectrogram: bool = True


class VideoPreprocessingConfig(BaseModel):
    """Video preprocessing settings."""

    model_config = ConfigDict(extra="forbid")

    extract_metadata: bool = True
    keyframe_interval_seconds: int = Field(default=2, ge=1)
    extract_audio_track: bool = True


class PreprocessingConfig(BaseModel):
    """Preprocessing configuration per media type."""

    model_config = ConfigDict(extra="forbid")

    image: ImagePreprocessingConfig = Field(default_factory=ImagePreprocessingConfig)
    audio: AudioPreprocessingConfig = Field(default_factory=AudioPreprocessingConfig)
    video: VideoPreprocessingConfig = Field(default_factory=VideoPreprocessingConfig)


class AnalyzerDefaults(BaseModel):
    """Default analyzer settings."""

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(default=120, ge=1)
    continue_on_error: bool = True


class AnalyzerMediaConfig(BaseModel):
    """Per-media analyzer enable list."""

    model_config = ConfigDict(extra="forbid")

    enabled: list[str] = Field(default_factory=list)


class AnalyzersConfig(BaseModel):
    """Analyzers configuration."""

    model_config = ConfigDict(extra="forbid")

    defaults: AnalyzerDefaults = Field(default_factory=AnalyzerDefaults)
    image: AnalyzerMediaConfig = Field(default_factory=AnalyzerMediaConfig)
    audio: AnalyzerMediaConfig = Field(default_factory=AnalyzerMediaConfig)
    video: AnalyzerMediaConfig = Field(default_factory=AnalyzerMediaConfig)
    settings: dict[str, object] = Field(default_factory=dict)


class RiskThresholds(BaseModel):
    """Score thresholds for risk levels."""

    model_config = ConfigDict(extra="forbid")

    low_max: int = Field(default=29, ge=0)
    medium_max: int = Field(default=60, ge=0)


class SeverityScores(BaseModel):
    """Score contributions per finding severity."""

    model_config = ConfigDict(extra="forbid")

    weak: int = Field(default=5, ge=0)
    significant: int = Field(default=25, ge=0)


class CriticalOverrideConfig(BaseModel):
    """Critical override policy."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    allowed_finding_types: list[str] = Field(default_factory=list)


class CompletenessConfig(BaseModel):
    """Completeness assessment settings."""

    model_config = ConfigDict(extra="forbid")

    minimum_for_assessment: float = Field(default=0.5, ge=0.0, le=1.0)


class RiskAssessmentConfig(BaseModel):
    """Risk assessment configuration."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = "score_model_v1"
    model_version: str = "0.1.0"
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    severity_scores: SeverityScores = Field(default_factory=SeverityScores)
    critical_override: CriticalOverrideConfig = Field(default_factory=CriticalOverrideConfig)
    completeness: CompletenessConfig = Field(default_factory=CompletenessConfig)


class ResultConfig(BaseModel):
    """Result storage configuration."""

    model_config = ConfigDict(extra="forbid")

    directory: str = "runtime/results"
    atomic_write: bool = True
    include_raw_metrics: bool = False
    store_original_name: bool = True


class ErrorHandlingConfig(BaseModel):
    """Error handling policy."""

    model_config = ConfigDict(extra="forbid")

    continue_if_analyzer_fails: bool = True
    mark_partial_on_analyzer_failure: bool = True
    hide_internal_error_details: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = ConfigDict(extra="forbid")

    level: LoggingLevel = "INFO"
    jsonl_path: str = "runtime/logs/application.jsonl"
    rotation_max_bytes: int = Field(default=10_485_760, ge=1)
    rotation_backup_count: int = Field(default=5, ge=0)

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, value: object) -> object:
        """Normalize supported textual levels before Literal validation."""
        if isinstance(value, str):
            return value.upper()
        return value


class ExternalSystemsConfig(BaseModel):
    """External systems integration configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    server: ServerConfig
    access_channels: AccessChannelsConfig
    limits: LimitsConfig
    allowed_formats: AllowedFormatsConfig
    validation: ValidationConfig
    temporary_storage: TemporaryStorageConfig
    preprocessing: PreprocessingConfig
    analyzers: AnalyzersConfig
    risk_assessment: RiskAssessmentConfig
    result: ResultConfig
    error_handling: ErrorHandlingConfig
    logging: LoggingConfig
    external_systems: ExternalSystemsConfig
