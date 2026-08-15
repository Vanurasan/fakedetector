"""State, registry, canonical routing, and deterministic FIFO execution."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Protocol, TypeVar

from fakedetector.domain import (
    AnalysisStatus,
    CleanupResult,
    ErrorDetail,
    MediaType,
    ProcessingStage,
    ValidatedFileDescriptor,
)
from fakedetector.lifecycle.models import AnalysisTask, TaskExecutionOutcome, TaskSnapshot

_CleanupOutcome = TypeVar("_CleanupOutcome")


class LifecycleStateError(Exception):
    """Safe invalid task lifecycle transition."""

    def __init__(self) -> None:
        super().__init__("Task lifecycle transition is invalid.")


class DuplicateTaskError(Exception):
    """Safe duplicate analysis identity reservation failure."""

    def __init__(self) -> None:
        super().__init__("Analysis task identity is already reserved.")


class TaskNotFoundError(Exception):
    """Safe missing task lookup failure."""

    def __init__(self) -> None:
        super().__init__("Analysis task was not found.")


class RouteBindingError(Exception):
    """Safe internal failure for a missing canonical executor binding."""

    def __init__(self) -> None:
        super().__init__("Canonical media executor binding is unavailable.")


class QueueStateError(Exception):
    """Safe rejection of duplicate, terminal, or otherwise invalid enqueue."""

    def __init__(self) -> None:
        super().__init__("Analysis task cannot be enqueued.")


class TaskExecutor(Protocol):
    """Narrow injected execution port for the managed lifecycle slice."""

    def execute(self, task: AnalysisTask) -> TaskExecutionOutcome:
        """Return only a factual primary execution outcome."""
        ...


class TaskQueue(Protocol):
    """Receiver-facing queue port with an explicit non-failing commit boundary."""

    def enqueue(self, task: AnalysisTask, executor: TaskExecutor) -> None:
        """Reserve local queue capacity for a provisional task."""
        ...

    def commit(self, analysis_id: str) -> None:
        """Make one provisional item dispatchable as the final receiver step."""
        ...

    def remove(self, analysis_id: str) -> None:
        """Remove a provisional queue reservation during receiver rollback."""
        ...


class AnalysisStateMachine:
    """Validate and apply the narrow Increment 1 status/stage transitions."""

    _TRANSITIONS = {
        (AnalysisStatus.QUEUED, ProcessingStage.REGISTERED): {
            (AnalysisStatus.QUEUED, ProcessingStage.ROUTING)
        },
        (AnalysisStatus.QUEUED, ProcessingStage.ROUTING): {
            (AnalysisStatus.QUEUED, ProcessingStage.QUEUED)
        },
        (AnalysisStatus.QUEUED, ProcessingStage.QUEUED): {
            (AnalysisStatus.RUNNING, ProcessingStage.PREPROCESSING),
            (AnalysisStatus.FAILED, ProcessingStage.CLEANUP),
        },
        (AnalysisStatus.RUNNING, ProcessingStage.PREPROCESSING): {
            (AnalysisStatus.COMPLETED, ProcessingStage.CLEANUP),
            (AnalysisStatus.FAILED, ProcessingStage.CLEANUP),
        },
        (AnalysisStatus.COMPLETED, ProcessingStage.CLEANUP): {
            (AnalysisStatus.COMPLETED, ProcessingStage.FINISHED)
        },
        (AnalysisStatus.FAILED, ProcessingStage.CLEANUP): {
            (AnalysisStatus.FAILED, ProcessingStage.FINISHED)
        },
    }

    def transition(
        self,
        task: AnalysisTask,
        *,
        status: AnalysisStatus,
        stage: ProcessingStage,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """Replace the complete immutable context only after all checks pass."""
        current = (task.context.status, task.context.stage)
        target = (status, stage)
        if target not in self._TRANSITIONS.get(current, set()):
            raise LifecycleStateError()
        if stage is ProcessingStage.PREPROCESSING:
            if task.context.started_at is not None or started_at is None:
                raise LifecycleStateError()
        elif started_at is not None:
            raise LifecycleStateError()
        if stage is ProcessingStage.FINISHED:
            if task.context.finished_at is not None or finished_at is None:
                raise LifecycleStateError()
        elif finished_at is not None:
            raise LifecycleStateError()

        task.context = replace(
            task.context,
            status=status,
            stage=stage,
            started_at=started_at or task.context.started_at,
            finished_at=finished_at,
        )


class TaskRegistry:
    """Authoritative typed in-process store for live and terminal Stage 4 tasks."""

    def __init__(self, state_machine: AnalysisStateMachine | None = None) -> None:
        self._tasks: dict[str, AnalysisTask] = {}
        self._cleanup_claims: set[str] = set()
        self._lock = RLock()
        self._state_machine = state_machine or AnalysisStateMachine()

    def reserve(self, task: AnalysisTask) -> None:
        with self._lock:
            analysis_id = task.context.analysis_id
            if analysis_id in self._tasks or analysis_id in self._cleanup_claims:
                raise DuplicateTaskError()
            self._tasks[analysis_id] = task

    def rollback(self, analysis_id: str) -> None:
        with self._lock:
            self._tasks.pop(analysis_id, None)

    def contains(self, analysis_id: str) -> bool:
        with self._lock:
            return analysis_id in self._tasks

    def is_active(self, analysis_id: str) -> bool:
        """Return whether a known task has not factually reached ``finished``."""
        with self._lock:
            task = self._tasks.get(analysis_id)
            return task is not None and task.context.stage is not ProcessingStage.FINISHED

    def cleanup_if_inactive(
        self,
        analysis_id: str,
        cleanup: Callable[[AnalysisTask | None], _CleanupOutcome],
    ) -> _CleanupOutcome | None:
        """Run cleanup with any inactive task while reservation cannot race it."""
        with self._lock:
            task = self._tasks.get(analysis_id)
            if task is not None and task.context.stage is not ProcessingStage.FINISHED:
                return None
            self._cleanup_claims.add(analysis_id)
            return cleanup(task)

    def snapshot(self, analysis_id: str) -> TaskSnapshot:
        with self._lock:
            return self._get(analysis_id).snapshot()

    def transition(
        self,
        analysis_id: str,
        *,
        status: AnalysisStatus,
        stage: ProcessingStage,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        with self._lock:
            self._state_machine.transition(
                self._get(analysis_id),
                status=status,
                stage=stage,
                started_at=started_at,
                finished_at=finished_at,
            )

    def mark_enqueued(self, analysis_id: str, queued_at: datetime) -> None:
        with self._lock:
            task = self._get(analysis_id)
            if task.queued_at is not None or task.context.stage is not ProcessingStage.QUEUED:
                raise QueueStateError()
            task.queued_at = queued_at

    def bind_route(self, analysis_id: str, media_type: MediaType) -> None:
        with self._lock:
            task = self._get(analysis_id)
            if task.route is not None or task.context.stage is not ProcessingStage.ROUTING:
                raise LifecycleStateError()
            if media_type is not task.validated_file.media_type:
                raise LifecycleStateError()
            task.route = media_type

    def claim(self, analysis_id: str, started_at: datetime) -> AnalysisTask:
        with self._lock:
            task = self._get(analysis_id)
            if task.execution_claimed or task.queued_at is None:
                raise LifecycleStateError()
            self._state_machine.transition(
                task,
                status=AnalysisStatus.RUNNING,
                stage=ProcessingStage.PREPROCESSING,
                started_at=started_at,
            )
            task.execution_claimed = True
            return task

    def record_outcome(self, analysis_id: str, outcome: TaskExecutionOutcome) -> None:
        with self._lock:
            task = self._get(analysis_id)
            self._state_machine.transition(
                task,
                status=outcome.status,
                stage=ProcessingStage.CLEANUP,
            )
            task.errors.extend(error.model_copy(deep=True) for error in outcome.errors)

    def fail_pending(self, analysis_id: str, error: ErrorDetail) -> AnalysisTask:
        """Claim terminalization, without execution, for one confirmed pending task."""
        with self._lock:
            task = self._get(analysis_id)
            if task.execution_claimed or task.queued_at is None:
                raise LifecycleStateError()
            self._state_machine.transition(
                task,
                status=AnalysisStatus.FAILED,
                stage=ProcessingStage.CLEANUP,
            )
            task.errors.append(error.model_copy(deep=True))
            return task

    def record_terminal_cleanup_and_finish(
        self,
        analysis_id: str,
        cleanup_result: CleanupResult,
    ) -> None:
        """Atomically record factual cleanup and move its task to ``finished``."""
        with self._lock:
            task = self._get(analysis_id)
            if (
                task.context.stage is not ProcessingStage.CLEANUP
                or task.cleanup_result is not None
                or cleanup_result.finished_at is None
            ):
                raise LifecycleStateError()
            recorded_cleanup = cleanup_result.model_copy(deep=True)
            self._state_machine.transition(
                task,
                status=task.context.status,
                stage=ProcessingStage.FINISHED,
                finished_at=cleanup_result.finished_at,
            )
            task.cleanup_result = recorded_cleanup

    def _get(self, analysis_id: str) -> AnalysisTask:
        try:
            return self._tasks[analysis_id]
        except KeyError:
            raise TaskNotFoundError() from None


class MediaRouter:
    """Resolve an injected executor solely from validated canonical media type."""

    def __init__(self, bindings: dict[MediaType, TaskExecutor]) -> None:
        self._bindings = dict(bindings)

    def resolve(self, validated_file: ValidatedFileDescriptor) -> TaskExecutor:
        try:
            return self._bindings[validated_file.media_type]
        except KeyError:
            raise RouteBindingError() from None


class DeterministicTaskQueue:
    """Single-threaded FIFO storing already resolved task executor routes."""

    def __init__(self) -> None:
        self._items: deque[tuple[str, TaskExecutor]] = deque()
        self._analysis_ids: set[str] = set()

    def enqueue(self, task: AnalysisTask, executor: TaskExecutor) -> None:
        analysis_id = task.context.analysis_id
        if (
            analysis_id in self._analysis_ids
            or task.queued_at is not None
            or task.execution_claimed
            or task.context.status is not AnalysisStatus.QUEUED
            or task.context.stage is not ProcessingStage.QUEUED
        ):
            raise QueueStateError()
        self._items.append((analysis_id, executor))
        self._analysis_ids.add(analysis_id)

    def remove(self, analysis_id: str) -> None:
        if analysis_id not in self._analysis_ids:
            return
        self._items = deque(item for item in self._items if item[0] != analysis_id)
        self._analysis_ids.discard(analysis_id)

    def commit(self, analysis_id: str) -> None:
        """Preserve the explicit receiver boundary; deterministic items never auto-run."""
        if analysis_id not in self._analysis_ids:
            raise QueueStateError()

    def pop_next(self) -> tuple[str, TaskExecutor] | None:
        if not self._items:
            return None
        item = self._items.popleft()
        self._analysis_ids.remove(item[0])
        return item

    def __len__(self) -> int:
        return len(self._items)
