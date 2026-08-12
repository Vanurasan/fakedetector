"""Public domain contracts for FakeDetector."""

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
from fakedetector.domain.models import (
    AudioTechnicalParameters,
    ErrorDetail,
    ImageTechnicalParameters,
    InputFileDescriptor,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationCheck,
    ValidationResult,
    VideoTechnicalParameters,
)

__all__ = [
    "AnalysisStatus",
    "AnalyzerStatus",
    "AudioTechnicalParameters",
    "CleanupStatus",
    "CompletenessStatus",
    "ErrorDetail",
    "FindingSeverity",
    "ImageTechnicalParameters",
    "InputFileDescriptor",
    "MediaType",
    "ProcessingStage",
    "RiskLevel",
    "SourceChannel",
    "SourceContext",
    "ValidatedFileDescriptor",
    "ValidationCheck",
    "ValidationResult",
    "VideoTechnicalParameters",
]
