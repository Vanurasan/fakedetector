"""Stage 4 Increment 1 managed accepted-task lifecycle tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import NoReturn

import pytest

from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalysisStatus,
    CleanupStatus,
    ErrorDetail,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
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
    Stage4TaskReceiver,
    TaskExecutionOutcome,
    TaskExecutor,
    TaskRegistry,
    TaskSnapshot,
    WorkspaceArtifactRegistry,
    config_snapshot_fingerprint,
)

_REGISTERED = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


class IncrementingClock:
    def __init__(self, current: datetime = _REGISTERED) -> None:
        self.current = current

    def now(self) -> datetime:
        result = self.current
        self.current += timedelta(seconds=1)
        return result


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


def make_stage3_service(
    *,
    config: AppConfig,
    clock: IncrementingClock,
    id_generator: SequenceIdGenerator,
    receiver: Stage4TaskReceiver,
    owner: LocalTemporaryInputOwner,
) -> FileIntakeService:
    controlled_intake = ControlledIntakeService(
        config=config,
        analysis_id_generator=id_generator,
        clock=clock,
        temporary_input_owner=owner,
    )
    return FileIntakeService(
        controlled_intake=controlled_intake,
        validator=FileValidator(config=config, temporary_input_owner=owner),
        temporary_input_owner=owner,
        accepted_receiver=receiver,
        clock=clock,
    )


def make_stage4(
    *,
    config: AppConfig,
    clock: IncrementingClock,
    executor: RecordingExecutor,
    bindings: dict[MediaType, RecordingExecutor] | None = None,
    queue: DeterministicTaskQueue | None = None,
) -> tuple[Stage4TaskReceiver, Stage4LifecycleRunner, TaskRegistry, DeterministicTaskQueue]:
    registry = TaskRegistry()
    actual_queue = queue if queue is not None else DeterministicTaskQueue()
    routes = bindings or dict.fromkeys(MediaType, executor)
    receiver = Stage4TaskReceiver(
        config=config,
        clock=clock,
        registry=registry,
        router=MediaRouter(routes),
        queue=actual_queue,
    )
    runner = Stage4LifecycleRunner(
        config=config,
        clock=clock,
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
    assert snapshot.queued_at is not None
    assert snapshot.route is MediaType.IMAGE
    assert "accepted_source" not in {item.name for item in fields(TaskSnapshot)}
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
    registry.finish(analysis_id, started_at + timedelta(seconds=1))
    with pytest.raises(LifecycleStateError):
        registry.finish(analysis_id, started_at + timedelta(seconds=2))
    with pytest.raises(QueueStateError):
        DeterministicTaskQueue().enqueue(task, RecordingExecutor())


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


def test_artifact_registry_tracks_and_cleans_application_obligations(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    artifact = workspace / "frames" / "001.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"generated")
    registry = WorkspaceArtifactRegistry(workspace)
    registry.register("frame_001", "frames/001.png")

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
    assert finished.finished_at is not None
    assert finished.cleanup is not None
    assert finished.cleanup.status is CleanupStatus.COMPLETED
    assert accepted.controlled_source.is_released
    assert not workspace.exists()
    assert executor.calls == [accepted.analysis_id]
    assert runner.run_next() is None


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
