"""Stage 4 Increment 2 bounded local execution lifecycle tests."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from threading import Barrier, Event, Lock, Thread, get_ident

import pytest

from fakedetector.config.models import AppConfig
from fakedetector.core import Clock, UtcClock
from fakedetector.domain import (
    AnalysisStatus,
    AudioTechnicalParameters,
    CleanupStatus,
    ImageTechnicalParameters,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
    VideoTechnicalParameters,
)
from fakedetector.intake import (
    ControlledIntakeService,
    FileIntakeService,
    FileValidator,
    LocalTemporaryInputOwner,
    OwnedSource,
    Stage3Accepted,
    Stage3Terminal,
)
from fakedetector.lifecycle import (
    BoundedLocalScheduler,
    DeterministicTaskQueue,
    LifecycleStateError,
    MediaRouter,
    SchedulerStateError,
    Stage4ReceiverError,
    Stage4TaskProcessor,
    Stage4TaskReceiver,
    TaskExecutionOutcome,
    TaskRegistry,
)

_REGISTERED = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


class SequenceIdGenerator:
    def __init__(self, *analysis_ids: str) -> None:
        self._analysis_ids = iter(analysis_ids)

    def generate(self) -> str:
        return next(self._analysis_ids)


class FixedClock:
    def now(self) -> datetime:
        return _REGISTERED


class TerminalFailureClock:
    def __init__(self) -> None:
        self._lock = Lock()
        self._fail_next = False

    def fail_next(self) -> None:
        with self._lock:
            self._fail_next = True

    def now(self) -> datetime:
        with self._lock:
            if self._fail_next:
                self._fail_next = False
                raise RuntimeError("PRIVATE CLOCK PATH C:\\clock\\source")
        return _REGISTERED


class CountingOwner(LocalTemporaryInputOwner):
    def __init__(self, root_path: Path) -> None:
        super().__init__(root_path)
        self._calls: Counter[str] = Counter()
        self._calls_lock = Lock()

    def cleanup(self, owned_source: OwnedSource) -> None:
        with self._calls_lock:
            self._calls[owned_source.analysis_id] += 1
        super().cleanup(owned_source)

    def cleanup_calls(self, analysis_id: str) -> int:
        with self._calls_lock:
            return self._calls[analysis_id]


class TerminalFailureOwner(CountingOwner):
    def __init__(self, root_path: Path, clock: TerminalFailureClock) -> None:
        super().__init__(root_path)
        self._clock = clock

    def cleanup(self, owned_source: OwnedSource) -> None:
        super().cleanup(owned_source)
        self._clock.fail_next()


class BlockingExecutor:
    def __init__(self, expected_running: int = 1) -> None:
        self.release = Event()
        self.expected_reached = Event()
        self._expected_running = expected_running
        self._lock = Lock()
        self.running: Counter[MediaType] = Counter()
        self.peak: Counter[MediaType] = Counter()
        self.calls: list[str] = []
        self.thread_ids: list[int] = []

    def execute(self, task) -> TaskExecutionOutcome:
        media_type = task.context.media_type
        with self._lock:
            self.calls.append(task.context.analysis_id)
            self.thread_ids.append(get_ident())
            self.running[media_type] += 1
            self.peak[media_type] = max(self.peak[media_type], self.running[media_type])
            if sum(self.running.values()) >= self._expected_running:
                self.expected_reached.set()
        assert self.release.wait(5)
        with self._lock:
            self.running[media_type] -= 1
        return TaskExecutionOutcome.completed()


class OrderedFailureExecutor:
    def __init__(self) -> None:
        self.first_started = Event()
        self.release_first = Event()
        self.calls: list[str] = []

    def execute(self, task) -> TaskExecutionOutcome:
        analysis_id = task.context.analysis_id
        self.calls.append(analysis_id)
        if analysis_id == "ordinary-a":
            self.first_started.set()
            assert self.release_first.wait(5)
            raise RuntimeError("PRIVATE C:\\source\\name.png")
        return TaskExecutionOutcome.completed()


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.called = Event()

    def execute(self, task) -> TaskExecutionOutcome:
        self.calls.append(task.context.analysis_id)
        self.called.set()
        return TaskExecutionOutcome.completed()


class TerminatingExecutor:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.calls: list[str] = []

    def execute(self, task) -> TaskExecutionOutcome:
        self.calls.append(task.context.analysis_id)
        self.started.set()
        assert self.release.wait(5)
        raise KeyboardInterrupt


class CommitGateScheduler(BoundedLocalScheduler):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.commit_entered = Event()
        self.allow_commit = Event()

    def commit(self, analysis_id: str) -> None:
        self.commit_entered.set()
        assert self.allow_commit.wait(5)
        super().commit(analysis_id)


def make_config(
    root: Path,
    *,
    image: int = 1,
    audio: int = 1,
    video: int = 1,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {
                "max_parallel_tasks": {"image": image, "audio": audio, "video": video}
            },
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


def descriptor(media_type: MediaType, analysis_id: str) -> ValidatedFileDescriptor:
    if media_type is MediaType.IMAGE:
        extension = "png"
        mime_type = "image/png"
        parameters = ImageTechnicalParameters(
            width=1,
            height=1,
            format="PNG",
            color_mode="RGB",
            has_metadata=False,
        )
    elif media_type is MediaType.AUDIO:
        extension = "wav"
        mime_type = "audio/wav"
        parameters = AudioTechnicalParameters(
            duration_seconds=1.0,
            sample_rate_hz=8000,
            channels=1,
            codec="pcm_s16le",
        )
    else:
        extension = "mp4"
        mime_type = "video/mp4"
        parameters = VideoTechnicalParameters(
            duration_seconds=1.0,
            container="mp4",
            video_codec="mpeg4",
            width=1,
            height=1,
            fps=1.0,
            has_audio=False,
        )
    return ValidatedFileDescriptor(
        original_name=f"{analysis_id}.{extension}",
        extension=extension,
        declared_mime_type=mime_type,
        detected_mime_type=mime_type,
        media_type=media_type,
        size_bytes=1,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=parameters,
    )


def accepted_source(
    owner: CountingOwner,
    analysis_id: str,
    media_type: MediaType,
) -> Stage3Accepted:
    owned_source = owner.create(analysis_id)
    owner.ingest(owned_source, BytesIO(b"x"), 1)
    controlled_source = owner.transfer(owned_source)
    validated_file = descriptor(media_type, analysis_id)
    validation = ValidationResult(
        accepted=True,
        checks=[],
        errors=[],
        validated_file=validated_file,
    )
    return Stage3Accepted(
        analysis_id=analysis_id,
        registered_at=_REGISTERED,
        source=SourceContext(channel=SourceChannel.API),
        validation=validation,
        validated_file=validated_file,
        controlled_source=controlled_source,
    )


def make_runtime(
    root: Path,
    executor,
    *,
    image: int = 1,
    audio: int = 1,
    video: int = 1,
    clock: Clock | None = None,
    scheduler_factory: Callable[..., BoundedLocalScheduler] = BoundedLocalScheduler,
):
    config = make_config(root, image=image, audio=audio, video=video)
    registry = TaskRegistry()
    actual_clock = clock or UtcClock()
    scheduler = scheduler_factory(config=config, clock=actual_clock, registry=registry)
    receiver = Stage4TaskReceiver(
        config=config,
        clock=actual_clock,
        registry=registry,
        router=MediaRouter(dict.fromkeys(MediaType, executor)),
        queue=scheduler,
    )
    return config, registry, scheduler, receiver


def submit(
    receiver: Stage4TaskReceiver,
    owner: CountingOwner,
    analysis_id: str,
    media_type: MediaType = MediaType.IMAGE,
) -> Stage3Accepted:
    accepted = accepted_source(owner, analysis_id, media_type)
    receiver.accept(accepted)
    return accepted


def make_intake_service(
    config: AppConfig,
    owner: CountingOwner,
    receiver: Stage4TaskReceiver,
    analysis_id: str,
) -> FileIntakeService:
    clock = FixedClock()
    return FileIntakeService(
        controlled_intake=ControlledIntakeService(
            config=config,
            analysis_id_generator=SequenceIdGenerator(analysis_id),
            clock=clock,
            temporary_input_owner=owner,
        ),
        validator=FileValidator(config=config, temporary_input_owner=owner),
        temporary_input_owner=owner,
        accepted_receiver=receiver,
        clock=clock,
    )


@pytest.mark.parametrize(
    ("media_type", "limits", "expected"),
    [
        (MediaType.IMAGE, (2, 1, 1), 2),
        (MediaType.AUDIO, (1, 2, 1), 2),
        (MediaType.VIDEO, (1, 1, 2), 2),
    ],
)
def test_configured_concurrency_limit_is_reached_and_not_exceeded_per_media(
    tmp_path: Path,
    media_type: MediaType,
    limits: tuple[int, int, int],
    expected: int,
) -> None:
    executor = BlockingExecutor(expected_running=expected)
    _config, registry, scheduler, receiver = make_runtime(
        tmp_path / "temp",
        executor,
        image=limits[0],
        audio=limits[1],
        video=limits[2],
    )
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()

    accepted = [
        submit(receiver, owner, f"{media_type.value}-{index}", media_type)
        for index in range(expected)
    ]
    assert executor.expected_reached.wait(5)
    assert executor.peak[media_type] == expected
    assert executor.peak[media_type] <= scheduler.capacity(media_type)

    executor.release.set()
    scheduler.shutdown(drain=True)
    for item in accepted:
        snapshot = registry.snapshot(item.analysis_id)
        assert snapshot.status is AnalysisStatus.COMPLETED
        assert owner.cleanup_calls(item.analysis_id) == 1


def test_media_limits_are_independent_and_execute_concurrently(tmp_path: Path) -> None:
    executor = BlockingExecutor(expected_running=4)
    _config, _registry, scheduler, receiver = make_runtime(
        tmp_path / "temp", executor, image=1, audio=2, video=1
    )
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()

    submit(receiver, owner, "cross-image", MediaType.IMAGE)
    submit(receiver, owner, "cross-audio-1", MediaType.AUDIO)
    submit(receiver, owner, "cross-audio-2", MediaType.AUDIO)
    submit(receiver, owner, "cross-video", MediaType.VIDEO)

    assert executor.expected_reached.wait(5)
    assert executor.peak == Counter({MediaType.AUDIO: 2, MediaType.IMAGE: 1, MediaType.VIDEO: 1})
    executor.release.set()
    scheduler.shutdown(drain=True)


def test_fifo_dispatch_and_executor_never_run_in_caller_thread(tmp_path: Path) -> None:
    executor = BlockingExecutor()
    _config, _registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    caller_thread = get_ident()
    scheduler.start()

    submit(receiver, owner, "fifo-a")
    assert executor.expected_reached.wait(5)
    submit(receiver, owner, "fifo-b")
    executor.release.set()
    scheduler.shutdown(drain=True)

    assert executor.calls == ["fifo-a", "fifo-b"]
    assert all(thread_id != caller_thread for thread_id in executor.thread_ids)


def test_exactly_once_registry_claim_race_executes_and_cleans_once(tmp_path: Path) -> None:
    owner = CountingOwner(tmp_path / "temp")
    config = make_config(tmp_path / "temp")
    registry = TaskRegistry()
    queue = DeterministicTaskQueue()
    executor = RecordingExecutor()
    receiver = Stage4TaskReceiver(
        config=config,
        clock=UtcClock(),
        registry=registry,
        router=MediaRouter(dict.fromkeys(MediaType, executor)),
        queue=queue,
    )
    submit(receiver, owner, "claim-race")
    assert queue.pop_next() is not None
    processor = Stage4TaskProcessor(config=config, clock=UtcClock(), registry=registry)
    barrier = Barrier(3)
    outcomes: list[object] = []

    def race() -> None:
        barrier.wait()
        try:
            outcomes.append(processor.execute("claim-race", executor))
        except Exception as error:
            outcomes.append(error)

    threads = [Thread(target=race), Thread(target=race)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(5)

    assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, LifecycleStateError) for outcome in outcomes) == 1
    assert executor.calls == ["claim-race"]
    assert owner.cleanup_calls("claim-race") == 1
    assert not registry.is_active("claim-race")


def test_queue_overflow_fails_before_confirmation_and_stage3_cleans(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    executor = BlockingExecutor()
    config, registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()
    submit(receiver, owner, "overflow-running")
    assert executor.expected_reached.wait(5)
    submit(receiver, owner, "overflow-pending")
    service = make_intake_service(config, owner, receiver, "overflow-rejected")

    outcome = service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name="pressure.png",
        declared_content_type="image/png",
        source=SourceContext(channel=SourceChannel.API),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.cleanup is not None and outcome.cleanup.status is CleanupStatus.COMPLETED
    assert not registry.contains("overflow-rejected")
    assert owner.cleanup_calls("overflow-rejected") == 1
    assert scheduler.pending_count(MediaType.IMAGE) == 1
    executor.release.set()
    scheduler.shutdown(drain=True)


def test_provisional_handoff_cannot_execute_and_losing_shutdown_stays_stage3_owned(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    executor = RecordingExecutor()
    config, registry, scheduler, receiver = make_runtime(
        tmp_path / "temp", executor, scheduler_factory=CommitGateScheduler
    )
    assert isinstance(scheduler, CommitGateScheduler)
    owner = CountingOwner(tmp_path / "temp")
    service = make_intake_service(config, owner, receiver, "commit-race")
    scheduler.start()
    outcomes: list[Stage3Accepted | Stage3Terminal] = []

    receiver_thread = Thread(
        target=lambda: outcomes.append(
            service.process(
                BytesIO(media_files["png"].read_bytes()),
                original_name="commit.png",
                declared_content_type="image/png",
                source=SourceContext(channel=SourceChannel.API),
            )
        )
    )
    receiver_thread.start()
    assert scheduler.commit_entered.wait(5)
    assert not executor.called.is_set()
    shutdown_thread = Thread(target=lambda: scheduler.shutdown(drain=False))
    shutdown_thread.start()
    assert scheduler.wait_until_not_accepting(5)
    scheduler.allow_commit.set()
    receiver_thread.join(5)
    shutdown_thread.join(5)

    assert len(outcomes) == 1 and isinstance(outcomes[0], Stage3Terminal)
    assert outcomes[0].status is AnalysisStatus.FAILED
    assert not registry.contains("commit-race")
    assert owner.cleanup_calls("commit-race") == 1
    assert not executor.called.is_set()
    assert scheduler.is_stopped


def test_ordinary_executor_exception_does_not_destroy_worker(tmp_path: Path) -> None:
    executor = OrderedFailureExecutor()
    _config, registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()
    submit(receiver, owner, "ordinary-a")
    assert executor.first_started.wait(5)
    submit(receiver, owner, "ordinary-b")
    executor.release_first.set()
    scheduler.shutdown(drain=True)

    failed = registry.snapshot("ordinary-a")
    completed = registry.snapshot("ordinary-b")
    assert failed.status is AnalysisStatus.FAILED
    assert failed.stage is ProcessingStage.FINISHED
    assert failed.errors[0].code == "internal_error"
    assert "PRIVATE" not in repr(failed)
    assert completed.status is AnalysisStatus.COMPLETED
    assert executor.calls == ["ordinary-a", "ordinary-b"]
    assert owner.cleanup_calls("ordinary-a") == owner.cleanup_calls("ordinary-b") == 1


def test_terminal_clock_failure_does_not_strand_task_or_destroy_worker(tmp_path: Path) -> None:
    clock = TerminalFailureClock()
    executor = BlockingExecutor()
    _config, registry, scheduler, receiver = make_runtime(
        tmp_path / "temp",
        executor,
        clock=clock,
    )
    owner = TerminalFailureOwner(tmp_path / "temp", clock)
    scheduler.start()
    first = submit(receiver, owner, "worker-clock-first")
    assert executor.expected_reached.wait(5)
    second = submit(receiver, owner, "worker-clock-second")
    executor.release.set()
    scheduler.shutdown(drain=True)

    for accepted in (first, second):
        snapshot = registry.snapshot(accepted.analysis_id)
        assert snapshot.status is AnalysisStatus.COMPLETED
        assert snapshot.stage is ProcessingStage.FINISHED
        assert snapshot.finished_at is not None
        assert snapshot.cleanup is not None
        assert snapshot.cleanup.status is CleanupStatus.COMPLETED
        assert snapshot.cleanup.finished_at == snapshot.finished_at
        assert accepted.controlled_source.is_released
        assert owner.cleanup_calls(accepted.analysis_id) == 1
        assert not registry.is_active(accepted.analysis_id)
    assert executor.calls == ["worker-clock-first", "worker-clock-second"]
    assert scheduler.is_stopped


def test_non_draining_shutdown_fails_pending_without_start_and_waits_for_running(
    tmp_path: Path,
) -> None:
    executor = BlockingExecutor()
    _config, registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()
    submit(receiver, owner, "nondrain-running")
    assert executor.expected_reached.wait(5)
    submit(receiver, owner, "nondrain-pending")
    shutdown_returned = Event()
    shutdown_thread = Thread(
        target=lambda: (scheduler.shutdown(drain=False), shutdown_returned.set())
    )
    shutdown_thread.start()
    assert scheduler.wait_until_not_accepting(5)
    assert not shutdown_returned.is_set()
    executor.release.set()
    shutdown_thread.join(5)

    running = registry.snapshot("nondrain-running")
    pending = registry.snapshot("nondrain-pending")
    assert running.status is AnalysisStatus.COMPLETED and running.started_at is not None
    assert pending.status is AnalysisStatus.FAILED
    assert pending.stage is ProcessingStage.FINISHED
    assert pending.started_at is None
    assert pending.finished_at is not None
    assert pending.errors[0].code == "internal_error"
    assert executor.calls == ["nondrain-running"]
    assert owner.cleanup_calls("nondrain-running") == 1
    assert owner.cleanup_calls("nondrain-pending") == 1
    assert scheduler.is_stopped


def test_non_draining_pending_terminal_clock_failure_cannot_strand_task(
    tmp_path: Path,
) -> None:
    clock = TerminalFailureClock()
    executor = BlockingExecutor()
    _config, registry, scheduler, receiver = make_runtime(
        tmp_path / "temp",
        executor,
        clock=clock,
    )
    owner = TerminalFailureOwner(tmp_path / "temp", clock)
    scheduler.start()
    submit(receiver, owner, "nondrain-clock-running")
    assert executor.expected_reached.wait(5)
    pending_accepted = submit(receiver, owner, "nondrain-clock-pending")
    shutdown_thread = Thread(target=lambda: scheduler.shutdown(drain=False))
    shutdown_thread.start()
    assert scheduler.wait_until_not_accepting(5)
    executor.release.set()
    shutdown_thread.join(5)

    pending = registry.snapshot("nondrain-clock-pending")
    assert pending.status is AnalysisStatus.FAILED
    assert pending.stage is ProcessingStage.FINISHED
    assert pending.started_at is None
    assert pending.finished_at is not None
    assert pending.cleanup is not None
    assert pending.cleanup.status is CleanupStatus.COMPLETED
    assert pending.cleanup.finished_at == pending.finished_at
    assert pending_accepted.controlled_source.is_released
    assert owner.cleanup_calls("nondrain-clock-pending") == 1
    assert not registry.is_active("nondrain-clock-pending")
    assert executor.calls == ["nondrain-clock-running"]
    assert scheduler.is_stopped


def test_draining_shutdown_executes_all_confirmed_pending_tasks(tmp_path: Path) -> None:
    executor = BlockingExecutor(expected_running=2)
    _config, registry, scheduler, receiver = make_runtime(
        tmp_path / "temp", executor, image=2
    )
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()
    analysis_ids = [f"drain-{index}" for index in range(4)]
    for analysis_id in analysis_ids[:2]:
        submit(receiver, owner, analysis_id)
    assert executor.expected_reached.wait(5)
    for analysis_id in analysis_ids[2:]:
        submit(receiver, owner, analysis_id)
    shutdown_thread = Thread(target=lambda: scheduler.shutdown(drain=True))
    shutdown_thread.start()
    executor.release.set()
    shutdown_thread.join(5)

    assert set(executor.calls) == set(analysis_ids)
    assert scheduler.is_stopped
    for analysis_id in analysis_ids:
        assert registry.snapshot(analysis_id).status is AnalysisStatus.COMPLETED
        assert owner.cleanup_calls(analysis_id) == 1


def test_shutdown_stops_new_stage3_handoffs_but_keeps_confirmed_stage4_ownership(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    executor = BlockingExecutor()
    config, registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()
    submit(receiver, owner, "confirmed-running")
    assert executor.expected_reached.wait(5)
    shutdown_thread = Thread(target=lambda: scheduler.shutdown(drain=True))
    shutdown_thread.start()
    assert scheduler.wait_until_not_accepting(5)
    service = make_intake_service(config, owner, receiver, "after-shutdown")

    outcome = service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name="after.png",
        declared_content_type="image/png",
        source=SourceContext(channel=SourceChannel.API),
    )
    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert not registry.contains("after-shutdown")
    assert owner.cleanup_calls("after-shutdown") == 1

    executor.release.set()
    shutdown_thread.join(5)
    assert registry.snapshot("confirmed-running").status is AnalysisStatus.COMPLETED
    assert owner.cleanup_calls("confirmed-running") == 1


def test_scheduler_lifecycle_operations_are_deterministic_and_unavailable_before_start(
    tmp_path: Path,
) -> None:
    executor = RecordingExecutor()
    _config, registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    accepted = accepted_source(owner, "before-start", MediaType.IMAGE)

    with pytest.raises(Stage4ReceiverError):
        receiver.accept(accepted)
    assert not registry.contains("before-start")
    accepted.controlled_source.cleanup()
    assert owner.cleanup_calls("before-start") == 1

    scheduler.start()
    with pytest.raises(SchedulerStateError):
        scheduler.start()
    scheduler.shutdown()
    with pytest.raises(SchedulerStateError):
        scheduler.shutdown()
    with pytest.raises(SchedulerStateError):
        scheduler.start()


def test_worker_base_exception_is_cleaned_and_reraised_at_controlled_shutdown(
    tmp_path: Path,
) -> None:
    executor = TerminatingExecutor()
    _config, registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    scheduler.start()
    submit(receiver, owner, "worker-termination")
    assert executor.started.wait(5)
    submit(receiver, owner, "worker-pending")
    executor.release.set()
    assert scheduler.wait_until_not_accepting(5)

    with pytest.raises(KeyboardInterrupt):
        scheduler.shutdown()

    snapshot = registry.snapshot("worker-termination")
    assert snapshot.status is AnalysisStatus.FAILED
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.cleanup is not None
    assert owner.cleanup_calls("worker-termination") == 1
    pending = registry.snapshot("worker-pending")
    assert pending.status is AnalysisStatus.FAILED
    assert pending.started_at is None
    assert pending.cleanup is not None
    assert executor.calls == ["worker-termination"]
    assert owner.cleanup_calls("worker-pending") == 1
    assert scheduler.is_stopped
