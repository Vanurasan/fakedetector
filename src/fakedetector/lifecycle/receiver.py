"""Concrete Stage 4 receiver and explicit deterministic lifecycle runner."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path, PureWindowsPath

from fakedetector.config.models import AppConfig
from fakedetector.core import Clock
from fakedetector.domain import (
    AnalysisStatus,
    CleanupResult,
    CleanupStatus,
    ErrorDetail,
    ProcessingStage,
)
from fakedetector.intake import Stage3Accepted, TemporaryInputCleanupError
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry
from fakedetector.lifecycle.execution import (
    DeterministicTaskQueue,
    LifecycleStateError,
    MediaRouter,
    TaskRegistry,
)
from fakedetector.lifecycle.models import (
    AnalysisContext,
    AnalysisTask,
    TaskExecutionOutcome,
    TaskSnapshot,
    config_snapshot_fingerprint,
)


class Stage4ReceiverError(Exception):
    """Safe typed failure before the Stage 3 to Stage 4 handoff commit."""

    def __init__(self) -> None:
        super().__init__("Stage 4 could not accept the analysis task.")


class Stage4TaskReceiver:
    """Commit accepted ownership only after registry, route, and FIFO success."""

    def __init__(
        self,
        *,
        config: AppConfig,
        clock: Clock,
        registry: TaskRegistry,
        router: MediaRouter,
        queue: DeterministicTaskQueue,
    ) -> None:
        self._config = config
        self._clock = clock
        self._registry = registry
        self._router = router
        self._queue = queue
        self._config_snapshot_id = config_snapshot_fingerprint(config)

    def accept(self, accepted: Stage3Accepted) -> None:
        """Perform the provisional receiver phase and return only after commit."""
        analysis_id = accepted.analysis_id
        reserved = False
        try:
            self._validate_accepted(accepted)
            workspace_path = _workspace_path(
                self._config.temporary_storage.root_path,
                accepted.analysis_id,
            )
            context = AnalysisContext(
                analysis_id=accepted.analysis_id,
                created_at=accepted.registered_at,
                status=AnalysisStatus.QUEUED,
                stage=ProcessingStage.REGISTERED,
                source=accepted.source.model_copy(deep=True),
                workspace_path=workspace_path,
                media_type=accepted.validated_file.media_type,
                config_snapshot_id=self._config_snapshot_id,
            )
            task = AnalysisTask(
                context=context,
                validation=accepted.validation.model_copy(deep=True),
                validated_file=accepted.validated_file.model_copy(deep=True),
                accepted_source=accepted.controlled_source,
                artifacts=WorkspaceArtifactRegistry(workspace_path),
            )
            self._registry.reserve(task)
            reserved = True
            self._registry.transition(
                analysis_id,
                status=AnalysisStatus.QUEUED,
                stage=ProcessingStage.ROUTING,
            )
            executor = self._router.resolve(task.validated_file)
            self._registry.bind_route(analysis_id, task.validated_file.media_type)
            self._registry.transition(
                analysis_id,
                status=AnalysisStatus.QUEUED,
                stage=ProcessingStage.QUEUED,
            )
            queued_at = self._clock.now()
            self._queue.enqueue(task, executor)
            self._registry.mark_enqueued(analysis_id, queued_at)
        except BaseException as error:
            if reserved:
                self._queue.remove(analysis_id)
                self._registry.rollback(analysis_id)
            if isinstance(error, Exception):
                raise Stage4ReceiverError() from None
            raise

    @staticmethod
    def _validate_accepted(accepted: Stage3Accepted) -> None:
        if accepted.analysis_id != accepted.controlled_source.analysis_id:
            raise ValueError("accepted source identity mismatch")
        if not accepted.validation.accepted or accepted.validation.validated_file is None:
            raise ValueError("accepted validation is not successful")
        if accepted.validation.validated_file != accepted.validated_file:
            raise ValueError("accepted descriptor does not match validation")


class Stage4LifecycleRunner:
    """Run one FIFO task explicitly, terminalize it, and attempt cleanup once."""

    def __init__(
        self,
        *,
        clock: Clock,
        registry: TaskRegistry,
        queue: DeterministicTaskQueue,
    ) -> None:
        self._clock = clock
        self._registry = registry
        self._queue = queue

    def run_next(self) -> TaskSnapshot | None:
        """Execute and finish exactly one queued task, or return None when empty."""
        item = self._queue.pop_next()
        if item is None:
            return None
        analysis_id, executor = item
        task = self._registry.claim(analysis_id, self._clock.now())
        termination: BaseException | None = None
        try:
            outcome = executor.execute(task)
        except Exception:
            outcome = TaskExecutionOutcome.failed(_execution_error())
        except BaseException as error:
            outcome = TaskExecutionOutcome.failed(_execution_error())
            termination = error

        self._registry.record_outcome(analysis_id, outcome)
        task.cleanup_result = _cleanup_once(task, self._clock)
        finished_at = task.cleanup_result.finished_at
        if finished_at is None:
            raise LifecycleStateError()
        self._registry.finish(analysis_id, finished_at)
        snapshot = self._registry.snapshot(analysis_id)
        if termination is not None:
            raise termination
        return snapshot


def _workspace_path(root_path: str, analysis_id: str) -> Path:
    windows_component = PureWindowsPath(analysis_id)
    if (
        not analysis_id
        or analysis_id in {".", ".."}
        or "/" in analysis_id
        or "\\" in analysis_id
        or ":" in analysis_id
        or "\0" in analysis_id
        or windows_component.drive
        or windows_component.is_reserved()
    ):
        raise ValueError("unsafe analysis identity")
    root = Path(root_path)
    workspace = root / analysis_id
    if workspace.parent != root:
        raise ValueError("unsafe analysis workspace")
    return workspace


def _cleanup_once(task: AnalysisTask, clock: Clock) -> CleanupResult:
    try:
        intermediate_deleted = task.artifacts.cleanup_once().completed
    except Exception:
        intermediate_deleted = False

    original_deleted = False
    source_intermediates_deleted = False
    cleanup_failed = False
    try:
        task.accepted_source.cleanup()
        original_deleted = True
        source_intermediates_deleted = True
    except TemporaryInputCleanupError as error:
        original_deleted = error.original_file_deleted
        source_intermediates_deleted = error.intermediate_files_deleted
        cleanup_failed = True
    except Exception:
        cleanup_failed = True

    intermediate_deleted = intermediate_deleted and source_intermediates_deleted
    completed = original_deleted and intermediate_deleted and not cleanup_failed
    if completed:
        status = CleanupStatus.COMPLETED
    elif original_deleted or intermediate_deleted:
        status = CleanupStatus.PARTIAL
    else:
        status = CleanupStatus.FAILED
    errors = [] if completed else [_cleanup_error()]
    return CleanupResult(
        status=status,
        original_file_deleted=original_deleted,
        intermediate_files_deleted=intermediate_deleted,
        quarantine_used=False,
        finished_at=_safe_now(clock),
        errors=errors,
    )


def _safe_now(clock: Clock) -> datetime | None:
    try:
        return clock.now()
    except Exception:
        return None


def _execution_error() -> ErrorDetail:
    return ErrorDetail(
        code="internal_error",
        category="internal",
        message="Внутренняя ошибка не позволила выполнить задачу анализа.",
        retryable=True,
    )


def _cleanup_error() -> ErrorDetail:
    return ErrorDetail(
        code="cleanup_failed",
        category="cleanup",
        message="Не удалось полностью удалить временные данные.",
        retryable=True,
    )
