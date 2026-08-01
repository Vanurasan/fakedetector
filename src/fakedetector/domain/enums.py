"""Canonical enumerations for the FakeDetector domain."""

from enum import StrEnum


class MediaType(StrEnum):
    """Supported media types."""

    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class SourceChannel(StrEnum):
    """Channels through which media enters the core."""

    WEBUI = "webui"
    API = "api"


class AnalysisStatus(StrEnum):
    """Analysis task statuses."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    REJECTED = "rejected"
    FAILED = "failed"


class ProcessingStage(StrEnum):
    """Diagnostic stages of analysis processing."""

    REGISTERED = "registered"
    VALIDATION = "validation"
    ROUTING = "routing"
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    ANALYSIS = "analysis"
    FINDING_FORMATION = "finding_formation"
    RISK_ASSESSMENT = "risk_assessment"
    RESULT_FORMATION = "result_formation"
    CLEANUP = "cleanup"
    PERSISTENCE = "persistence"
    FINISHED = "finished"


class AnalyzerStatus(StrEnum):
    """Analyzer execution statuses."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"
    TIMEOUT = "timeout"


class FindingSeverity(StrEnum):
    """Severity levels for normalized findings."""

    WEAK = "weak"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"


class RiskLevel(StrEnum):
    """Final risk levels when an assessment is available."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CompletenessStatus(StrEnum):
    """Analysis completeness statuses."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    NOT_ASSESSED = "not_assessed"


class CleanupStatus(StrEnum):
    """Temporary data cleanup statuses."""

    NOT_STARTED = "not_started"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
