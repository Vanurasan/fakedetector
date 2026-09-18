"""Deterministic post-handoff cleanup recovery for controlled local workspaces."""

from __future__ import annotations

import logging
import os
import re
import shutil
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from fakedetector._filesystem import (
    ensure_private_directory,
    require_direct_child_directory,
    require_missing_path,
    require_safe_directory,
    require_safe_tree,
)
from fakedetector.config.models import TemporaryStorageConfig
from fakedetector.core import AuthoritativeLifecycleClock
from fakedetector.core.clock import AuthoritativeClockError
from fakedetector.domain import CleanupStatus, ErrorDetail
from fakedetector.intake import LocalTemporaryInputOwner, TemporaryInputCleanupError
from fakedetector.lifecycle.execution import TaskRegistry
from fakedetector.lifecycle.models import AnalysisTask, CleanupFacts, TerminalSettlementSnapshot
from fakedetector.logging_setup import emit_diagnostic

_SYSTEM_ANALYSIS_ID = re.compile(r"^[0-9a-f]{32}$")
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SweepIssue:
    """Safe technical diagnostic for one item not recovered by a sweep."""

    analysis_id: str | None
    code: str


@dataclass(frozen=True, slots=True)
class SweepResult:
    """Deterministic factual summary of one workspace and quarantine sweep."""

    workspaces_deleted: tuple[str, ...]
    workspaces_quarantined: tuple[str, ...]
    quarantine_deleted: tuple[str, ...]
    issues: tuple[SweepIssue, ...]


class WorkspaceCleanup:
    """Resolve one confirmed task's cleanup obligations with configured recovery."""

    def __init__(
        self,
        *,
        config: TemporaryStorageConfig,
        clock: AuthoritativeLifecycleClock,
    ) -> None:
        self._config = config
        self._clock = clock

    def cleanup_task(
        self,
        task: AnalysisTask,
        settlement: TerminalSettlementSnapshot,
        record_progress: Callable[..., None],
    ) -> CleanupFacts:
        """Attempt only outstanding obligations, then optionally quarantine."""
        original_deleted = settlement.original_file_deleted or task.accepted_source.is_released
        artifact_cleanup_completed = settlement.artifact_cleanup_completed
        intermediate_deleted = settlement.intermediate_files_deleted
        if original_deleted and intermediate_deleted:
            return self._facts(
                original_deleted=True,
                intermediate_deleted=True,
                quarantine_used=settlement.quarantine_used,
            )

        attempts_remaining = 1 + self._config.cleanup_retries - settlement.attempts_completed
        for _attempt in range(max(0, attempts_remaining)):
            if not artifact_cleanup_completed:
                try:
                    artifact_cleanup_completed = task.artifacts.cleanup_once().completed
                except Exception:
                    artifact_cleanup_completed = False
                record_progress(
                    original_file_deleted=original_deleted,
                    artifact_cleanup_completed=artifact_cleanup_completed,
                    intermediate_files_deleted=intermediate_deleted,
                )

            source_intermediates_deleted = False
            if not original_deleted or not intermediate_deleted:
                try:
                    task.accepted_source.cleanup()
                except TemporaryInputCleanupError as error:
                    original_deleted = original_deleted or error.original_file_deleted
                    source_intermediates_deleted = error.intermediate_files_deleted
                except Exception:
                    source_intermediates_deleted = False
                else:
                    original_deleted = True
                    source_intermediates_deleted = True

            intermediate_deleted = artifact_cleanup_completed and source_intermediates_deleted
            record_progress(
                original_file_deleted=original_deleted,
                artifact_cleanup_completed=artifact_cleanup_completed,
                intermediate_files_deleted=intermediate_deleted,
                attempt_completed=True,
            )
            if original_deleted and intermediate_deleted:
                record_progress(
                    original_file_deleted=True,
                    artifact_cleanup_completed=artifact_cleanup_completed,
                    intermediate_files_deleted=True,
                    quarantine_used=False,
                    quarantine_decided=True,
                )
                return self._facts(
                    original_deleted=True,
                    intermediate_deleted=True,
                    quarantine_used=False,
                )

        quarantine_used = settlement.quarantine_used
        if self._config.quarantine_enabled and not settlement.quarantine_decided:
            try:
                task.accepted_source._quarantine(self._clock.now())
            except Exception:
                quarantine_used = False
            else:
                quarantine_used = True
            record_progress(
                original_file_deleted=original_deleted,
                artifact_cleanup_completed=artifact_cleanup_completed,
                intermediate_files_deleted=intermediate_deleted,
                quarantine_used=quarantine_used,
                quarantine_decided=True,
            )
        elif not settlement.quarantine_decided:
            record_progress(
                original_file_deleted=original_deleted,
                artifact_cleanup_completed=artifact_cleanup_completed,
                intermediate_files_deleted=intermediate_deleted,
                quarantine_used=quarantine_used,
                quarantine_decided=True,
            )

        return self._facts(
            original_deleted=original_deleted,
            intermediate_deleted=intermediate_deleted,
            quarantine_used=quarantine_used,
        )

    def _facts(
        self,
        *,
        original_deleted: bool,
        intermediate_deleted: bool,
        quarantine_used: bool,
    ) -> CleanupFacts:
        completed = original_deleted and intermediate_deleted
        if completed:
            status = CleanupStatus.COMPLETED
        elif original_deleted or intermediate_deleted:
            status = CleanupStatus.PARTIAL
        else:
            status = CleanupStatus.FAILED
        return CleanupFacts(
            status=status,
            original_file_deleted=original_deleted,
            intermediate_files_deleted=intermediate_deleted,
            quarantine_used=quarantine_used,
            errors=() if completed else (_cleanup_error(),),
        )


class WorkspaceJanitor:
    """Sweep only stale safe direct children of configured application roots."""

    def __init__(
        self,
        *,
        config: TemporaryStorageConfig,
        clock: AuthoritativeLifecycleClock,
        registry: TaskRegistry,
        temporary_input_owner: LocalTemporaryInputOwner,
    ) -> None:
        self._config = config
        self._clock = clock
        self._registry = registry
        self._temporary_input_owner = temporary_input_owner
        self._root = Path(config.root_path)
        self._quarantine_root = self._root.parent / "quarantine"
        self._sweep_lock = Lock()

    def sweep(self) -> SweepResult:
        """Run one serialized best-effort workspace then quarantine recovery pass."""
        with self._sweep_lock:
            try:
                now = self._clock.now()
            except AuthoritativeClockError:
                return SweepResult((), (), (), ())
            deleted, quarantined, workspace_issues = self._sweep_workspaces(now)
            quarantine_deleted, quarantine_issues = self._sweep_quarantine(now)
            issues = (*workspace_issues, *quarantine_issues)
            for issue in issues:
                emit_diagnostic(
                    _LOGGER,
                    logging.WARNING,
                    "cleanup_failed",
                    analysis_id=issue.analysis_id,
                    phase="recovery",
                    code=issue.code,
                    stage="cleanup",
                )
            return SweepResult(
                workspaces_deleted=tuple(deleted),
                workspaces_quarantined=tuple(quarantined),
                quarantine_deleted=tuple(quarantine_deleted),
                issues=issues,
            )

    def _sweep_workspaces(
        self,
        now: datetime,
    ) -> tuple[list[str], list[str], tuple[SweepIssue, ...]]:
        deleted: list[str] = []
        quarantined: list[str] = []
        issues: list[SweepIssue] = []
        entries = self._safe_entries(self._root, issues, "workspace_root_unsafe")
        for entry in entries:
            analysis_id = entry.name
            if not self._trusted_directory(entry, analysis_id):
                issues.append(SweepIssue(None, "workspace_entry_unsafe"))
                continue
            expired = self._expired(entry, now, timedelta(minutes=self._config.ttl_minutes))
            if expired is None:
                issues.append(SweepIssue(analysis_id, "workspace_age_unavailable"))
                continue
            if not expired:
                continue

            def recover_workspace(
                entry: Path = entry,
                analysis_id: str = analysis_id,
            ) -> str:
                return self._recover_workspace(entry, analysis_id)

            def cleanup_if_inactive(
                analysis_id: str = analysis_id,
            ) -> str | None:
                return self._registry.cleanup_if_inactive(
                    analysis_id,
                    recover_workspace,
                )

            outcome = self._temporary_input_owner._cleanup_if_unprotected(
                analysis_id,
                cleanup_if_inactive,
            )
            if outcome == "deleted":
                deleted.append(analysis_id)
            elif outcome == "quarantined":
                quarantined.append(analysis_id)
            elif outcome == "failed":
                issues.append(SweepIssue(analysis_id, "workspace_cleanup_failed"))
        return deleted, quarantined, tuple(issues)

    def _sweep_quarantine(
        self,
        now: datetime,
    ) -> tuple[list[str], tuple[SweepIssue, ...]]:
        deleted: list[str] = []
        issues: list[SweepIssue] = []
        entries = self._safe_entries(
            self._quarantine_root,
            issues,
            "quarantine_root_unsafe",
        )
        for entry in entries:
            analysis_id = entry.name
            if not self._trusted_directory(entry, analysis_id):
                issues.append(SweepIssue(None, "quarantine_entry_unsafe"))
                continue
            expired = self._expired(
                entry,
                now,
                timedelta(hours=self._config.quarantine_ttl_hours),
            )
            if expired is None:
                issues.append(SweepIssue(analysis_id, "quarantine_age_unavailable"))
                continue
            if not expired:
                continue

            def remove_quarantine(
                entry: Path = entry,
            ) -> bool:
                return self._remove_quarantine(entry)

            outcome = self._registry.cleanup_if_inactive(
                analysis_id,
                remove_quarantine,
            )
            if outcome is None:
                continue
            if not outcome:
                issues.append(SweepIssue(analysis_id, "quarantine_cleanup_failed"))
            else:
                deleted.append(analysis_id)
        return deleted, tuple(issues)

    @staticmethod
    def _remove_quarantine(entry: Path) -> bool:
        try:
            require_direct_child_directory(entry.parent, entry)
            require_safe_tree(entry)
            shutil.rmtree(entry)
        except OSError:
            return False
        return True

    def _recover_workspace(self, entry: Path, analysis_id: str) -> str:
        for _attempt in range(1 + self._config.cleanup_retries):
            try:
                require_direct_child_directory(self._root, entry)
                require_safe_tree(entry)
                shutil.rmtree(entry)
            except OSError:
                continue
            return "deleted"

        if not self._config.quarantine_enabled:
            return "failed"
        try:
            self._move_to_quarantine(entry, analysis_id)
        except OSError:
            return "failed"
        return "quarantined"

    def _move_to_quarantine(self, entry: Path, analysis_id: str) -> None:
        destination = self._quarantine_root / analysis_id
        if entry.parent != self._root or destination.parent != self._quarantine_root:
            raise OSError
        require_direct_child_directory(self._root, entry)
        require_safe_tree(entry)
        ensure_private_directory(self._quarantine_root)
        require_missing_path(destination)
        entry.rename(destination)
        require_direct_child_directory(self._quarantine_root, destination)
        require_safe_tree(destination)
        timestamp = self._clock.now().timestamp()
        with suppress(OSError):
            os.utime(destination, (timestamp, timestamp))

    @staticmethod
    def _safe_entries(root: Path, issues: list[SweepIssue], code: str) -> tuple[Path, ...]:
        try:
            if not require_safe_directory(root, missing_ok=True):
                return ()
            return tuple(sorted(root.iterdir(), key=lambda entry: entry.name))
        except OSError:
            issues.append(SweepIssue(None, code))
            return ()

    @staticmethod
    def _trusted_directory(entry: Path, analysis_id: str) -> bool:
        if _SYSTEM_ANALYSIS_ID.fullmatch(analysis_id) is None:
            return False
        try:
            require_direct_child_directory(entry.parent, entry)
            require_safe_tree(entry)
        except OSError:
            return False
        return True

    @staticmethod
    def _expired(entry: Path, now: datetime, ttl: timedelta) -> bool | None:
        try:
            modified_at = datetime.fromtimestamp(entry.stat(follow_symlinks=False).st_mtime, UTC)
        except OSError:
            return None
        return now - modified_at >= ttl


def _cleanup_error() -> ErrorDetail:
    return ErrorDetail(
        code="cleanup_failed",
        category="cleanup",
        message="Не удалось полностью удалить временные данные.",
        retryable=True,
    )
