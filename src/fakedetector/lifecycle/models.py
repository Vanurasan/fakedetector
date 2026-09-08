"""Internal Stage 4 task aggregate and safe lifecycle snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.core._cleanup_safety import _CleanupSafetyBarrier
from fakedetector.domain import (
    AnalysisStatus,
    CleanupResult,
    CleanupStatus,
    ErrorDetail,
    MediaType,
    ProcessingStage,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.domain.models import validate_utc_datetime
from fakedetector.intake import AcceptedSource
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry
from fakedetector.preprocessing._models import PreparedMedia


def config_snapshot_fingerprint(config: AppConfig) -> str:
    """Return the full SHA-256 digest of stable canonical validated config JSON."""
    return _ConfigSnapshot.capture(config).snapshot_id


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Canonical internal context created from factual Stage 3 acceptance data."""

    analysis_id: str
    created_at: datetime
    status: AnalysisStatus
    stage: ProcessingStage
    source: SourceContext
    workspace_path: Path
    media_type: MediaType
    config_snapshot_id: str
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.analysis_id:
            raise ValueError("analysis_id must not be empty")
        if not self.config_snapshot_id:
            raise ValueError("config_snapshot_id must not be empty")
        validate_utc_datetime(self.created_at, "created_at")
        if self.started_at is not None:
            validate_utc_datetime(self.started_at, "started_at")
        if self.finished_at is not None:
            validate_utc_datetime(self.finished_at, "finished_at")


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Immutable copy of safe source attribution fields."""

    channel: str
    connector: str | None
    external_system: str | None
    external_reference: str | None


@dataclass(frozen=True, slots=True)
class ErrorSnapshot:
    """Immutable safe lifecycle error without exception text or traceback."""

    code: str
    category: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class CleanupSnapshot:
    """Immutable factual cleanup projection."""

    status: CleanupStatus
    original_file_deleted: bool
    intermediate_files_deleted: bool
    quarantine_used: bool
    finished_at: datetime | None
    errors: tuple[ErrorSnapshot, ...]


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    """Read-only safe task state that never exposes capabilities or internal paths."""

    analysis_id: str
    created_at: datetime
    status: AnalysisStatus
    stage: ProcessingStage
    source: SourceSnapshot
    media_type: MediaType
    config_snapshot_id: str
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    route: MediaType | None
    cleanup: CleanupSnapshot | None
    errors: tuple[ErrorSnapshot, ...]


@dataclass(frozen=True, slots=True)
class TaskExecutionOutcome:
    """Factual narrow result returned by an injected Increment 1 executor."""

    status: AnalysisStatus
    errors: tuple[ErrorDetail, ...] = ()
    _cleanup_safety_barrier: _CleanupSafetyBarrier | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.status not in {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED}:
            raise ValueError("execution outcome must be completed or failed")
        if self.status is AnalysisStatus.COMPLETED and self.errors:
            raise ValueError("completed execution outcome cannot contain errors")
        if self.status is AnalysisStatus.FAILED and not self.errors:
            raise ValueError("failed execution outcome requires a safe error")
        if self.status is AnalysisStatus.COMPLETED and self._cleanup_safety_barrier is not None:
            raise ValueError("completed execution outcome cannot defer cleanup")
        if self._cleanup_safety_barrier is not None and not isinstance(
            self._cleanup_safety_barrier,
            _CleanupSafetyBarrier,
        ):
            raise TypeError("cleanup safety barrier does not implement its private contract")

    @classmethod
    def completed(cls) -> TaskExecutionOutcome:
        return cls(status=AnalysisStatus.COMPLETED)

    @classmethod
    def failed(
        cls,
        error: ErrorDetail,
        *,
        _cleanup_safety_barrier: _CleanupSafetyBarrier | None = None,
    ) -> TaskExecutionOutcome:
        return cls(
            status=AnalysisStatus.FAILED,
            errors=(error,),
            _cleanup_safety_barrier=_cleanup_safety_barrier,
        )


class TerminalSettlementPhase(Enum):
    """Internal-only physical cleanup settlement progress."""

    CLAIMED = auto()
    CLEANUP_IN_PROGRESS = auto()
    FACT_READY = auto()


@dataclass(frozen=True, slots=True)
class CleanupFacts:
    """Timestamp-free factual cleanup outcome retained before publication."""

    status: CleanupStatus
    original_file_deleted: bool
    intermediate_files_deleted: bool
    quarantine_used: bool
    errors: tuple[ErrorDetail, ...]


@dataclass(slots=True)
class TerminalSettlement:
    """Minimal recoverable in-memory state hidden from public task snapshots."""

    phase: TerminalSettlementPhase
    owner_token: object | None
    _cleanup_safety_barrier: _CleanupSafetyBarrier | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    original_file_deleted: bool = False
    artifact_cleanup_completed: bool = False
    intermediate_files_deleted: bool = False
    quarantine_used: bool = False
    quarantine_decided: bool = False
    attempts_completed: int = 0
    facts: CleanupFacts | None = None


@dataclass(frozen=True, slots=True)
class TerminalSettlementSnapshot:
    """Immutable processor-facing view of recoverable settlement state."""

    phase: TerminalSettlementPhase
    original_file_deleted: bool
    artifact_cleanup_completed: bool
    intermediate_files_deleted: bool
    quarantine_used: bool
    quarantine_decided: bool
    attempts_completed: int
    facts: CleanupFacts | None


@dataclass(frozen=True, slots=True)
class _StoredAnalyzerResult:
    """Immutable canonical result bytes and identity for registry publication checks."""

    analyzer_id: str
    media_type: MediaType
    canonical_json: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_json, bytes):
            raise TypeError("stored analyzer result requires immutable bytes")


@dataclass(frozen=True, slots=True)
class Stage5TaskData:
    """Internal prepared state and ordered analyzer results retained by one task."""

    prepared_media: PreparedMedia
    analyzer_results: tuple[_StoredAnalyzerResult, ...] = ()

    def __post_init__(self) -> None:
        results = tuple(self.analyzer_results)
        if any(not isinstance(result, _StoredAnalyzerResult) for result in results):
            raise TypeError("Stage 5 task data requires stored analyzer results")
        object.__setattr__(self, "analyzer_results", results)


@dataclass(frozen=True, slots=True)
class _StoredFinding:
    """Immutable canonical finding bytes and identity for registry checks."""

    finding_id: str
    source_analyzer_id: str
    source_analyzer_version: str
    canonical_json: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not self.finding_id or not self.source_analyzer_id or not self.source_analyzer_version:
            raise ValueError("stored finding identity is incomplete")
        if not isinstance(self.canonical_json, bytes):
            raise TypeError("stored finding requires immutable bytes")


@dataclass(frozen=True, slots=True)
class Stage6TaskData:
    """Internal sibling state retaining canonical normalized findings."""

    findings: tuple[_StoredFinding, ...] = ()

    def __post_init__(self) -> None:
        findings = tuple(self.findings)
        if any(not isinstance(finding, _StoredFinding) for finding in findings):
            raise TypeError("Stage 6 task data requires stored findings")
        finding_ids = [finding.finding_id for finding in findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("Stage 6 task data contains conflicting finding IDs")
        object.__setattr__(self, "findings", findings)


@dataclass(slots=True)
class AnalysisTask:
    """Internal application aggregate retaining the accepted-source capability."""

    context: AnalysisContext
    validation: ValidationResult
    validated_file: ValidatedFileDescriptor
    accepted_source: AcceptedSource
    artifacts: WorkspaceArtifactRegistry
    stage5_data: Stage5TaskData | None = None
    stage6_data: Stage6TaskData | None = None
    queued_at: datetime | None = None
    cleanup_result: CleanupResult | None = None
    errors: list[ErrorDetail] = field(default_factory=list)
    route: MediaType | None = None
    execution_claimed: bool = False
    terminal_settlement: TerminalSettlement | None = None

    def __post_init__(self) -> None:
        if self.context.analysis_id != self.accepted_source.analysis_id:
            raise ValueError("task source identity does not match context")
        if not self.validation.accepted or self.validation.validated_file is None:
            raise ValueError("task requires successful validation")
        if self.validation.validated_file != self.validated_file:
            raise ValueError("task validated descriptor does not match validation")
        if self.context.media_type is not self.validated_file.media_type:
            raise ValueError("task media type does not match validated descriptor")
        if self.stage5_data is not None:
            prepared_media = self.stage5_data.prepared_media
            if prepared_media.analysis_id != self.context.analysis_id:
                raise ValueError("task Stage 5 identity does not match context")
            if prepared_media.media_type is not self.context.media_type:
                raise ValueError("task Stage 5 media type does not match context")
            if not prepared_media.source_file_ref._references(self.accepted_source):
                raise ValueError("task Stage 5 source capability does not match task source")
            if any(
                not self.artifacts._matches_registered_artifact(
                    artifact.artifact_ref,
                    artifact.artifact_id,
                )
                for artifact in prepared_media.artifacts
            ):
                raise ValueError("task Stage 5 artifact capability does not match task registry")
        if self.stage6_data is not None:
            if not isinstance(self.stage6_data, Stage6TaskData):
                raise TypeError("task Stage 6 data must be Stage6TaskData")
            if self.stage5_data is None:
                raise ValueError("task Stage 6 data requires Stage 5 data")

    def snapshot(self) -> TaskSnapshot:
        """Copy the current aggregate into an immutable capability-free projection."""
        source = self.context.source
        return TaskSnapshot(
            analysis_id=self.context.analysis_id,
            created_at=self.context.created_at,
            status=self.context.status,
            stage=self.context.stage,
            source=SourceSnapshot(
                channel=source.channel.value,
                connector=source.connector,
                external_system=source.external_system,
                external_reference=source.external_reference,
            ),
            media_type=self.context.media_type,
            config_snapshot_id=self.context.config_snapshot_id,
            queued_at=self.queued_at,
            started_at=self.context.started_at,
            finished_at=self.context.finished_at,
            route=self.route,
            cleanup=_cleanup_snapshot(self.cleanup_result),
            errors=tuple(_error_snapshot(error) for error in self.errors),
        )


def _error_snapshot(error: ErrorDetail) -> ErrorSnapshot:
    return ErrorSnapshot(
        code=error.code,
        category=error.category,
        message=error.message,
        retryable=error.retryable,
    )


def _cleanup_snapshot(cleanup: CleanupResult | None) -> CleanupSnapshot | None:
    if cleanup is None:
        return None
    return CleanupSnapshot(
        status=cleanup.status,
        original_file_deleted=cleanup.original_file_deleted,
        intermediate_files_deleted=cleanup.intermediate_files_deleted,
        quarantine_used=cleanup.quarantine_used,
        finished_at=cleanup.finished_at,
        errors=tuple(_error_snapshot(error) for error in cleanup.errors),
    )
