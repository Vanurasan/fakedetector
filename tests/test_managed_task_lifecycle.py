"""Stage 4 Increment 1 managed accepted-task lifecycle tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import NoReturn

import pytest

from fakedetector.config.models import AppConfig
from fakedetector.core import AuthoritativeLifecycleClock, Clock
from fakedetector.domain import (
    AnalysisStatus,
    CleanupStatus,
    ErrorDetail,
    ImageTechnicalParameters,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.intake import (
    ControlledIntakeService,
    FileIntakeService,
    FileValidator,
    LocalTemporaryInputOwner,
    OwnedSource,
    Stage3Accepted,
    Stage3Terminal,
    TemporaryInputCleanupError,
)
from fakedetector.lifecycle import (
    AnalysisContext,
    AnalysisStateMachine,
    AnalysisTask,
    ArtifactRegistrationError,
    DeterministicTaskQueue,
    DuplicateTaskError,
    LifecycleStateError,
    MediaRouter,
    QueueStateError,
    RouteBindingError,
    Stage4LifecycleRunner,
    Stage4ReceiverError,
    Stage4TaskProcessor,
    Stage4TaskReceiver,
    TaskExecutionOutcome,
    TaskExecutor,
    TaskRegistry,
    TaskSnapshot,
    WorkspaceArtifactRegistry,
    config_snapshot_fingerprint,
)
from fakedetector.lifecycle.models import CleanupFacts

_REGISTERED = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def authoritative(clock: Clock | AuthoritativeLifecycleClock) -> AuthoritativeLifecycleClock:
    if isinstance(clock, AuthoritativeLifecycleClock):
        return clock
    existing = getattr(clock, "_authoritative_lifecycle_clock", None)
    if isinstance(existing, AuthoritativeLifecycleClock):
        return existing
    result = AuthoritativeLifecycleClock(clock)
    clock._authoritative_lifecycle_clock = result  # type: ignore[attr-defined]
    return result


class IncrementingClock:
    def __init__(self, current: datetime = _REGISTERED) -> None:
        self.current = current

    def now(self) -> datetime:
        result = self.current
        self.current += timedelta(seconds=1)
        return result


class TerminalFailureClock:
    def __init__(self, current: datetime = _REGISTERED) -> None:
        self.current = current
        self._fail_next = False

    def fail_next(self) -> None:
        self._fail_next = True

    def now(self) -> datetime:
        if self._fail_next:
            self._fail_next = False
            raise RuntimeError("PRIVATE CLOCK PATH C:\\clock\\source")
        result = self.current
        self.current += timedelta(seconds=1)
        return result


class SequenceClock:
    def __init__(self, *timestamps: datetime) -> None:
        self._timestamps = list(timestamps)

    def now(self) -> datetime:
        if not self._timestamps:
            raise AssertionError("clock exhausted")
        return self._timestamps.pop(0)


class TerminalFailureOwner(LocalTemporaryInputOwner):
    def __init__(self, root_path: Path, clock: TerminalFailureClock) -> None:
        super().__init__(root_path)
        self._clock = clock
        self.cleanup_calls = 0

    def cleanup(self, owned_source: OwnedSource) -> None:
        self.cleanup_calls += 1
        super().cleanup(owned_source)
        self._clock.fail_next()


class SequenceIdGenerator:
    def __init__(self, *analysis_ids: str) -> None:
        self._analysis_ids = iter(analysis_ids)

    def generate(self) -> str:
        return next(self._analysis_ids)


class RecordingExecutor:
    def __init__(self, *, fail: bool = False, raise_error: bool = False) -> None:
        self.fail = fail
        self.raise_error = raise_error
        self.calls: list[str] = []

    def execute(self, task: AnalysisTask) -> TaskExecutionOutcome:
        self.calls.append(task.context.analysis_id)
        if self.raise_error:
            raise RuntimeError("PRIVATE EXECUTOR PATH C:\\secret\\source")
        if self.fail:
            return TaskExecutionOutcome.failed(safe_execution_error())
        return TaskExecutionOutcome.completed()


class FailingQueue(DeterministicTaskQueue):
    def enqueue(self, task: AnalysisTask, executor: TaskExecutor) -> NoReturn:
        super().enqueue(task, executor)
        raise QueueStateError()


def make_config(root: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {},
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {"root_path": str(root)},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {},
            "error_handling": {},
            "logging": {},
            "external_systems": {},
        }
    )


def source_context() -> SourceContext:
    return SourceContext(
        channel=SourceChannel.API,
        connector="mail_connector",
        external_system="mail_gateway",
        external_reference="message-42",
    )


def safe_execution_error() -> ErrorDetail:
    return ErrorDetail(
        code="internal_error",
        category="internal",
        message="Задача анализа не выполнена.",
        retryable=True,
    )


def image_descriptor(analysis_id: str) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name=f"{analysis_id}.png",
        extension="png",
        declared_mime_type="image/png",
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=1,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=ImageTechnicalParameters(
            width=1,
            height=1,
            format="PNG",
            color_mode="RGB",
            has_metadata=False,
        ),
    )


def make_stage3_service(
    *,
    config: AppConfig,
    clock: Clock,
    id_generator: SequenceIdGenerator,
    receiver: Stage4TaskReceiver,
    owner: LocalTemporaryInputOwner,
) -> FileIntakeService:
    shared_clock = authoritative(clock)
    controlled_intake = ControlledIntakeService(
        config=config,
        analysis_id_generator=id_generator,
        clock=shared_clock,
        temporary_input_owner=owner,
    )
    return FileIntakeService(
        controlled_intake=controlled_intake,
        validator=FileValidator(config=config, temporary_input_owner=owner),
        temporary_input_owner=owner,
        accepted_receiver=receiver,
        clock=shared_clock,
    )


def make_stage4(
    *,
    config: AppConfig,
    clock: Clock,
    executor: RecordingExecutor,
    bindings: dict[MediaType, RecordingExecutor] | None = None,
    queue: DeterministicTaskQueue | None = None,
) -> tuple[Stage4TaskReceiver, Stage4LifecycleRunner, TaskRegistry, DeterministicTaskQueue]:
    shared_clock = authoritative(clock)
    registry = TaskRegistry()
    actual_queue = queue if queue is not None else DeterministicTaskQueue()
    routes = bindings or dict.fromkeys(MediaType, executor)
    receiver = Stage4TaskReceiver(
        config=config,
        clock=shared_clock,
        registry=registry,
        router=MediaRouter(routes),
        queue=actual_queue,
    )
    runner = Stage4LifecycleRunner(
        config=config,
        clock=shared_clock,
        registry=registry,
        queue=actual_queue,
    )
    return receiver, runner, registry, actual_queue


def process_png(
    service: FileIntakeService,
    media_files: dict[str, Path],
    *,
    original_name: str = "sample.png",
) -> Stage3Accepted | Stage3Terminal:
    return service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name=original_name,
        declared_content_type="image/png",
        source=source_context(),
    )


def move_task_to_queue_boundary(registry: TaskRegistry, analysis_id: str) -> None:
    registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.ROUTING,
    )
    registry.bind_route(analysis_id, MediaType.IMAGE)
    registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.QUEUED,
    )


def make_registered_task(
    root: Path,
    analysis_id: str,
) -> tuple[AnalysisTask, TaskRegistry, LocalTemporaryInputOwner]:
    owner = LocalTemporaryInputOwner(root)
    owned_source = owner.create(analysis_id)
    owner.ingest(owned_source, BytesIO(b"x"), 1)
    accepted_source = owner.transfer(owned_source)
    validated_file = image_descriptor(analysis_id)
    validation = ValidationResult(
        accepted=True,
        checks=[],
        errors=[],
        validated_file=validated_file,
    )
    task = AnalysisTask(
        context=AnalysisContext(
            analysis_id=analysis_id,
            created_at=_REGISTERED,
            status=AnalysisStatus.QUEUED,
            stage=ProcessingStage.REGISTERED,
            source=source_context(),
            workspace_path=root / analysis_id,
            media_type=MediaType.IMAGE,
            config_snapshot_id="a" * 64,
        ),
        validation=validation,
        validated_file=validated_file,
        accepted_source=accepted_source,
        artifacts=WorkspaceArtifactRegistry(root / analysis_id),
    )
    registry = TaskRegistry()
    registry.reserve(task)
    return task, registry, owner


def fact_ready_settlement(registry: TaskRegistry, analysis_id: str) -> object:
    _task, owner_token = registry.claim_terminal_settlement(analysis_id)
    registry.start_terminal_cleanup(analysis_id, owner_token)
    registry.record_cleanup_progress(
        analysis_id,
        owner_token,
        original_file_deleted=True,
        intermediate_files_deleted=True,
        attempt_completed=True,
        quarantine_decided=True,
    )
    registry.mark_terminal_facts_ready(
        analysis_id,
        owner_token,
        CleanupFacts(
            status=CleanupStatus.COMPLETED,
            original_file_deleted=True,
            intermediate_files_deleted=True,
            quarantine_used=False,
            errors=(),
        ),
    )
    return owner_token


@pytest.fixture
def accepted_task(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> Iterator[tuple[AnalysisTask, TaskRegistry, RecordingExecutor]]:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    receiver, _runner, registry, _queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("unit-task"),
        receiver=receiver,
        owner=owner,
    )
    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)
    task = registry._tasks[accepted.analysis_id]
    yield task, registry, executor
    if not accepted.controlled_source.is_released:
        accepted.controlled_source.cleanup()


def test_config_snapshot_fingerprint_is_stable_full_digest_and_sensitive(tmp_path: Path) -> None:
    config = make_config(tmp_path / "temp")
    same_config = AppConfig.model_validate(config.model_dump(mode="json"))
    changed = config.model_copy(deep=True)
    changed.server.port += 1

    fingerprint = config_snapshot_fingerprint(config)

    assert len(fingerprint) == 64
    assert fingerprint == config_snapshot_fingerprint(same_config)
    assert fingerprint != config_snapshot_fingerprint(changed)
    assert "MEDIA_ANALYZER_API_TOKEN" not in fingerprint


def test_config_snapshot_capture_revalidates_mutated_app_config(tmp_path: Path) -> None:
    config = make_config(tmp_path / "temp")
    config.limits.__dict__["processing_timeout_seconds"] = 0

    with pytest.raises(ValueError):
        config_snapshot_fingerprint(config)


def test_context_and_task_snapshot_are_truthful_safe_and_read_only(
    accepted_task: tuple[AnalysisTask, TaskRegistry, RecordingExecutor],
    tmp_path: Path,
) -> None:
    task, registry, _executor = accepted_task
    snapshot = registry.snapshot(task.context.analysis_id)

    assert task.context.status is AnalysisStatus.QUEUED
    assert task.context.stage is ProcessingStage.QUEUED
    assert task.context.media_type is MediaType.IMAGE
    assert task.context.started_at is None
    assert task.context.finished_at is None
    assert task.stage5_data is None
    assert snapshot.queued_at is not None
    assert snapshot.route is MediaType.IMAGE
    assert "accepted_source" not in {item.name for item in fields(TaskSnapshot)}
    assert "stage5_data" not in {item.name for item in fields(TaskSnapshot)}
    assert "workspace_path" not in {item.name for item in fields(TaskSnapshot)}
    assert str(tmp_path) not in repr(snapshot)
    with pytest.raises(FrozenInstanceError):
        snapshot.status = AnalysisStatus.FAILED  # type: ignore[misc]


def test_analysis_context_requires_utc(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="created_at"):
        AnalysisContext(
            analysis_id="context",
            created_at=datetime(2026, 8, 15, 9, 0),
            status=AnalysisStatus.QUEUED,
            stage=ProcessingStage.REGISTERED,
            source=source_context(),
            workspace_path=tmp_path,
            media_type=MediaType.IMAGE,
            config_snapshot_id="a" * 64,
        )


def test_state_machine_rejects_reverse_skip_duplicate_finish_and_terminal_restart(
    accepted_task: tuple[AnalysisTask, TaskRegistry, RecordingExecutor],
) -> None:
    task, registry, _executor = accepted_task
    analysis_id = task.context.analysis_id
    started_at = _REGISTERED + timedelta(minutes=1)
    registry.claim(analysis_id, started_at)

    with pytest.raises(LifecycleStateError):
        registry.claim(analysis_id, started_at)
    with pytest.raises(LifecycleStateError):
        registry.transition(
            analysis_id,
            status=AnalysisStatus.QUEUED,
            stage=ProcessingStage.ROUTING,
        )

    registry.record_outcome(analysis_id, TaskExecutionOutcome.completed())
    with pytest.raises(LifecycleStateError):
        registry.transition(
            analysis_id,
            status=AnalysisStatus.RUNNING,
            stage=ProcessingStage.PREPROCESSING,
            started_at=started_at,
        )
    owner_token = fact_ready_settlement(registry, analysis_id)
    registry.finalize_terminal_settlement(
        analysis_id,
        owner_token,
        started_at + timedelta(seconds=1),
    )
    with pytest.raises(LifecycleStateError):
        registry.finalize_terminal_settlement(
            analysis_id,
            owner_token,
            started_at + timedelta(seconds=1),
        )
    with pytest.raises(QueueStateError):
        DeterministicTaskQueue().enqueue(task, RecordingExecutor())


def test_registry_atomically_records_terminal_cleanup_and_rejects_duplicates(
    accepted_task: tuple[AnalysisTask, TaskRegistry, RecordingExecutor],
) -> None:
    task, registry, _executor = accepted_task
    analysis_id = task.context.analysis_id
    finished_at = _REGISTERED + timedelta(minutes=1)
    started_at = task.queued_at
    assert started_at is not None
    registry.claim(analysis_id, started_at)
    registry.record_outcome(analysis_id, TaskExecutionOutcome.completed())
    owner_token = fact_ready_settlement(registry, analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.finalize_terminal_settlement(
            analysis_id,
            object(),
            finished_at,
        )

    unchanged = registry.snapshot(analysis_id)
    assert unchanged.stage is ProcessingStage.CLEANUP
    assert unchanged.cleanup is None
    assert unchanged.finished_at is None
    assert registry.is_active(analysis_id)

    registry.finalize_terminal_settlement(analysis_id, owner_token, finished_at)

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.finished_at == finished_at
    assert snapshot.cleanup is not None
    assert snapshot.cleanup.finished_at == finished_at
    assert not registry.is_active(analysis_id)
    with pytest.raises(LifecycleStateError):
        registry.finalize_terminal_settlement(analysis_id, owner_token, finished_at)
    assert registry.snapshot(analysis_id) == snapshot


def test_terminal_settlement_claim_is_cleanup_only_and_has_one_owner(tmp_path: Path) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "settlement-claim", "claim")

    with pytest.raises(LifecycleStateError):
        registry.claim_terminal_settlement(task.context.analysis_id)

    move_task_to_queue_boundary(registry, task.context.analysis_id)
    registry.mark_enqueued(task.context.analysis_id, _REGISTERED)
    registry.fail_pending(task.context.analysis_id, safe_execution_error())
    _claimed, owner_token = registry.claim_terminal_settlement(task.context.analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.claim_terminal_settlement(task.context.analysis_id)
    assert owner_token is not None


def test_registry_generic_transition_cannot_publish_finished_without_cleanup(
    tmp_path: Path,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "finish-bypass", "bypass")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)
    registry.claim(analysis_id, _REGISTERED)
    registry.record_outcome(analysis_id, TaskExecutionOutcome.completed())

    with pytest.raises(LifecycleStateError):
        registry.transition(
            analysis_id,
            status=AnalysisStatus.COMPLETED,
            stage=ProcessingStage.FINISHED,
            finished_at=_REGISTERED,
        )

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.stage is ProcessingStage.CLEANUP
    assert snapshot.cleanup is None
    assert snapshot.finished_at is None


def test_terminal_settlement_progress_survives_reentry_and_fact_ready_is_immutable(
    tmp_path: Path,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "settlement-progress", "progress")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)
    registry.fail_pending(analysis_id, safe_execution_error())
    _claimed, owner_token = registry.claim_terminal_settlement(analysis_id)
    registry.start_terminal_cleanup(analysis_id, owner_token)
    registry.record_cleanup_progress(
        analysis_id,
        owner_token,
        original_file_deleted=False,
        artifact_cleanup_completed=True,
        intermediate_files_deleted=False,
        attempt_completed=True,
        quarantine_decided=True,
    )
    registry.release_terminal_settlement(analysis_id, owner_token)

    _reclaimed, recovery_token = registry.claim_terminal_settlement(analysis_id)
    recovered = registry.terminal_settlement(analysis_id, recovery_token)
    assert recovered.artifact_cleanup_completed
    assert recovered.attempts_completed == 1
    facts = CleanupFacts(
        status=CleanupStatus.FAILED,
        original_file_deleted=False,
        intermediate_files_deleted=False,
        quarantine_used=False,
        errors=(safe_execution_error(),),
    )
    registry.mark_terminal_facts_ready(analysis_id, recovery_token, facts)

    with pytest.raises(LifecycleStateError):
        registry.start_terminal_cleanup(analysis_id, recovery_token)
    with pytest.raises(LifecycleStateError):
        registry.record_cleanup_progress(
            analysis_id,
            recovery_token,
            original_file_deleted=False,
            intermediate_files_deleted=False,
        )


def test_fact_ready_invalid_commit_preserves_facts_and_processor_recovery_skips_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "settlement-recovery"
    task, registry, _owner = make_registered_task(root, "recovery")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)
    registry.fail_pending(analysis_id, safe_execution_error())
    owner_token = fact_ready_settlement(registry, analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.finalize_terminal_settlement(
            analysis_id,
            owner_token,
            _REGISTERED - timedelta(seconds=1),
        )
    assert registry.terminal_settlement(analysis_id, owner_token).facts is not None
    registry.release_terminal_settlement(analysis_id, owner_token)

    config = make_config(root)
    processor = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(IncrementingClock()),
        registry=registry,
    )
    monkeypatch.setattr(
        processor._cleanup,
        "cleanup_task",
        lambda *_args, **_kwargs: pytest.fail("FACT_READY cleanup must not rerun"),
    )

    snapshot = processor.settle_terminal(analysis_id)

    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.cleanup is not None
    assert snapshot.finished_at == snapshot.cleanup.finished_at
    assert not registry.is_active(analysis_id)


@pytest.mark.parametrize(
    "queued_at",
    [
        datetime(2026, 8, 15, 9, 0),
        datetime(2026, 8, 15, 12, 0, tzinfo=timezone(timedelta(hours=3))),
    ],
)
def test_registry_rejects_invalid_queued_at_without_mutation(
    tmp_path: Path,
    queued_at: datetime,
) -> None:
    task, registry, owner = make_registered_task(tmp_path / "queue-invalid", "queue-invalid")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    before = registry.snapshot(analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.mark_enqueued(analysis_id, queued_at)

    after = registry.snapshot(analysis_id)
    assert after == before
    assert after.queued_at is None
    assert after.stage is ProcessingStage.QUEUED
    task.accepted_source.cleanup()


def test_registry_rejects_queued_at_before_created_at_without_mutation(
    tmp_path: Path,
) -> None:
    task, registry, owner = make_registered_task(tmp_path / "queue-before", "queue-before")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    before = registry.snapshot(analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.mark_enqueued(analysis_id, _REGISTERED - timedelta(seconds=1))

    assert registry.snapshot(analysis_id) == before
    task.accepted_source.cleanup()


def test_registry_accepts_equal_created_and_queued_timestamps(
    tmp_path: Path,
) -> None:
    task, registry, owner = make_registered_task(tmp_path / "queue-equal", "queue-equal")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)

    registry.mark_enqueued(analysis_id, task.context.created_at)

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.queued_at == task.context.created_at
    task.accepted_source.cleanup()


@pytest.mark.parametrize(
    "started_at",
    [
        datetime(2026, 8, 15, 9, 1),
        datetime(2026, 8, 15, 12, 1, tzinfo=timezone(timedelta(hours=3))),
    ],
)
def test_registry_rejects_invalid_started_at_without_mutation(
    tmp_path: Path,
    started_at: datetime,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "start-invalid", "start-invalid")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)
    before = registry.snapshot(analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.claim(analysis_id, started_at)

    after = registry.snapshot(analysis_id)
    assert after == before
    assert after.started_at is None
    assert task.execution_claimed is False


@pytest.mark.parametrize(
    "started_at",
    [
        _REGISTERED - timedelta(seconds=1),
        _REGISTERED + timedelta(seconds=1),
    ],
)
def test_registry_rejects_started_at_before_required_lower_bounds(
    tmp_path: Path,
    started_at: datetime,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "start-before", "start-before")
    analysis_id = task.context.analysis_id
    queued_at = _REGISTERED + timedelta(seconds=2)
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, queued_at)
    before = registry.snapshot(analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.claim(analysis_id, started_at)

    assert registry.snapshot(analysis_id) == before
    assert task.execution_claimed is False


def test_registry_accepts_equal_queued_and_started_timestamps(
    tmp_path: Path,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "start-equal", "start-equal")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)

    registry.claim(analysis_id, _REGISTERED)

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.started_at == _REGISTERED


def test_registry_rejects_invalid_executed_terminal_timestamp_without_mutation_and_recovers(
    tmp_path: Path,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "finish-executed", "finish-executed")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)
    registry.claim(analysis_id, _REGISTERED)
    registry.record_outcome(analysis_id, TaskExecutionOutcome.completed())
    owner_token = fact_ready_settlement(registry, analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.finalize_terminal_settlement(
            analysis_id,
            owner_token,
            _REGISTERED - timedelta(seconds=1),
        )

    unchanged = registry.snapshot(analysis_id)
    assert unchanged.stage is ProcessingStage.CLEANUP
    assert unchanged.cleanup is None
    assert unchanged.finished_at is None

    registry.finalize_terminal_settlement(analysis_id, owner_token, _REGISTERED)

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.finished_at == _REGISTERED
    assert snapshot.cleanup is not None
    assert snapshot.cleanup.finished_at == _REGISTERED


def test_registry_accepts_equal_started_and_finished_timestamps(
    tmp_path: Path,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "finish-equal", "finish-equal")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)
    registry.claim(analysis_id, _REGISTERED)
    registry.record_outcome(analysis_id, TaskExecutionOutcome.completed())
    owner_token = fact_ready_settlement(registry, analysis_id)
    registry.finalize_terminal_settlement(analysis_id, owner_token, _REGISTERED)

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.finished_at == _REGISTERED
    assert snapshot.cleanup is not None
    assert snapshot.cleanup.finished_at == _REGISTERED


def test_registry_rejects_invalid_never_started_terminal_timestamp_without_mutation_and_recovers(
    tmp_path: Path,
) -> None:
    task, registry, _owner = make_registered_task(tmp_path / "finish-pending", "finish-pending")
    analysis_id = task.context.analysis_id
    move_task_to_queue_boundary(registry, analysis_id)
    registry.mark_enqueued(analysis_id, _REGISTERED)
    registry.fail_pending(analysis_id, safe_execution_error())
    owner_token = fact_ready_settlement(registry, analysis_id)

    with pytest.raises(LifecycleStateError):
        registry.finalize_terminal_settlement(
            analysis_id,
            owner_token,
            _REGISTERED - timedelta(seconds=1),
        )

    unchanged = registry.snapshot(analysis_id)
    assert unchanged.stage is ProcessingStage.CLEANUP
    assert unchanged.started_at is None
    assert unchanged.cleanup is None
    assert unchanged.finished_at is None

    registry.finalize_terminal_settlement(analysis_id, owner_token, _REGISTERED)

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.status is AnalysisStatus.FAILED
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.started_at is None
    assert snapshot.cleanup is not None
    assert snapshot.cleanup.finished_at == _REGISTERED
    assert not registry.is_active(analysis_id)


def test_state_machine_rejects_prohibited_skip_without_mutation(
    accepted_task: tuple[AnalysisTask, TaskRegistry, RecordingExecutor],
) -> None:
    task, _registry, _executor = accepted_task
    initial = replace(task.context, stage=ProcessingStage.REGISTERED)
    task.context = initial

    with pytest.raises(LifecycleStateError):
        AnalysisStateMachine().transition(
            task,
            status=AnalysisStatus.RUNNING,
            stage=ProcessingStage.PREPROCESSING,
            started_at=_REGISTERED,
        )

    assert task.context is initial


def test_registry_rejects_duplicate_and_returns_detached_safe_snapshot(
    accepted_task: tuple[AnalysisTask, TaskRegistry, RecordingExecutor],
) -> None:
    task, registry, _executor = accepted_task

    with pytest.raises(DuplicateTaskError):
        registry.reserve(task)

    snapshot = registry.snapshot(task.context.analysis_id)
    task.errors.append(safe_execution_error())
    assert snapshot.errors == ()


def test_router_has_all_canonical_bindings_and_uses_only_validated_media_type(
    accepted_task: tuple[AnalysisTask, TaskRegistry, RecordingExecutor],
) -> None:
    task, _registry, _executor = accepted_task
    executors = {media_type: RecordingExecutor() for media_type in MediaType}
    router = MediaRouter(executors)

    assert router.resolve(task.validated_file) is executors[MediaType.IMAGE]
    renamed = task.validated_file.model_copy(update={"original_name": "movie.mp4"})
    assert router.resolve(renamed) is executors[MediaType.IMAGE]

    with pytest.raises(RouteBindingError):
        MediaRouter({MediaType.AUDIO: executors[MediaType.AUDIO]}).resolve(task.validated_file)


@pytest.mark.parametrize(
    ("artifact_id", "relative_path"),
    [
        ("frame", "../outside.bin"),
        ("frame", "C:\\outside.bin"),
        ("user/name", "frames/001.png"),
        ("frame", "CON"),
        ("frame", "con.png"),
        ("frame", "nested/AUX.txt"),
        ("frame", "COM1.bin"),
        ("frame", "lpt9.log"),
        ("frame", "output./child.png"),
        ("frame", "output /child.png"),
        ("frame", "nested/output."),
        ("frame", "nested/output "),
        ("frame", "output:stream"),
        ("frame", "nested/../outside.bin"),
        ("frame", "output\u00e9.png"),
    ],
)
def test_artifact_registry_rejects_user_controlled_paths(
    tmp_path: Path,
    artifact_id: str,
    relative_path: str,
) -> None:
    registry = WorkspaceArtifactRegistry(tmp_path / "workspace")
    with pytest.raises(ArtifactRegistrationError):
        registry.register(artifact_id, relative_path)
    assert registry.cleanup_obligations() == ()
    assert not (tmp_path / "workspace").exists()


@pytest.mark.parametrize(
    ("original", "alias"),
    [
        ("output", "output."),
        ("output", "output "),
        ("output", "OUTPUT"),
        ("Frames/Output.png", "frames/output.PNG"),
        ("Frames/Output.png", "FRAMES/Output.png"),
    ],
)
def test_artifact_registry_rejects_windows_alias_before_write(
    tmp_path: Path, original: str, alias: str
) -> None:
    workspace = tmp_path / "workspace"
    registry = WorkspaceArtifactRegistry(workspace)
    original_ref = registry.register("original", original)

    with pytest.raises(ArtifactRegistrationError):
        alias_ref = registry.register("alias", alias)
        registry.with_local_artifact_path(alias_ref, lambda path: path.write_bytes(b"alias"))

    assert registry.cleanup_obligations() == (workspace / original,)
    assert not workspace.exists()
    assert (
        registry.with_local_artifact_path(original_ref, lambda path: path) == workspace / original
    )
    # A rejected target must not consume the ID or create a cleanup obligation.
    registry.register("alias", "distinct.png")
    assert registry.cleanup_once().completed


def test_artifact_registry_allows_distinct_siblings_and_nested_paths(tmp_path: Path) -> None:
    registry = WorkspaceArtifactRegistry(tmp_path)
    relative_paths = (
        "output",
        "output.png",
        "outputs/one.png",
        "outputs/two.png",
        "outputs/deep/x.png",
    )
    refs = [
        registry.register(f"artifact_{index}", path) for index, path in enumerate(relative_paths)
    ]
    assert registry.cleanup_obligations() == tuple(tmp_path / path for path in relative_paths)
    assert list(tmp_path.iterdir()) == []

    def write(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(path.name.encode("ascii"))

    for ref in refs:
        registry.with_local_artifact_path(ref, write)
    for ref, relative_path in zip(refs, relative_paths, strict=True):
        assert registry.with_local_artifact_path(ref, lambda path: path.read_bytes()) == Path(
            relative_path
        ).name.encode("ascii")
    assert registry.cleanup_once().completed
    assert list(tmp_path.iterdir()) == []


def test_artifact_registry_tracks_and_cleans_application_obligations(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    artifact = workspace / "frames" / "001.png"
    workspace.mkdir()
    registry = WorkspaceArtifactRegistry(workspace)
    artifact_ref = registry.register("frame_001", "frames/001.png")

    assert not artifact.exists()

    def create_artifact(path: Path) -> None:
        path.parent.mkdir()
        path.write_bytes(b"generated")

    registry.with_local_artifact_path(artifact_ref, create_artifact)

    assert registry.cleanup_obligations() == (artifact,)
    assert registry.cleanup_once().completed
    assert not artifact.exists()


def test_artifact_registry_rejects_foreign_ref_and_duplicate_target(tmp_path: Path) -> None:
    first = WorkspaceArtifactRegistry(tmp_path / "first")
    second = WorkspaceArtifactRegistry(tmp_path / "second")
    artifact_ref = first.register("frame_001", "frames/001.png")

    with pytest.raises(ArtifactRegistrationError):
        second.with_local_artifact_path(artifact_ref, lambda path: path)
    with pytest.raises(ArtifactRegistrationError):
        first.register("frame_002", "frames/001.png")


def test_completed_or_missing_artifact_obligation_cannot_reopen(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry = WorkspaceArtifactRegistry(workspace)
    artifact_ref = registry.register("missing_artifact", "missing.bin")

    assert registry.cleanup_once().completed
    assert registry.cleanup_obligations() == (workspace / "missing.bin",)
    with pytest.raises(ArtifactRegistrationError):
        registry.with_local_artifact_path(artifact_ref, lambda path: path)


def test_artifact_obligation_survives_failure_during_physical_creation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "partial.bin"
    registry = WorkspaceArtifactRegistry(workspace)
    artifact_ref = registry.register("partial_artifact", "partial.bin")

    def fail_after_partial_create(path: Path) -> NoReturn:
        path.write_bytes(b"partial")
        raise OSError("creation failed")

    with pytest.raises(OSError, match="creation failed"):
        registry.with_local_artifact_path(artifact_ref, fail_after_partial_create)

    assert registry.cleanup_obligations() == (artifact,)
    assert registry.cleanup_once().completed
    assert not artifact.exists()


def test_preconfirmation_missing_route_rolls_back_and_stage3_cleans(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    receiver, _runner, registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
        bindings={MediaType.AUDIO: executor, MediaType.VIDEO: executor},
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("missing-route"),
        receiver=receiver,
        owner=owner,
    )

    outcome = process_png(service, media_files)

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert outcome.errors[0].code == "internal_error"
    assert not registry.contains(outcome.analysis_id)
    assert len(queue) == 0
    assert not (root / outcome.analysis_id).exists()


def test_preconfirmation_enqueue_failure_rolls_back_and_stage3_cleans(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    failing_queue = FailingQueue()
    receiver, _runner, registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
        queue=failing_queue,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("enqueue-failure"),
        receiver=receiver,
        owner=owner,
    )

    outcome = process_png(service, media_files)

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert not registry.contains(outcome.analysis_id)
    assert len(queue) == 0
    assert not (root / outcome.analysis_id).exists()


def test_regressing_raw_queued_sample_uses_shared_authoritative_domain(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    queued_at = _REGISTERED - timedelta(days=1)
    clock = SequenceClock(_REGISTERED, queued_at)
    executor = RecordingExecutor()
    receiver, _runner, registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("invalid-queued-at"),
        receiver=receiver,
        owner=owner,
    )
    outcome = process_png(service, media_files)

    assert isinstance(outcome, Stage3Accepted)
    snapshot = registry.snapshot("invalid-queued-at")
    assert snapshot.queued_at is not None
    assert snapshot.queued_at >= snapshot.created_at
    assert len(queue) == 1
    queue.remove(outcome.analysis_id)
    outcome.controlled_source.cleanup()
    assert len(queue) == 0
    assert not (root / outcome.analysis_id).exists()


def test_duplicate_reservation_keeps_existing_authoritative_task_and_cleans_second_source(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    receiver, _runner, registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    first_owner = LocalTemporaryInputOwner(root)
    first_service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("duplicate-task"),
        receiver=receiver,
        owner=first_owner,
    )
    first = process_png(first_service, media_files)
    assert isinstance(first, Stage3Accepted)
    existing_snapshot = registry.snapshot(first.analysis_id)
    first.controlled_source.cleanup()

    second_owner = LocalTemporaryInputOwner(root)
    second_service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("duplicate-task"),
        receiver=receiver,
        owner=second_owner,
    )
    second = process_png(second_service, media_files)

    assert isinstance(second, Stage3Terminal)
    assert second.status is AnalysisStatus.FAILED
    assert second.cleanup is not None
    assert second.cleanup.status is CleanupStatus.COMPLETED
    assert registry.snapshot("duplicate-task") == existing_snapshot
    assert len(queue) == 1
    assert not (root / "duplicate-task").exists()


def test_receiver_identity_mismatch_is_safe_typed_and_keeps_stage3_ownership(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    receiver, _runner, registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("identity-source"),
        receiver=receiver,
        owner=owner,
    )
    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)
    registry.rollback(accepted.analysis_id)
    queue.remove(accepted.analysis_id)

    mismatched = replace(accepted, analysis_id="other-analysis")
    with pytest.raises(Stage4ReceiverError) as exc_info:
        receiver.accept(mismatched)

    assert str(tmp_path) not in str(exc_info.value)
    assert not registry.contains("other-analysis")
    assert not accepted.controlled_source.is_released
    accepted.controlled_source.cleanup()


def test_confirmed_queue_preserves_source_until_run_then_completes_and_cleans(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    receiver, runner, registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("success-png"),
        receiver=receiver,
        owner=owner,
    )

    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)
    workspace = root / accepted.analysis_id
    queued = registry.snapshot(accepted.analysis_id)

    assert len(queue) == 1
    assert queued.analysis_id == accepted.analysis_id
    assert queued.created_at == accepted.registered_at
    assert queued.media_type is accepted.validated_file.media_type is MediaType.IMAGE
    assert queued.status is AnalysisStatus.QUEUED
    assert queued.stage is ProcessingStage.QUEUED
    assert queued.queued_at is not None
    assert queued.started_at is None
    assert queued.finished_at is None
    assert workspace.exists()
    assert not accepted.controlled_source.is_released

    finished = runner.run_next()

    assert finished is not None
    assert finished.status is AnalysisStatus.COMPLETED
    assert finished.stage is ProcessingStage.FINISHED
    assert finished.started_at is not None
    assert finished.finished_at == _REGISTERED + timedelta(seconds=3)
    assert finished.cleanup is not None
    assert finished.cleanup.status is CleanupStatus.COMPLETED
    assert finished.cleanup.finished_at == finished.finished_at
    assert accepted.controlled_source.is_released
    assert not workspace.exists()
    assert executor.calls == [accepted.analysis_id]
    assert runner.run_next() is None


@pytest.mark.parametrize(
    ("raise_error", "expected_status"),
    [
        (False, AnalysisStatus.COMPLETED),
        (True, AnalysisStatus.FAILED),
    ],
)
def test_runner_terminal_clock_failure_uses_authoritative_monotonic_degradation(
    tmp_path: Path,
    media_files: dict[str, Path],
    raise_error: bool,
    expected_status: AnalysisStatus,
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = TerminalFailureClock()
    executor = RecordingExecutor(raise_error=raise_error)
    receiver, runner, registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = TerminalFailureOwner(root, clock)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator(f"terminal-clock-{expected_status.value}"),
        receiver=receiver,
        owner=owner,
    )
    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)
    workspace = root / accepted.analysis_id

    finished = runner.run_next()

    assert finished is not None
    assert finished.status is expected_status
    assert finished.stage is ProcessingStage.FINISHED
    assert finished.started_at is not None
    assert finished.finished_at is not None
    assert finished.finished_at >= finished.started_at
    assert finished.cleanup is not None
    assert finished.cleanup.status is CleanupStatus.COMPLETED
    assert finished.cleanup.finished_at == finished.finished_at
    assert owner.cleanup_calls == 1
    assert accepted.controlled_source.is_released
    assert not workspace.exists()
    assert not registry.is_active(accepted.analysis_id)
    assert len(queue) == 0
    assert executor.calls == [accepted.analysis_id]
    assert "PRIVATE CLOCK" not in repr(finished)


@pytest.mark.parametrize(
    "terminal_sample",
    [
        RuntimeError("terminal raw failure"),
        datetime(2026, 8, 15, 9, 0, 3),
        datetime(2026, 8, 15, 12, 0, 3, tzinfo=timezone(timedelta(hours=3))),
        _REGISTERED - timedelta(seconds=1),
    ],
)
@pytest.mark.parametrize(
    ("raise_error", "expected_status"),
    [(False, AnalysisStatus.COMPLETED), (True, AnalysisStatus.FAILED)],
)
def test_runner_invalid_terminal_raw_samples_degrade_without_stranding(
    tmp_path: Path,
    media_files: dict[str, Path],
    terminal_sample: object,
    raise_error: bool,
    expected_status: AnalysisStatus,
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = SequenceClock(
        _REGISTERED,
        _REGISTERED + timedelta(seconds=1),
        _REGISTERED + timedelta(seconds=2),
        terminal_sample,  # type: ignore[arg-type]
    )
    executor = RecordingExecutor(raise_error=raise_error)
    receiver, runner, registry, _queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator(f"terminal-matrix-{expected_status.value}"),
        receiver=receiver,
        owner=owner,
    )
    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)

    finished = runner.run_next()

    assert finished is not None
    assert finished.status is expected_status
    assert finished.stage is ProcessingStage.FINISHED
    assert finished.started_at is not None
    assert finished.finished_at is not None
    assert finished.finished_at >= finished.started_at
    assert finished.cleanup is not None
    assert finished.cleanup.finished_at == finished.finished_at
    assert accepted.controlled_source.is_released
    assert not registry.is_active(accepted.analysis_id)


def test_terminal_clock_fault_after_quarantine_preserves_factual_outcome(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = SequenceClock(
        _REGISTERED,
        _REGISTERED + timedelta(seconds=1),
        _REGISTERED + timedelta(seconds=2),
        _REGISTERED + timedelta(seconds=3),
        datetime(2026, 8, 15, 9, 0, 4),
    )
    executor = RecordingExecutor()
    receiver, runner, registry, _queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("a" * 32),
        receiver=receiver,
        owner=owner,
    )
    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)
    cleanup_calls = 0

    def fail_cleanup(_source: OwnedSource) -> NoReturn:
        nonlocal cleanup_calls
        cleanup_calls += 1
        raise TemporaryInputCleanupError()

    monkeypatch.setattr(owner, "cleanup", fail_cleanup)

    finished = runner.run_next()

    assert finished is not None
    assert finished.status is AnalysisStatus.COMPLETED
    assert finished.stage is ProcessingStage.FINISHED
    assert finished.cleanup is not None
    assert finished.cleanup.status is CleanupStatus.FAILED
    assert finished.cleanup.quarantine_used
    assert finished.cleanup.finished_at == finished.finished_at
    assert cleanup_calls == 1 + config.temporary_storage.cleanup_retries
    assert not registry.is_active(accepted.analysis_id)


def test_executor_exception_becomes_safe_failed_and_cleanup_runs_exactly_once(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor(raise_error=True)
    receiver, runner, registry, _queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("failed-png"),
        receiver=receiver,
        owner=owner,
    )
    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)
    cleanup_calls = 0
    real_cleanup = owner.cleanup

    def tracking_cleanup(owned_source: OwnedSource) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1
        real_cleanup(owned_source)

    monkeypatch.setattr(owner, "cleanup", tracking_cleanup)

    finished = runner.run_next()

    assert finished is not None
    assert finished.status is AnalysisStatus.FAILED
    assert finished.stage is ProcessingStage.FINISHED
    assert finished.cleanup is not None
    assert finished.cleanup.status is CleanupStatus.COMPLETED
    assert cleanup_calls == 1
    assert finished.errors[0].code == "internal_error"
    assert "PRIVATE" not in repr(finished)
    assert str(tmp_path) not in repr(finished)
    assert registry.snapshot(accepted.analysis_id) == finished


def test_cleanup_failure_preserves_completed_primary_status_and_uses_configured_retries(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    receiver, runner, _registry, _queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("cleanup-failure"),
        receiver=receiver,
        owner=owner,
    )
    accepted = process_png(service, media_files)
    assert isinstance(accepted, Stage3Accepted)
    cleanup_calls = 0

    def fail_cleanup(_owned_source: OwnedSource) -> NoReturn:
        nonlocal cleanup_calls
        cleanup_calls += 1
        raise TemporaryInputCleanupError()

    monkeypatch.setattr(owner, "cleanup", fail_cleanup)

    finished = runner.run_next()

    assert finished is not None
    assert finished.status is AnalysisStatus.COMPLETED
    assert finished.stage is ProcessingStage.FINISHED
    assert finished.cleanup is not None
    assert finished.cleanup.status is CleanupStatus.FAILED
    assert finished.cleanup.errors[0].code == "cleanup_failed"
    assert cleanup_calls == 1 + config.temporary_storage.cleanup_retries
    assert not finished.cleanup.quarantine_used


def test_fifo_run_next_is_deterministic_for_two_confirmed_tasks(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    root = tmp_path / "temp"
    config = make_config(root)
    clock = IncrementingClock()
    executor = RecordingExecutor()
    receiver, runner, _registry, queue = make_stage4(
        config=config,
        clock=clock,
        executor=executor,
    )
    owner = LocalTemporaryInputOwner(root)
    service = make_stage3_service(
        config=config,
        clock=clock,
        id_generator=SequenceIdGenerator("fifo-first", "fifo-second"),
        receiver=receiver,
        owner=owner,
    )

    first = process_png(service, media_files, original_name="first.png")
    second = process_png(service, media_files, original_name="second.png")
    assert isinstance(first, Stage3Accepted)
    assert isinstance(second, Stage3Accepted)
    assert len(queue) == 2

    first_snapshot = runner.run_next()
    second_snapshot = runner.run_next()

    assert first_snapshot is not None and first_snapshot.analysis_id == "fifo-first"
    assert second_snapshot is not None and second_snapshot.analysis_id == "fifo-second"
    assert executor.calls == ["fifo-first", "fifo-second"]


def test_execution_outcome_rejects_non_terminal_and_inconsistent_values() -> None:
    with pytest.raises(ValueError):
        TaskExecutionOutcome(status=AnalysisStatus.RUNNING)
    with pytest.raises(ValueError):
        TaskExecutionOutcome(status=AnalysisStatus.COMPLETED, errors=(safe_execution_error(),))
    with pytest.raises(ValueError):
        TaskExecutionOutcome(status=AnalysisStatus.FAILED)


def test_failed_execution_outcome_keeps_cleanup_barrier_private_and_nonsemantic() -> None:
    class Barrier:
        def try_confirm_safe(self) -> bool:
            return False

    first_barrier = Barrier()
    second_barrier = Barrier()
    first = TaskExecutionOutcome.failed(
        safe_execution_error(),
        _cleanup_safety_barrier=first_barrier,
    )
    second = TaskExecutionOutcome.failed(
        safe_execution_error(),
        _cleanup_safety_barrier=second_barrier,
    )

    assert first == second
    assert "Barrier" not in repr(first)
    assert "cleanup_safety" not in repr(first)
    with pytest.raises(ValueError):
        TaskExecutionOutcome(
            status=AnalysisStatus.COMPLETED,
            _cleanup_safety_barrier=first_barrier,
        )
