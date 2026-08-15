"""Internal Stage 4 task aggregate and safe lifecycle snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from fakedetector.config.models import AppConfig
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
from fakedetector.intake import AcceptedSource
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry


def config_snapshot_fingerprint(config: AppConfig) -> str:
    """Return the full SHA-256 digest of stable canonical validated config JSON."""
    canonical_json = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _require_utc(value: datetime, field_name: str) -> None:
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


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
        _require_utc(self.created_at, "created_at")
        if self.started_at is not None:
            _require_utc(self.started_at, "started_at")
        if self.finished_at is not None:
            _require_utc(self.finished_at, "finished_at")


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

    def __post_init__(self) -> None:
        if self.status not in {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED}:
            raise ValueError("execution outcome must be completed or failed")
        if self.status is AnalysisStatus.COMPLETED and self.errors:
            raise ValueError("completed execution outcome cannot contain errors")
        if self.status is AnalysisStatus.FAILED and not self.errors:
            raise ValueError("failed execution outcome requires a safe error")

    @classmethod
    def completed(cls) -> TaskExecutionOutcome:
        return cls(status=AnalysisStatus.COMPLETED)

    @classmethod
    def failed(cls, error: ErrorDetail) -> TaskExecutionOutcome:
        return cls(status=AnalysisStatus.FAILED, errors=(error,))


@dataclass(slots=True)
class AnalysisTask:
    """Internal application aggregate retaining the accepted-source capability."""

    context: AnalysisContext
    validation: ValidationResult
    validated_file: ValidatedFileDescriptor
    accepted_source: AcceptedSource
    artifacts: WorkspaceArtifactRegistry
    queued_at: datetime | None = None
    cleanup_result: CleanupResult | None = None
    errors: list[ErrorDetail] = field(default_factory=list)
    route: MediaType | None = None
    execution_claimed: bool = False

    def __post_init__(self) -> None:
        if self.context.analysis_id != self.accepted_source.analysis_id:
            raise ValueError("task source identity does not match context")
        if not self.validation.accepted or self.validation.validated_file is None:
            raise ValueError("task requires successful validation")
        if self.validation.validated_file != self.validated_file:
            raise ValueError("task validated descriptor does not match validation")
        if self.context.media_type is not self.validated_file.media_type:
            raise ValueError("task media type does not match validated descriptor")

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
