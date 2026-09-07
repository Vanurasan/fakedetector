"""State, registry, canonical routing, and deterministic FIFO execution."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Protocol, TypeVar

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.analyzers._transport import _serialize_stage5_analyzer_result
from fakedetector.domain import (
    AnalysisStatus,
    AnalyzerResult,
    CleanupResult,
    ErrorDetail,
    MediaType,
    ProcessingStage,
    ValidatedFileDescriptor,
)
from fakedetector.domain.models import validate_utc_datetime
from fakedetector.lifecycle.models import (
    AnalysisTask,
    CleanupFacts,
    Stage5TaskData,
    TaskExecutionOutcome,
    TaskSnapshot,
    TerminalSettlement,
    TerminalSettlementPhase,
    TerminalSettlementSnapshot,
    _StoredAnalyzerResult,
)
from fakedetector.preprocessing._models import PreparedMedia

_CleanupOutcome = TypeVar("_CleanupOutcome")


class LifecycleStateError(Exception):
    """Safe invalid task lifecycle transition."""

    def __init__(self) -> None:
        super().__init__("Task lifecycle transition is invalid.")


class TimestampValidationError(LifecycleStateError):
    """Safe internal rejection for authoritative timestamp form or chronology."""


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
    """Validate and apply canonical managed lifecycle status/stage transitions."""

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
            (AnalysisStatus.RUNNING, ProcessingStage.ANALYSIS),
            (AnalysisStatus.COMPLETED, ProcessingStage.CLEANUP),
            (AnalysisStatus.FAILED, ProcessingStage.CLEANUP),
        },
        (AnalysisStatus.RUNNING, ProcessingStage.ANALYSIS): {
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
        """Claim inactive cleanup, run it unlocked, then release the reservation."""
        with self._lock:
            if analysis_id in self._cleanup_claims:
                return None
            task = self._tasks.get(analysis_id)
            if task is not None and task.context.stage is not ProcessingStage.FINISHED:
                return None
            self._cleanup_claims.add(analysis_id)

        try:
            return cleanup(task)
        finally:
            with self._lock:
                self._cleanup_claims.remove(analysis_id)

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
            if stage is ProcessingStage.FINISHED:
                raise LifecycleStateError()
            task = self._get(analysis_id)
            if stage is ProcessingStage.ANALYSIS and task.stage5_data is None:
                raise LifecycleStateError()
            self._state_machine.transition(
                task,
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
            self._validate_queued_at(task, queued_at)
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
            self._validate_started_at(task, started_at)
            self._state_machine.transition(
                task,
                status=AnalysisStatus.RUNNING,
                stage=ProcessingStage.PREPROCESSING,
                started_at=started_at,
            )
            task.execution_claimed = True
            return task

    def validate_stage5_execution(self, task: AnalysisTask) -> None:
        """Reject a stale or already-mutated task before Stage 5 performs work."""
        with self._lock:
            authoritative = self._require_stage5_task(task, ProcessingStage.PREPROCESSING)
            if authoritative.stage5_data is not None:
                raise LifecycleStateError()

    def publish_stage5_prepared(
        self,
        task: AnalysisTask,
        prepared_media: PreparedMedia,
    ) -> None:
        """Publish one capability-checked prepared value while still preprocessing."""
        with self._lock:
            authoritative = self._require_stage5_task(task, ProcessingStage.PREPROCESSING)
            if authoritative.stage5_data is not None:
                raise LifecycleStateError()
            if (
                not isinstance(prepared_media, PreparedMedia)
                or prepared_media.analysis_id != authoritative.context.analysis_id
                or prepared_media.media_type is not authoritative.context.media_type
                or not prepared_media.source_file_ref._references(authoritative.accepted_source)
                or any(
                    not authoritative.artifacts._matches_registered_artifact(
                        artifact.artifact_ref,
                        artifact.artifact_id,
                    )
                    for artifact in prepared_media.artifacts
                )
            ):
                raise LifecycleStateError()
            authoritative.stage5_data = Stage5TaskData(prepared_media=prepared_media)

    def start_stage5_analysis(self, task: AnalysisTask) -> None:
        """Enter analysis only after authoritative prepared data was published."""
        with self._lock:
            authoritative = self._require_stage5_task(task, ProcessingStage.PREPROCESSING)
            if authoritative.stage5_data is None:
                raise LifecycleStateError()
            self._state_machine.transition(
                authoritative,
                status=AnalysisStatus.RUNNING,
                stage=ProcessingStage.ANALYSIS,
            )

    def append_stage5_analyzer_result(
        self,
        task: AnalysisTask,
        result: AnalyzerResult,
    ) -> None:
        """Append one completed orchestration result in authoritative plan order."""
        if not isinstance(result, AnalyzerResult):
            raise LifecycleStateError()
        try:
            validated_result = AnalyzerResult.model_validate(
                result.model_dump(mode="python", warnings="error")
            )
            stored_result = _StoredAnalyzerResult(
                analyzer_id=validated_result.analyzer_id,
                media_type=validated_result.media_type,
                canonical_json=_serialize_stage5_analyzer_result(validated_result),
            )
        except (PydanticSerializationError, ValidationError, TypeError, ValueError):
            raise LifecycleStateError() from None
        with self._lock:
            authoritative = self._require_stage5_task(task, ProcessingStage.ANALYSIS)
            data = authoritative.stage5_data
            if (
                data is None
                or stored_result.media_type is not authoritative.context.media_type
                or any(
                    existing.analyzer_id == stored_result.analyzer_id
                    for existing in data.analyzer_results
                )
            ):
                raise LifecycleStateError()
            authoritative.stage5_data = Stage5TaskData(
                prepared_media=data.prepared_media,
                analyzer_results=(
                    *data.analyzer_results,
                    stored_result,
                ),
            )

    def _read_stage5_analyzer_results(self, task: AnalysisTask) -> tuple[AnalyzerResult, ...]:
        """Materialize detached canonical facts from one authoritative task, also terminal."""
        with self._lock:
            authoritative = self._get(task.context.analysis_id)
            if authoritative is not task:
                raise LifecycleStateError()
            data = authoritative.stage5_data
            results = () if data is None else data.analyzer_results
        return tuple(
            AnalyzerResult.model_validate_json(result.canonical_json) for result in results
        )

    def record_outcome(self, analysis_id: str, outcome: TaskExecutionOutcome) -> None:
        with self._lock:
            task = self._get(analysis_id)
            self._state_machine.transition(
                task,
                status=outcome.status,
                stage=ProcessingStage.CLEANUP,
            )
            task.errors.extend(error.model_copy(deep=True) for error in outcome.errors)
            if outcome._cleanup_safety_barrier is not None:
                task.terminal_settlement = TerminalSettlement(
                    phase=TerminalSettlementPhase.CLAIMED,
                    owner_token=None,
                    _cleanup_safety_barrier=outcome._cleanup_safety_barrier,
                    original_file_deleted=task.accepted_source.is_released,
                )

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

    def claim_terminal_settlement(self, analysis_id: str) -> tuple[AnalysisTask, object]:
        """Claim exclusive ownership before the first physical cleanup side effect."""
        with self._lock:
            task = self._get(analysis_id)
            if task.context.stage is not ProcessingStage.CLEANUP or task.cleanup_result is not None:
                raise LifecycleStateError()
            settlement = task.terminal_settlement
            if settlement is None:
                settlement = TerminalSettlement(
                    phase=TerminalSettlementPhase.CLAIMED,
                    owner_token=object(),
                    original_file_deleted=task.accepted_source.is_released,
                )
                task.terminal_settlement = settlement
            elif settlement.owner_token is not None:
                raise LifecycleStateError()
            else:
                settlement.owner_token = object()
            assert settlement.owner_token is not None
            return task, settlement.owner_token

    def terminal_settlement(
        self,
        analysis_id: str,
        owner_token: object,
    ) -> TerminalSettlementSnapshot:
        """Return immutable factual progress to the current settlement owner."""
        with self._lock:
            settlement = self._owned_settlement(analysis_id, owner_token)
            facts = settlement.facts
            return TerminalSettlementSnapshot(
                phase=settlement.phase,
                original_file_deleted=settlement.original_file_deleted,
                artifact_cleanup_completed=settlement.artifact_cleanup_completed,
                intermediate_files_deleted=settlement.intermediate_files_deleted,
                quarantine_used=settlement.quarantine_used,
                quarantine_decided=settlement.quarantine_decided,
                attempts_completed=settlement.attempts_completed,
                facts=(
                    None
                    if facts is None
                    else CleanupFacts(
                        status=facts.status,
                        original_file_deleted=facts.original_file_deleted,
                        intermediate_files_deleted=facts.intermediate_files_deleted,
                        quarantine_used=facts.quarantine_used,
                        errors=tuple(error.model_copy(deep=True) for error in facts.errors),
                    )
                ),
            )

    def start_terminal_cleanup(self, analysis_id: str, owner_token: object) -> None:
        """Move a fresh settlement claim into its single cleanup workflow."""
        with self._lock:
            settlement = self._owned_settlement(analysis_id, owner_token)
            if (
                settlement.phase is not TerminalSettlementPhase.CLAIMED
                or settlement._cleanup_safety_barrier is not None
            ):
                raise LifecycleStateError()
            settlement.phase = TerminalSettlementPhase.CLEANUP_IN_PROGRESS

    def _try_confirm_terminal_cleanup_safe(
        self,
        analysis_id: str,
        owner_token: object,
    ) -> bool:
        """Invoke an unresolved safety barrier without holding the registry lock."""
        with self._lock:
            settlement = self._owned_settlement(analysis_id, owner_token)
            barrier = settlement._cleanup_safety_barrier
            if barrier is None:
                return True
            if settlement.phase is not TerminalSettlementPhase.CLAIMED:
                raise LifecycleStateError()

        try:
            confirmed_safe = barrier.try_confirm_safe()
        except Exception:
            return False
        if confirmed_safe is not True:
            return False

        with self._lock:
            settlement = self._owned_settlement(analysis_id, owner_token)
            if (
                settlement.phase is not TerminalSettlementPhase.CLAIMED
                or settlement._cleanup_safety_barrier is not barrier
            ):
                raise LifecycleStateError()
            settlement._cleanup_safety_barrier = None
        return True

    def record_cleanup_progress(
        self,
        analysis_id: str,
        owner_token: object,
        *,
        original_file_deleted: bool,
        artifact_cleanup_completed: bool | None = None,
        intermediate_files_deleted: bool,
        attempt_completed: bool = False,
        quarantine_used: bool = False,
        quarantine_decided: bool | None = None,
    ) -> None:
        """Persist monotonic factual cleanup progress after physical operations."""
        with self._lock:
            settlement = self._owned_settlement(analysis_id, owner_token)
            if settlement.phase is not TerminalSettlementPhase.CLEANUP_IN_PROGRESS:
                raise LifecycleStateError()
            if (
                settlement.original_file_deleted
                and not original_file_deleted
                or (artifact_cleanup_completed is False and settlement.artifact_cleanup_completed)
                or settlement.intermediate_files_deleted
                and not intermediate_files_deleted
                or settlement.quarantine_used
                and not quarantine_used
                or quarantine_decided is False
                and settlement.quarantine_decided
            ):
                raise LifecycleStateError()
            settlement.original_file_deleted = original_file_deleted
            if artifact_cleanup_completed is not None:
                settlement.artifact_cleanup_completed = artifact_cleanup_completed
            settlement.intermediate_files_deleted = intermediate_files_deleted
            settlement.quarantine_used = quarantine_used
            if quarantine_decided is not None:
                settlement.quarantine_decided = quarantine_decided
            if attempt_completed:
                settlement.attempts_completed += 1

    def mark_terminal_facts_ready(
        self,
        analysis_id: str,
        owner_token: object,
        facts: CleanupFacts,
    ) -> None:
        """Freeze cleanup facts and permanently prohibit another physical workflow."""
        with self._lock:
            settlement = self._owned_settlement(analysis_id, owner_token)
            if settlement.phase is not TerminalSettlementPhase.CLEANUP_IN_PROGRESS:
                raise LifecycleStateError()
            if settlement.facts is not None:
                raise LifecycleStateError()
            if (
                not settlement.quarantine_decided
                or facts.original_file_deleted != settlement.original_file_deleted
                or facts.intermediate_files_deleted != settlement.intermediate_files_deleted
                or facts.quarantine_used != settlement.quarantine_used
            ):
                raise LifecycleStateError()
            settlement.facts = CleanupFacts(
                status=facts.status,
                original_file_deleted=facts.original_file_deleted,
                intermediate_files_deleted=facts.intermediate_files_deleted,
                quarantine_used=facts.quarantine_used,
                errors=tuple(error.model_copy(deep=True) for error in facts.errors),
            )
            settlement.phase = TerminalSettlementPhase.FACT_READY

    def finalize_terminal_settlement(
        self,
        analysis_id: str,
        owner_token: object,
        finished_at: datetime,
    ) -> None:
        """Atomically publish cleanup and ``FINISHED`` after all validation succeeds."""
        with self._lock:
            task = self._get(analysis_id)
            settlement = self._owned_settlement(analysis_id, owner_token)
            if settlement.phase is not TerminalSettlementPhase.FACT_READY:
                raise LifecycleStateError()
            facts = settlement.facts
            if facts is None or task.cleanup_result is not None:
                raise LifecycleStateError()
            self._validate_finished_at(task, finished_at)
            recorded_cleanup = CleanupResult(
                status=facts.status,
                original_file_deleted=facts.original_file_deleted,
                intermediate_files_deleted=facts.intermediate_files_deleted,
                quarantine_used=facts.quarantine_used,
                finished_at=finished_at,
                errors=[error.model_copy(deep=True) for error in facts.errors],
            )
            self._state_machine.transition(
                task,
                status=task.context.status,
                stage=ProcessingStage.FINISHED,
                finished_at=finished_at,
            )
            task.cleanup_result = recorded_cleanup
            task.terminal_settlement = None

    def release_terminal_settlement(self, analysis_id: str, owner_token: object) -> None:
        """Allow processor-only re-entry while preserving all settlement facts."""
        with self._lock:
            settlement = self._owned_settlement(analysis_id, owner_token)
            settlement.owner_token = None

    def recoverable_terminal_tasks(self) -> tuple[str, ...]:
        """List active cleanup settlements that currently have no processor owner."""
        with self._lock:
            return tuple(
                analysis_id
                for analysis_id, task in self._tasks.items()
                if task.context.stage is ProcessingStage.CLEANUP
                and task.terminal_settlement is not None
                and task.terminal_settlement.owner_token is None
            )

    def _owned_settlement(
        self,
        analysis_id: str,
        owner_token: object,
    ) -> TerminalSettlement:
        task = self._get(analysis_id)
        settlement = task.terminal_settlement
        if (
            task.context.stage is not ProcessingStage.CLEANUP
            or settlement is None
            or settlement.owner_token is not owner_token
        ):
            raise LifecycleStateError()
        return settlement

    def _require_stage5_task(
        self,
        task: AnalysisTask,
        stage: ProcessingStage,
    ) -> AnalysisTask:
        if not isinstance(task, AnalysisTask):
            raise LifecycleStateError()
        authoritative = self._get(task.context.analysis_id)
        if (
            authoritative is not task
            or not authoritative.execution_claimed
            or authoritative.context.status is not AnalysisStatus.RUNNING
            or authoritative.context.stage is not stage
            or authoritative.cleanup_result is not None
            or authoritative.terminal_settlement is not None
        ):
            raise LifecycleStateError()
        return authoritative

    @staticmethod
    def _validate_queued_at(task: AnalysisTask, queued_at: datetime) -> None:
        try:
            validated = validate_utc_datetime(queued_at, "queued_at")
        except ValueError:
            raise TimestampValidationError() from None
        assert validated is not None
        if validated < task.context.created_at:
            raise TimestampValidationError()

    @staticmethod
    def _validate_started_at(task: AnalysisTask, started_at: datetime) -> None:
        try:
            validated = validate_utc_datetime(started_at, "started_at")
        except ValueError:
            raise TimestampValidationError() from None
        assert validated is not None
        if task.queued_at is None:
            raise LifecycleStateError()
        if validated < task.context.created_at or validated < task.queued_at:
            raise TimestampValidationError()

    @staticmethod
    def _validate_finished_at(task: AnalysisTask, finished_at: datetime) -> None:
        try:
            validated = validate_utc_datetime(finished_at, "finished_at")
        except ValueError:
            raise TimestampValidationError() from None
        assert validated is not None
        if task.context.started_at is not None:
            if validated < task.context.started_at:
                raise TimestampValidationError()
            return
        if task.queued_at is None:
            raise LifecycleStateError()
        if validated < task.context.created_at or validated < task.queued_at:
            raise TimestampValidationError()

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
