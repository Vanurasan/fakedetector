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
from fakedetector.domain.models import InputFileDescriptor, SourceContext

__all__ = [
    "AnalysisStatus",
    "AnalyzerStatus",
    "CleanupStatus",
    "CompletenessStatus",
    "FindingSeverity",
    "InputFileDescriptor",
    "MediaType",
    "ProcessingStage",
    "RiskLevel",
    "SourceChannel",
    "SourceContext",
]
