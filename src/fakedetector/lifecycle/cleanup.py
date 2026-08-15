"""Deterministic post-handoff cleanup recovery for controlled local workspaces."""

from __future__ import annotations

import logging
import os
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from fakedetector.config.models import TemporaryStorageConfig
from fakedetector.core import Clock
from fakedetector.domain import CleanupResult, CleanupStatus, ErrorDetail
from fakedetector.intake import TemporaryInputCleanupError
from fakedetector.lifecycle.execution import TaskRegistry
from fakedetector.lifecycle.models import AnalysisTask

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

    def __init__(self, *, config: TemporaryStorageConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock

    def cleanup_task(self, task: AnalysisTask) -> CleanupResult:
        """Attempt only outstanding obligations, then optionally quarantine."""
        original_deleted = task.accepted_source.is_released
        intermediate_deleted = False

        for _attempt in range(1 + self._config.cleanup_retries):
            if not intermediate_deleted:
                try:
                    intermediate_deleted = task.artifacts.cleanup_once().completed
                except Exception:
                    intermediate_deleted = False

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

            intermediate_deleted = intermediate_deleted and source_intermediates_deleted
            if original_deleted and intermediate_deleted:
                return self._result(
                    original_deleted=True,
                    intermediate_deleted=True,
                    quarantine_used=False,
                )

        quarantine_used = False
        if self._config.quarantine_enabled:
            try:
                task.accepted_source._quarantine(self._clock.now())
            except Exception:
                quarantine_used = False
            else:
                quarantine_used = True

        return self._result(
            original_deleted=original_deleted,
            intermediate_deleted=intermediate_deleted,
            quarantine_used=quarantine_used,
        )

    def _result(
        self,
        *,
        original_deleted: bool,
        intermediate_deleted: bool,
        quarantine_used: bool,
    ) -> CleanupResult:
        completed = original_deleted and intermediate_deleted
        if completed:
            status = CleanupStatus.COMPLETED
        elif original_deleted or intermediate_deleted:
            status = CleanupStatus.PARTIAL
        else:
            status = CleanupStatus.FAILED
        return CleanupResult(
            status=status,
            original_file_deleted=original_deleted,
            intermediate_files_deleted=intermediate_deleted,
            quarantine_used=quarantine_used,
            finished_at=_safe_now(self._clock),
            errors=[] if completed else [_cleanup_error()],
        )


class WorkspaceJanitor:
    """Sweep only stale safe direct children of configured application roots."""

    def __init__(
        self,
        *,
        config: TemporaryStorageConfig,
        clock: Clock,
        registry: TaskRegistry,
    ) -> None:
        self._config = config
        self._clock = clock
        self._registry = registry
        self._root = Path(config.root_path)
        self._quarantine_root = self._root.parent / "quarantine"
        self._sweep_lock = Lock()

    def sweep(self) -> SweepResult:
        """Run one serialized best-effort workspace then quarantine recovery pass."""
        with self._sweep_lock:
            now = self._clock.now()
            deleted, quarantined, workspace_issues = self._sweep_workspaces(now)
            quarantine_deleted, quarantine_issues = self._sweep_quarantine(now)
            issues = (*workspace_issues, *quarantine_issues)
            for issue in issues:
                _LOGGER.warning(
                    "Stage 4 cleanup recovery did not complete.",
                    extra={"analysis_id": issue.analysis_id, "cleanup_code": issue.code},
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

            def recover_workspace(entry: Path = entry, analysis_id: str = analysis_id) -> str:
                return self._recover_workspace(entry, analysis_id)

            outcome = self._registry.cleanup_if_inactive(
                analysis_id,
                recover_workspace,
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

            def remove_quarantine(entry: Path = entry) -> bool:
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
            shutil.rmtree(entry)
        except OSError:
            return False
        return True

    def _recover_workspace(self, entry: Path, analysis_id: str) -> str:
        for _attempt in range(1 + self._config.cleanup_retries):
            try:
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
        if self._quarantine_root.exists():
            if self._quarantine_root.is_symlink() or not self._quarantine_root.is_dir():
                raise OSError
        else:
            self._quarantine_root.mkdir()
        if destination.exists() or destination.is_symlink():
            raise OSError
        entry.rename(destination)
        timestamp = self._clock.now().timestamp()
        with suppress(OSError):
            os.utime(destination, (timestamp, timestamp))

    @staticmethod
    def _safe_entries(root: Path, issues: list[SweepIssue], code: str) -> tuple[Path, ...]:
        if not root.exists():
            return ()
        if root.is_symlink() or not root.is_dir():
            issues.append(SweepIssue(None, code))
            return ()
        try:
            return tuple(sorted(root.iterdir(), key=lambda entry: entry.name))
        except OSError:
            issues.append(SweepIssue(None, code))
            return ()

    @staticmethod
    def _trusted_directory(entry: Path, analysis_id: str) -> bool:
        return (
            _SYSTEM_ANALYSIS_ID.fullmatch(analysis_id) is not None
            and not entry.is_symlink()
            and entry.is_dir()
        )

    @staticmethod
    def _expired(entry: Path, now: datetime, ttl: timedelta) -> bool | None:
        try:
            modified_at = datetime.fromtimestamp(entry.stat(follow_symlinks=False).st_mtime, UTC)
        except OSError:
            return None
        return now - modified_at >= ttl


def _safe_now(clock: Clock) -> datetime | None:
    try:
        return clock.now()
    except Exception:
        return None


def _cleanup_error() -> ErrorDetail:
    return ErrorDetail(
        code="cleanup_failed",
        category="cleanup",
        message="Не удалось полностью удалить временные данные.",
        retryable=True,
    )
