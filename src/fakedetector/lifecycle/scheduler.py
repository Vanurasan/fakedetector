"""Bounded local per-media scheduling and controlled worker lifecycle."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from threading import Condition, RLock, Thread

from fakedetector.config.models import AppConfig
from fakedetector.core import Clock
from fakedetector.domain import AnalysisStatus, MediaType, ProcessingStage
from fakedetector.lifecycle.cleanup import WorkspaceJanitor
from fakedetector.lifecycle.execution import (
    QueueStateError,
    TaskExecutor,
    TaskRegistry,
)
from fakedetector.lifecycle.models import AnalysisTask
from fakedetector.lifecycle.receiver import Stage4TaskProcessor

_LOGGER = logging.getLogger(__name__)


class SchedulerStateError(Exception):
    """Safe rejection of an invalid local scheduler lifecycle operation."""

    def __init__(self) -> None:
        super().__init__("Local task scheduler lifecycle operation is invalid.")


class _SchedulerState(Enum):
    NOT_STARTED = auto()
    RUNNING = auto()
    SHUTTING_DOWN = auto()
    STOPPED = auto()


@dataclass(slots=True)
class _QueueItem:
    analysis_id: str
    executor: TaskExecutor
    dispatchable: bool = False


@dataclass(frozen=True, slots=True)
class _ClaimedItem:
    item: _QueueItem
    task: AnalysisTask
    execute: bool


class BoundedLocalScheduler:
    """Explicit local scheduler with bounded FIFO queues and per-media workers.

    Each media queue's pending capacity equals that media's configured worker
    limit. This deterministic policy bounds both queued work and worker resources
    without extending the canonical configuration schema.
    """

    def __init__(
        self,
        *,
        config: AppConfig,
        clock: Clock,
        registry: TaskRegistry,
    ) -> None:
        limits = config.limits.max_parallel_tasks
        self._limits = {
            MediaType.IMAGE: limits.image,
            MediaType.AUDIO: limits.audio,
            MediaType.VIDEO: limits.video,
        }
        self._queues = {media_type: deque[_QueueItem]() for media_type in MediaType}
        self._analysis_ids: set[str] = set()
        self._condition = Condition(RLock())
        self._processor = Stage4TaskProcessor(config=config, clock=clock, registry=registry)
        self._janitor = WorkspaceJanitor(
            config=config.temporary_storage,
            clock=clock,
            registry=registry,
        )
        self._registry = registry
        self._state = _SchedulerState.NOT_STARTED
        self._drain = True
        self._threads: list[Thread] = []
        self._shutdown_in_progress = False
        self._termination: BaseException | None = None

    @property
    def is_running(self) -> bool:
        """Return whether submissions may currently be accepted."""
        with self._condition:
            return self._state is _SchedulerState.RUNNING

    @property
    def is_stopped(self) -> bool:
        """Return whether shutdown joined all worker resources."""
        with self._condition:
            return self._state is _SchedulerState.STOPPED

    def capacity(self, media_type: MediaType) -> int:
        """Return the deterministic pending capacity for one canonical route."""
        return self._limits[media_type]

    def pending_count(self, media_type: MediaType) -> int:
        """Return queued provisional and confirmed items for one media type."""
        with self._condition:
            return len(self._queues[media_type])

    def wait_until_not_accepting(self, timeout: float) -> bool:
        """Wait boundedly until submissions are no longer accepted."""
        with self._condition:
            return self._condition.wait_for(
                lambda: self._state is not _SchedulerState.RUNNING,
                timeout=timeout,
            )

    def start(self) -> None:
        """Create all configured workers and atomically make the scheduler ready."""
        self._sweep_best_effort()
        with self._condition:
            if self._state is not _SchedulerState.NOT_STARTED:
                raise SchedulerStateError()
            threads = [
                Thread(
                    target=self._worker,
                    args=(media_type,),
                    name=f"stage4-{media_type.value}-{index}",
                    daemon=False,
                )
                for media_type in MediaType
                for index in range(self._limits[media_type])
            ]
            started: list[Thread] = []
            try:
                for thread in threads:
                    thread.start()
                    started.append(thread)
            except Exception:
                self._threads = started
                self._state = _SchedulerState.STOPPED
                self._condition.notify_all()
                failure = True
            else:
                self._threads = threads
                self._state = _SchedulerState.RUNNING
                self._condition.notify_all()
                failure = False

        if failure:
            for thread in started:
                thread.join()
            raise SchedulerStateError() from None

    def enqueue(self, task: AnalysisTask, executor: TaskExecutor) -> None:
        """Reserve capacity non-blockingly while the handoff remains provisional."""
        analysis_id = task.context.analysis_id
        media_type = task.validated_file.media_type
        with self._condition:
            queue = self._queues[media_type]
            if (
                self._state is not _SchedulerState.RUNNING
                or len(queue) >= self._limits[media_type]
                or analysis_id in self._analysis_ids
                or task.queued_at is not None
                or task.execution_claimed
                or task.context.status is not AnalysisStatus.QUEUED
                or task.context.stage is not ProcessingStage.QUEUED
                or task.route is not media_type
            ):
                raise QueueStateError()
            queue.append(_QueueItem(analysis_id=analysis_id, executor=executor))
            self._analysis_ids.add(analysis_id)

    def commit(self, analysis_id: str) -> None:
        """Atomically decide ownership and expose an item to workers.

        Shutdown can win only before this boundary. Once this method marks the
        item dispatchable, it performs no potentially failing receiver work.
        """
        with self._condition:
            if self._state is not _SchedulerState.RUNNING:
                raise QueueStateError()
            item = self._find(analysis_id)
            if item is None or item.dispatchable:
                raise QueueStateError()
            item.dispatchable = True
            self._condition.notify_all()

    def remove(self, analysis_id: str) -> None:
        """Release only a non-dispatchable provisional reservation."""
        with self._condition:
            for queue in self._queues.values():
                for item in queue:
                    if item.analysis_id == analysis_id and not item.dispatchable:
                        queue.remove(item)
                        self._analysis_ids.discard(analysis_id)
                        self._condition.notify_all()
                        return

    def shutdown(self, *, drain: bool = True) -> None:
        """Stop submissions, settle all confirmed work, and join every worker."""
        with self._condition:
            worker_terminated = (
                self._state is _SchedulerState.SHUTTING_DOWN
                and self._termination is not None
                and not self._shutdown_in_progress
            )
            if self._state is not _SchedulerState.RUNNING and not worker_terminated:
                raise SchedulerStateError()
            self._shutdown_in_progress = True
            if self._state is _SchedulerState.RUNNING:
                self._state = _SchedulerState.SHUTTING_DOWN
                self._drain = drain
                self._discard_provisional()
            threads = tuple(self._threads)
            self._condition.notify_all()

        for thread in threads:
            thread.join()

        self._sweep_best_effort()

        with self._condition:
            self._state = _SchedulerState.STOPPED
            self._threads.clear()
            self._shutdown_in_progress = False
            termination = self._termination
            self._condition.notify_all()
        if termination is not None:
            raise termination

    def _worker(self, media_type: MediaType) -> None:
        while True:
            claimed = self._take_next(media_type)
            if claimed is None:
                return
            try:
                if claimed.execute:
                    self._processor.execute_claimed(claimed.task, claimed.item.executor)
                else:
                    self._processor.finish_failed_pending(claimed.task)
            except Exception:
                self._settle_infrastructure_failure(claimed.item.analysis_id)
            except BaseException as error:
                self._stop_after_worker_termination(error)
            finally:
                self._sweep_best_effort()

    def _take_next(self, media_type: MediaType) -> _ClaimedItem | None:
        with self._condition:
            queue = self._queues[media_type]
            while True:
                if queue and queue[0].dispatchable:
                    item = queue[0]
                    execute = not (
                        self._state is _SchedulerState.SHUTTING_DOWN and not self._drain
                    )
                    task = (
                        self._processor.claim_execution(item.analysis_id)
                        if execute
                        else self._processor.claim_pending_failure(item.analysis_id)
                    )
                    queue.popleft()
                    self._analysis_ids.remove(item.analysis_id)
                    return _ClaimedItem(item=item, task=task, execute=execute)
                if self._state in {_SchedulerState.SHUTTING_DOWN, _SchedulerState.STOPPED}:
                    return None
                self._condition.wait()

    def _sweep_best_effort(self) -> None:
        try:
            self._janitor.sweep()
        except Exception:
            _LOGGER.warning("Stage 4 cleanup recovery sweep failed.")

    def _settle_infrastructure_failure(self, analysis_id: str) -> None:
        try:
            snapshot = self._registry.snapshot(analysis_id)
            if (
                snapshot.status is AnalysisStatus.QUEUED
                and snapshot.stage is ProcessingStage.QUEUED
                and snapshot.queued_at is not None
            ):
                self._processor.fail_pending(analysis_id)
        except Exception:
            return

    def _stop_after_worker_termination(self, error: BaseException) -> None:
        with self._condition:
            if self._termination is None:
                self._termination = error
            if self._state is _SchedulerState.RUNNING:
                self._state = _SchedulerState.SHUTTING_DOWN
                self._drain = False
                self._discard_provisional()
            self._condition.notify_all()

    def _find(self, analysis_id: str) -> _QueueItem | None:
        for queue in self._queues.values():
            for item in queue:
                if item.analysis_id == analysis_id:
                    return item
        return None

    def _discard_provisional(self) -> None:
        for queue in self._queues.values():
            confirmed = [item for item in queue if item.dispatchable]
            removed = {item.analysis_id for item in queue if not item.dispatchable}
            queue.clear()
            queue.extend(confirmed)
            self._analysis_ids.difference_update(removed)
