"""Concrete Stage 4 receiver and explicit deterministic lifecycle runner."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from fakedetector.config.models import AppConfig
from fakedetector.core import Clock
from fakedetector.domain import AnalysisStatus, ErrorDetail, ProcessingStage
from fakedetector.intake import Stage3Accepted
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry
from fakedetector.lifecycle.cleanup import WorkspaceCleanup
from fakedetector.lifecycle.execution import (
    DeterministicTaskQueue,
    MediaRouter,
    TaskExecutor,
    TaskQueue,
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
        queue: TaskQueue,
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
            self._queue.commit(analysis_id)
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
    """Run one FIFO task explicitly, terminalize it, and recover cleanup."""

    def __init__(
        self,
        *,
        config: AppConfig,
        clock: Clock,
        registry: TaskRegistry,
        queue: DeterministicTaskQueue,
    ) -> None:
        self._clock = clock
        self._registry = registry
        self._queue = queue
        self._processor = Stage4TaskProcessor(config=config, clock=clock, registry=registry)

    def run_next(self) -> TaskSnapshot | None:
        """Execute and finish exactly one queued task, or return None when empty."""
        item = self._queue.pop_next()
        if item is None:
            return None
        analysis_id, executor = item
        return self._processor.execute(analysis_id, executor)


class Stage4TaskProcessor:
    """Canonical claim, execution, terminalization, and cleanup-recovery core."""

    def __init__(self, *, config: AppConfig, clock: Clock, registry: TaskRegistry) -> None:
        self._clock = clock
        self._registry = registry
        self._cleanup = WorkspaceCleanup(config=config.temporary_storage, clock=clock)

    def execute(self, analysis_id: str, executor: TaskExecutor) -> TaskSnapshot:
        """Claim and finish one confirmed task, propagating only ``BaseException``."""
        task = self.claim_execution(analysis_id)
        return self.execute_claimed(task, executor)

    def claim_execution(self, analysis_id: str) -> AnalysisTask:
        """Apply the authoritative exactly-once execution claim."""
        return self._registry.claim(analysis_id, self._clock.now())

    def execute_claimed(self, task: AnalysisTask, executor: TaskExecutor) -> TaskSnapshot:
        """Finish one task whose exactly-once registry claim already succeeded."""
        analysis_id = task.context.analysis_id
        termination: BaseException | None = None
        try:
            outcome = executor.execute(task)
            if not isinstance(outcome, TaskExecutionOutcome):
                raise TypeError("executor returned an invalid outcome")
        except Exception:
            outcome = TaskExecutionOutcome.failed(_execution_error())
        except BaseException as error:
            outcome = TaskExecutionOutcome.failed(_execution_error())
            termination = error

        self._registry.record_outcome(analysis_id, outcome)
        snapshot = self._cleanup_and_finish(task)
        if termination is not None:
            raise termination
        return snapshot

    def fail_pending(self, analysis_id: str) -> TaskSnapshot:
        """Fail one confirmed task that never factually started execution."""
        task = self.claim_pending_failure(analysis_id)
        return self._cleanup_and_finish(task)

    def claim_pending_failure(self, analysis_id: str) -> AnalysisTask:
        """Claim a never-started task for shutdown failure terminalization."""
        return self._registry.fail_pending(analysis_id, _shutdown_error())

    def finish_failed_pending(self, task: AnalysisTask) -> TaskSnapshot:
        """Cleanup one pending task already claimed for shutdown terminalization."""
        return self._cleanup_and_finish(task)

    def _cleanup_and_finish(self, task: AnalysisTask) -> TaskSnapshot:
        analysis_id = task.context.analysis_id
        cleanup_result = self._cleanup.cleanup_task(task)
        if cleanup_result.finished_at is None:
            cleanup_result = cleanup_result.model_copy(
                update={"finished_at": datetime.now(UTC)},
            )
        self._registry.record_terminal_cleanup_and_finish(analysis_id, cleanup_result)
        return self._registry.snapshot(analysis_id)


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


def _shutdown_error() -> ErrorDetail:
    return ErrorDetail(
        code="internal_error",
        category="internal",
        message="Задача анализа не выполнена из-за остановки обработки.",
        retryable=True,
    )
