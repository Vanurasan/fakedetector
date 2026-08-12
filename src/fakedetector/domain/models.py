"""Canonical Pydantic models for the FakeDetector domain."""

from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    field_validator,
    model_validator,
)

from fakedetector.domain.enums import (
    AnalysisStatus,
    AnalyzerStatus,
    CleanupStatus,
    CompletenessStatus,
    FindingSeverity,
    MediaType,
    ProcessingStage,
    RiskLevel,
    SourceChannel,
)


def _validate_utc_datetime(value: datetime | None, field_group: str) -> datetime | None:
    """Require an aware UTC value without silently converting another timezone."""
    if value is not None and value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_group} must be timezone-aware UTC")
    return value


def _serialize_utc_datetime(value: datetime | None) -> str | None:
    """Serialize a validated UTC timestamp with the canonical Z suffix."""
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


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
        validated = _validate_utc_datetime(value, "received_at")
        assert validated is not None
        return validated

    @field_serializer("received_at", when_used="json")
    def serialize_received_at(self, value: datetime) -> str:
        """Serialize the validated UTC timestamp with the canonical Z suffix."""
        serialized = _serialize_utc_datetime(value)
        assert serialized is not None
        return serialized


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


class AnalyzerResult(BaseModel):
    """Structured result returned by one analyzer execution."""

    model_config = ConfigDict(extra="forbid")

    analyzer_id: str
    analyzer_version: str
    media_type: MediaType
    group: str
    status: AnalyzerStatus
    applicable: bool
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None = Field(ge=0)
    score: float | None
    score_name: str | None
    summary: str
    raw_metrics: dict[str, JsonValue]
    candidate_findings: list[JsonValue]
    warnings: list[str]
    errors: list[ErrorDetail]

    @field_validator("started_at", "finished_at")
    @classmethod
    def validate_datetime_is_utc(cls, value: datetime | None) -> datetime | None:
        """Require aware UTC datetimes without converting another timezone."""
        return _validate_utc_datetime(value, "analyzer datetimes")

    @field_serializer("started_at", "finished_at", when_used="json")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        """Serialize validated UTC timestamps with the canonical Z suffix."""
        return _serialize_utc_datetime(value)

    @model_validator(mode="after")
    def validate_status_and_score(self) -> Self:
        """Enforce only the cross-field invariants fixed by the contract."""
        if self.score is not None and self.score_name is None:
            raise ValueError("score_name is required when score is provided")
        if self.status is AnalyzerStatus.NOT_APPLICABLE and self.applicable:
            raise ValueError("not_applicable status requires applicable=false")
        if self.status in {AnalyzerStatus.ERROR, AnalyzerStatus.TIMEOUT} and not self.errors:
            raise ValueError("error and timeout statuses require at least one error")
        if self.status is AnalyzerStatus.SKIPPED and not (
            self.summary.strip() or any(warning.strip() for warning in self.warnings)
        ):
            raise ValueError("skipped status requires a safe reason")
        return self


class FileLocalization(BaseModel):
    """Localization covering the complete media file."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["file"]


class BoundingBoxLocalization(BaseModel):
    """Normalized rectangular localization within an image or frame."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bounding_box"]
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)
    coordinate_space: Literal["normalized"]


class TimeIntervalLocalization(BaseModel):
    """Localization expressed as an inclusive time interval in seconds."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["time_interval"]
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_interval_order(self) -> Self:
        """Require the interval start not to follow its end."""
        if self.start_seconds > self.end_seconds:
            raise ValueError("start_seconds must be less than or equal to end_seconds")
        return self


class FrameIntervalLocalization(BaseModel):
    """Localization expressed as an inclusive frame interval."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["frame_interval"]
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_interval_order(self) -> Self:
        """Require the interval start not to follow its end."""
        if self.start_frame > self.end_frame:
            raise ValueError("start_frame must be less than or equal to end_frame")
        return self


Localization = Annotated[
    FileLocalization
    | BoundingBoxLocalization
    | TimeIntervalLocalization
    | FrameIntervalLocalization,
    Field(discriminator="type"),
]


class Finding(BaseModel):
    """Normalized finding formed from an analyzer result."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    group: str
    type: str
    severity: FindingSeverity
    source_analyzer_id: str
    source_analyzer_version: str
    description: str
    localization: Localization | None
    source_score: float | None
    score_impact: float | None
    critical_override_eligible: bool
    correlation_group: str | None
    evidence_refs: list[str]


class AnalysisCompleteness(BaseModel):
    """Declared coverage and status of an analysis execution."""

    model_config = ConfigDict(extra="forbid")

    status: CompletenessStatus
    planned_analyzers: int = Field(ge=0)
    applicable_analyzers: int = Field(ge=0)
    completed_analyzers: int = Field(ge=0)
    failed_analyzers: int = Field(ge=0)
    timed_out_analyzers: int = Field(ge=0)
    skipped_analyzers: int = Field(ge=0)
    not_applicable_analyzers: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    missing_capabilities: list[str]
    explanation: str


class RiskAssessment(BaseModel):
    """Declared risk assessment produced by a separately configured algorithm."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    model_version: str
    score: float | None
    score_based_level: RiskLevel | None
    critical_override_applied: bool
    critical_finding_ids: list[str]
    final_level: RiskLevel | None
    probability: float | None
    probability_method: str | None
    summary: str
    explanation: str
    limitations: list[str]

    @model_validator(mode="after")
    def validate_declared_assessment(self) -> Self:
        """Enforce only fixed evidence requirements without calculating risk."""
        if self.probability is not None and not (
            self.probability_method is not None and self.probability_method.strip()
        ):
            raise ValueError("probability requires a non-empty probability_method")
        if self.critical_override_applied and not self.critical_finding_ids:
            raise ValueError("critical override requires at least one finding ID")
        return self


_RecommendationAction = Literal[
    "no_additional_action",
    "manual_review",
    "verify_source",
    "verify_source_via_independent_channel",
    "request_better_quality_source",
    "retry_analysis",
    "escalate_to_security",
    "send_to_incident_response",
]


class Recommendation(BaseModel):
    """Canonical non-automated action recommendation for an analysis result."""

    model_config = ConfigDict(extra="forbid")

    primary_action: _RecommendationAction
    additional_actions: list[_RecommendationAction]
    text: str
    requires_manual_review: bool


class CleanupResult(BaseModel):
    """Recorded outcome of temporary media cleanup."""

    model_config = ConfigDict(extra="forbid")

    status: CleanupStatus
    original_file_deleted: bool
    intermediate_files_deleted: bool
    quarantine_used: bool
    finished_at: datetime | None
    errors: list[ErrorDetail]

    @field_validator("finished_at")
    @classmethod
    def validate_finished_at_is_utc(cls, value: datetime | None) -> datetime | None:
        """Require UTC when cleanup has a finish timestamp."""
        return _validate_utc_datetime(value, "cleanup finished_at")

    @field_serializer("finished_at", when_used="json")
    def serialize_finished_at(self, value: datetime | None) -> str | None:
        """Serialize cleanup completion time with the canonical Z suffix."""
        return _serialize_utc_datetime(value)


class AnalysisProcessing(BaseModel):
    """Timing and version context embedded in an analysis result."""

    model_config = ConfigDict(extra="forbid")

    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None = Field(ge=0)
    config_snapshot_id: str
    application_version: str

    @field_validator("queued_at", "started_at", "finished_at")
    @classmethod
    def validate_datetime_is_utc(cls, value: datetime | None) -> datetime | None:
        """Require UTC for every processing timestamp that is present."""
        return _validate_utc_datetime(value, "processing datetimes")

    @field_serializer("queued_at", "started_at", "finished_at", when_used="json")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        """Serialize processing timestamps with the canonical Z suffix."""
        return _serialize_utc_datetime(value)


class AnalysisResult(BaseModel):
    """Versioned top-level result of the FakeDetector analysis flow."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    analysis_id: str
    created_at: datetime
    updated_at: datetime
    status: AnalysisStatus
    stage: ProcessingStage
    source: SourceContext
    file: InputFileDescriptor | ValidatedFileDescriptor
    processing: AnalysisProcessing
    analyzers: list[AnalyzerResult]
    findings: list[Finding]
    completeness: AnalysisCompleteness
    risk_assessment: RiskAssessment
    recommendation: Recommendation
    cleanup: CleanupResult
    warnings: list[str]
    errors: list[ErrorDetail]

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_datetime_is_utc(cls, value: datetime) -> datetime:
        """Require UTC for top-level result timestamps."""
        validated = _validate_utc_datetime(value, "analysis result datetimes")
        assert validated is not None
        return validated

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize result timestamps with the canonical Z suffix."""
        serialized = _serialize_utc_datetime(value)
        assert serialized is not None
        return serialized

    @model_validator(mode="after")
    def validate_terminal_result(self) -> Self:
        """Enforce fixed structural invariants for terminal result statuses."""
        if self.status is AnalysisStatus.REJECTED:
            if self.analyzers:
                raise ValueError("rejected result cannot contain analyzer results")
            if self.findings:
                raise ValueError("rejected result cannot contain findings")
            if self.risk_assessment.final_level is not None:
                raise ValueError("rejected result cannot contain a final risk level")
            if self.completeness.status is not CompletenessStatus.NOT_ASSESSED:
                raise ValueError("rejected result requires completeness=not_assessed")
            if not self.errors:
                raise ValueError("rejected result requires at least one error")
        if self.status is AnalysisStatus.FAILED:
            if self.risk_assessment.final_level is not None:
                raise ValueError("failed result cannot contain a final risk level")
            if not self.errors:
                raise ValueError("failed result requires at least one error")
        if (
            self.status is AnalysisStatus.PARTIAL
            and self.completeness.status is not CompletenessStatus.PARTIAL
        ):
            raise ValueError("partial result requires completeness=partial")
        if (
            self.completeness.status is CompletenessStatus.INSUFFICIENT
            and self.risk_assessment.final_level is not None
        ):
            raise ValueError("insufficient completeness cannot contain a final risk level")
        return self
