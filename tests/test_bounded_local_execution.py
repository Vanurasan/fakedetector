"""Stage 4 Increment 2 bounded local execution lifecycle tests."""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from inspect import getsourcelines
from io import BytesIO
from pathlib import Path
from threading import Barrier, Event, Lock, Thread, get_ident
from threading import enumerate as enumerate_threads
from types import FrameType

import pytest
from result_backend_fakes import SuccessfulAcceptedResultFinalizer

import fakedetector.lifecycle.scheduler as scheduler_module
from fakedetector.app import create_app
from fakedetector.config.models import AppConfig
from fakedetector.core import AuthoritativeLifecycleClock, Clock, UtcClock
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


class SequenceClock:
    def __init__(self, *timestamps: datetime) -> None:
        self._timestamps = list(timestamps)
        self._lock = Lock()

    def now(self) -> datetime:
        with self._lock:
            if not self._timestamps:
                raise AssertionError("clock exhausted")
            return self._timestamps.pop(0)


class WorkerArmableClock:
    def __init__(self, *, initial: datetime) -> None:
        self._current = initial
        self._lock = Lock()
        self._control_thread = get_ident()
        self._armed = False
        self._invalid_offset = None

    def arm_invalid_next_worker(self, *, offset: timedelta) -> None:
        with self._lock:
            self._armed = True
            self._invalid_offset = offset

    def now(self) -> datetime:
        with self._lock:
            result = self._current
            self._current += timedelta(seconds=1)
            if self._armed and get_ident() != self._control_thread:
                assert self._invalid_offset is not None
                self._armed = False
                invalid = result + self._invalid_offset
                self._invalid_offset = None
                return invalid
            return result


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


class EventedOwner(CountingOwner):
    def __init__(self, root_path: Path, watched_analysis_id: str) -> None:
        super().__init__(root_path)
        self.watched_analysis_id = watched_analysis_id
        self.cleaned = Event()

    def cleanup(self, owned_source: OwnedSource) -> None:
        super().cleanup(owned_source)
        if owned_source.analysis_id == self.watched_analysis_id:
            self.cleaned.set()


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


class SelectiveBlockingExecutor:
    def __init__(self, blocked_analysis_id: str) -> None:
        self.blocked_analysis_id = blocked_analysis_id
        self.release = Event()
        self.blocked_started = Event()
        self.calls: list[str] = []

    def execute(self, task) -> TaskExecutionOutcome:
        analysis_id = task.context.analysis_id
        self.calls.append(analysis_id)
        if analysis_id == self.blocked_analysis_id:
            self.blocked_started.set()
            assert self.release.wait(5)
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


def install_scheduler_start_failure(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
    *,
    start_before_failure: bool = False,
    joined: list[Thread] | None = None,
) -> list[Thread]:
    real_thread = Thread
    created: list[Thread] = []
    start_count = 0

    def thread_factory(*args: object, **kwargs: object) -> Thread:
        thread = real_thread(*args, **kwargs)
        real_start = thread.start

        def controlled_start() -> None:
            nonlocal start_count
            start_count += 1
            if start_count == 2:
                if start_before_failure:
                    real_start()
                    assert thread.ident is not None
                raise failure
            real_start()

        real_join = thread.join

        def controlled_join(timeout: float | None = None) -> None:
            if joined is not None:
                joined.append(thread)
            real_join(timeout)

        thread.start = controlled_start
        thread.join = controlled_join
        created.append(thread)
        return thread

    monkeypatch.setattr(scheduler_module, "Thread", thread_factory)
    return created


def install_scheduler_post_loop_interruption(
    monkeypatch: pytest.MonkeyPatch,
    interruption: BaseException,
    *,
    worker_count: int,
    joined: list[Thread],
    before_statement: str,
) -> tuple[list[Thread], Callable[[FrameType, str, object], Callable[..., object] | None]]:
    real_thread = Thread
    created: list[Thread] = []
    completed_starts = 0
    start_source, start_line = getsourcelines(BoundedLocalScheduler.start)
    interruption_line = start_line + next(
        index for index, line in enumerate(start_source) if before_statement in line
    )

    def thread_factory(*args: object, **kwargs: object) -> Thread:
        thread = real_thread(*args, **kwargs)
        real_start = thread.start
        real_join = thread.join

        def controlled_start() -> None:
            nonlocal completed_starts
            real_start()
            completed_starts += 1

        def controlled_join(timeout: float | None = None) -> None:
            joined.append(thread)
            real_join(timeout)

        thread.start = controlled_start
        thread.join = controlled_join
        created.append(thread)
        return thread

    def interrupt_after_launch_loop(
        frame: FrameType,
        event: str,
        _arg: object,
    ) -> Callable[..., object] | None:
        if (
            completed_starts == worker_count
            and event == "line"
            and frame.f_code is BoundedLocalScheduler.start.__code__
            and frame.f_lineno == interruption_line
        ):
            raise interruption
        return interrupt_after_launch_loop

    monkeypatch.setattr(scheduler_module, "Thread", thread_factory)
    return created, interrupt_after_launch_loop


def install_scheduler_thread_tracking(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[Thread], list[Thread]]:
    real_thread = Thread
    created: list[Thread] = []
    joined: list[Thread] = []

    def thread_factory(*args: object, **kwargs: object) -> Thread:
        thread = real_thread(*args, **kwargs)
        real_join = thread.join

        def tracked_join(timeout: float | None = None) -> None:
            joined.append(thread)
            real_join(timeout)

        thread.join = tracked_join
        created.append(thread)
        return thread

    monkeypatch.setattr(scheduler_module, "Thread", thread_factory)
    return created, joined


def stop_scheduler_test_threads(
    scheduler: BoundedLocalScheduler,
    created: list[Thread],
) -> None:
    if any(thread.is_alive() for thread in created):
        with scheduler._condition:
            scheduler._state = scheduler_module._SchedulerState.STOPPED
            scheduler._condition.notify_all()
        for thread in created:
            if thread.ident is not None:
                thread.join(5)


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
    raw_clock = clock or UtcClock()
    actual_clock = AuthoritativeLifecycleClock(raw_clock)
    scheduler = scheduler_factory(
        config=config,
        clock=actual_clock,
        registry=registry,
        result_finalizer=SuccessfulAcceptedResultFinalizer(),
    )
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
    clock = receiver._clock
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
    clock = AuthoritativeLifecycleClock(UtcClock())
    receiver = Stage4TaskReceiver(
        config=config,
        clock=clock,
        registry=registry,
        router=MediaRouter(dict.fromkeys(MediaType, executor)),
        queue=queue,
    )
    submit(receiver, owner, "claim-race")
    assert queue.pop_next() is not None
    processor = Stage4TaskProcessor(
        config=config,
        clock=clock,
        registry=registry,
        result_finalizer=SuccessfulAcceptedResultFinalizer(),
    )
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


def test_worker_leaves_post_save_publication_failure_in_persistence_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = RecordingExecutor()
    _config, registry, scheduler, receiver = make_runtime(tmp_path / "temp", executor)
    owner = CountingOwner(tmp_path / "temp")
    real_finalize = registry.finalize_terminal_settlement
    finalize_calls = 0

    def fail_first_finalize(analysis_id: str, owner_token: object, finished_at: datetime) -> None:
        nonlocal finalize_calls
        finalize_calls += 1
        if finalize_calls == 1:
            raise LifecycleStateError()
        real_finalize(analysis_id, owner_token, finished_at)

    monkeypatch.setattr(registry, "finalize_terminal_settlement", fail_first_finalize)
    scheduler.start()
    accepted = submit(receiver, owner, "fact-ready-recovery")
    scheduler.shutdown(drain=True)

    snapshot = registry.snapshot(accepted.analysis_id)
    assert finalize_calls == 1
    assert snapshot.status is AnalysisStatus.COMPLETED
    assert snapshot.stage is ProcessingStage.PERSISTENCE
    assert snapshot.cleanup is None
    assert snapshot.finished_at is None
    assert owner.cleanup_calls(accepted.analysis_id) == 1
    assert accepted.controlled_source.is_released
    assert registry.is_active(accepted.analysis_id)
    assert registry.recoverable_terminal_tasks() == ()


def test_regressing_raw_started_sample_degrades_and_worker_remains_usable(
    tmp_path: Path,
) -> None:
    clock = WorkerArmableClock(initial=_REGISTERED)
    executor = SelectiveBlockingExecutor("valid-start-b")
    _config, registry, scheduler, receiver = make_runtime(
        tmp_path / "temp",
        executor,
        clock=clock,
    )
    owner = EventedOwner(tmp_path / "temp", "invalid-start-a")
    scheduler.start()
    clock.arm_invalid_next_worker(offset=timedelta(days=-1))
    first = submit(receiver, owner, "invalid-start-a")
    assert owner.cleaned.wait(5)
    second = submit(receiver, owner, "valid-start-b")
    assert executor.blocked_started.wait(5)
    executor.release.set()
    scheduler.shutdown(drain=True)

    first_finished = registry.snapshot(first.analysis_id)
    assert first_finished.status is AnalysisStatus.COMPLETED
    assert first_finished.stage is ProcessingStage.FINISHED
    assert first_finished.started_at is not None
    assert first_finished.queued_at is not None
    assert first_finished.started_at >= first_finished.queued_at
    assert first_finished.finished_at is not None
    assert first_finished.cleanup is not None
    assert first_finished.cleanup.finished_at == first_finished.finished_at
    assert owner.cleanup_calls(first.analysis_id) == 1
    assert first.controlled_source.is_released
    assert not registry.is_active(first.analysis_id)

    completed = registry.snapshot(second.analysis_id)
    assert completed.status is AnalysisStatus.COMPLETED
    assert completed.stage is ProcessingStage.FINISHED
    assert completed.started_at is not None
    assert completed.started_at >= completed.queued_at  # type: ignore[operator]
    assert owner.cleanup_calls(second.analysis_id) == 1
    assert second.controlled_source.is_released
    assert executor.calls == [first.analysis_id, second.analysis_id]
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


def test_scheduler_ordinary_partial_start_failure_joins_started_threads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, _registry, scheduler, _receiver = make_runtime(
        tmp_path / "temp",
        RecordingExecutor(),
    )
    joined: list[Thread] = []
    created = install_scheduler_start_failure(
        monkeypatch,
        RuntimeError("private startup"),
        joined=joined,
    )

    try:
        with pytest.raises(SchedulerStateError):
            scheduler.start()

        assert created[0].ident is not None
        assert created[0] in joined
        assert created[1] not in joined
        assert all(not thread.is_alive() for thread in created)
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        stop_scheduler_test_threads(scheduler, created)


def test_scheduler_interrupted_partial_start_preserves_exception_and_joins_threads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, _registry, scheduler, _receiver = make_runtime(
        tmp_path / "temp",
        RecordingExecutor(),
    )
    interruption = KeyboardInterrupt("scheduler startup interrupted")
    joined: list[Thread] = []
    created = install_scheduler_start_failure(
        monkeypatch,
        interruption,
        joined=joined,
    )

    try:
        with pytest.raises(KeyboardInterrupt) as captured:
            scheduler.start()

        assert captured.value is interruption
        assert created[0].ident is not None
        assert created[0] in joined
        assert created[1] not in joined
        assert all(not thread.is_alive() for thread in created)
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        stop_scheduler_test_threads(scheduler, created)


def test_scheduler_started_then_interrupted_thread_is_explicitly_joined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, _registry, scheduler, _receiver = make_runtime(
        tmp_path / "temp",
        RecordingExecutor(),
    )
    interruption = KeyboardInterrupt("scheduler startup interrupted after start")
    joined: list[Thread] = []
    created = install_scheduler_start_failure(
        monkeypatch,
        interruption,
        start_before_failure=True,
        joined=joined,
    )

    try:
        with pytest.raises(KeyboardInterrupt) as captured:
            scheduler.start()

        assert captured.value is interruption
        assert created[1].ident is not None
        assert created[1] in joined
        assert all(thread in joined for thread in created if thread.ident is not None)
        assert all(not thread.is_alive() for thread in created)
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        stop_scheduler_test_threads(scheduler, created)


def test_scheduler_interruption_after_start_return_joins_preowned_thread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, _registry, scheduler, _receiver = make_runtime(
        tmp_path / "temp",
        RecordingExecutor(),
    )
    interruption = KeyboardInterrupt("scheduler interrupted after start returned")
    real_thread = Thread
    created: list[Thread] = []
    joined: list[Thread] = []
    start_returned = False

    def thread_factory(*args: object, **kwargs: object) -> Thread:
        thread = real_thread(*args, **kwargs)
        real_start = thread.start
        real_join = thread.join

        def controlled_start() -> None:
            nonlocal start_returned
            real_start()
            start_returned = True

        def controlled_join(timeout: float | None = None) -> None:
            joined.append(thread)
            real_join(timeout)

        thread.start = controlled_start
        thread.join = controlled_join
        created.append(thread)
        return thread

    def interrupt_scheduler_after_return(
        frame: FrameType,
        event: str,
        _arg: object,
    ) -> Callable[..., object] | None:
        if (
            start_returned
            and event == "line"
            and frame.f_code is BoundedLocalScheduler.start.__code__
        ):
            raise interruption
        return interrupt_scheduler_after_return

    monkeypatch.setattr(scheduler_module, "Thread", thread_factory)
    previous_trace = sys.gettrace()
    sys.settrace(interrupt_scheduler_after_return)
    try:
        with pytest.raises(KeyboardInterrupt) as captured:
            scheduler.start()

        assert start_returned
        assert captured.value is interruption
        assert created[0].ident is not None
        assert created[0] in joined
        assert all(thread not in joined for thread in created[1:])
        assert all(not thread.is_alive() for thread in created)
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        sys.settrace(previous_trace)
        stop_scheduler_test_threads(scheduler, created)


@pytest.mark.parametrize(
    "before_statement",
    ["self._threads = threads", "self._state = _SchedulerState.RUNNING"],
    ids=["before-ownership", "after-ownership-before-running"],
)
@pytest.mark.parametrize(
    ("failure_type", "expected_type"),
    [
        (KeyboardInterrupt, KeyboardInterrupt),
        (SystemExit, SystemExit),
        (RuntimeError, SchedulerStateError),
    ],
    ids=["keyboard-interrupt", "system-exit", "ordinary-exception"],
)
def test_scheduler_post_loop_failure_joins_all_started_workers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    before_statement: str,
    failure_type: type[BaseException],
    expected_type: type[BaseException],
) -> None:
    _config, _registry, scheduler, _receiver = make_runtime(
        tmp_path / "temp",
        RecordingExecutor(),
    )
    failure = failure_type("scheduler failed before startup commit")
    joined: list[Thread] = []
    created, trace = install_scheduler_post_loop_interruption(
        monkeypatch,
        failure,
        worker_count=len(MediaType),
        joined=joined,
        before_statement=before_statement,
    )
    previous_trace = sys.gettrace()
    sys.settrace(trace)

    try:
        with pytest.raises(expected_type) as captured:
            scheduler.start()

        if isinstance(failure, Exception):
            assert captured.value is not failure
        else:
            assert captured.value is failure
        assert len(created) == len(MediaType)
        assert all(thread.ident is not None for thread in created)
        assert joined == created
        assert all(not thread.is_alive() for thread in created)
        assert not scheduler.is_running
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        sys.settrace(previous_trace)
        stop_scheduler_test_threads(scheduler, created)


@pytest.mark.parametrize("failure_type", [KeyboardInterrupt, SystemExit])
def test_production_lifespan_interrupted_start_leaves_no_partial_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_type: type[BaseException],
) -> None:
    interruption = failure_type("production scheduler startup interrupted")
    joined: list[Thread] = []
    created = install_scheduler_start_failure(monkeypatch, interruption, joined=joined)
    app = create_app(make_config(tmp_path / "temp"))
    scheduler = app.state.runtime.scheduler

    def unexpected_shutdown(*, drain: bool = True) -> None:
        del drain
        raise AssertionError("failed start already owns its cleanup")

    monkeypatch.setattr(scheduler, "shutdown", unexpected_shutdown)

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            raise AssertionError("lifespan body must not run after failed startup")

    try:
        with pytest.raises(failure_type) as captured:
            asyncio.run(run_lifespan())

        assert captured.value is interruption
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert joined == created[:1]
        assert all(not thread.is_alive() for thread in created)
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        stop_scheduler_test_threads(scheduler, created)


@pytest.mark.parametrize("failure_type", [KeyboardInterrupt, SystemExit, RuntimeError])
@pytest.mark.parametrize("failure_point", ["post-start", "body"])
def test_production_lifespan_caller_interruption_shuts_down_owned_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_type: type[BaseException],
    failure_point: str,
) -> None:
    interruption = failure_type("production lifespan interrupted after scheduler start")
    created, joined = install_scheduler_thread_tracking(monkeypatch)
    app = create_app(make_config(tmp_path / "temp"))
    scheduler = app.state.runtime.scheduler
    real_start = scheduler.start

    def start_then_interrupt() -> None:
        real_start()
        if failure_point == "post-start":
            raise interruption

    monkeypatch.setattr(scheduler, "start", start_then_interrupt)

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert failure_point == "body"
            raise interruption

    try:
        with pytest.raises(failure_type) as captured:
            asyncio.run(run_lifespan())

        assert captured.value is interruption
        assert len(created) == len(MediaType)
        assert all(thread.ident is not None for thread in created)
        assert joined == created
        assert all(not thread.is_alive() for thread in created)
        assert not scheduler.is_running
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        stop_scheduler_test_threads(scheduler, created)


def test_production_lifespan_normally_starts_and_shuts_down_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created, joined = install_scheduler_thread_tracking(monkeypatch)
    app = create_app(make_config(tmp_path / "temp"))
    scheduler = app.state.runtime.scheduler

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert scheduler.is_running
            assert len(created) == len(MediaType)
            assert all(thread.ident is not None for thread in created)

    try:
        asyncio.run(run_lifespan())

        assert joined == created
        assert all(not thread.is_alive() for thread in created)
        assert not scheduler.is_running
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        stop_scheduler_test_threads(scheduler, created)


@pytest.mark.parametrize("failure_point", ["post-start", "body"])
@pytest.mark.parametrize("worker_type", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("primary_type", [KeyboardInterrupt, SystemExit, RuntimeError, None])
def test_production_lifespan_preserves_exception_precedence_after_worker_termination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
    worker_type: type[BaseException],
    primary_type: type[BaseException] | None,
) -> None:
    primary = primary_type("primary caller failure") if primary_type is not None else None
    termination = worker_type("secondary worker termination")
    assert primary is not termination
    created, joined = install_scheduler_thread_tracking(monkeypatch)
    config = make_config(tmp_path / "temp")
    app = create_app(config)
    scheduler = app.state.runtime.scheduler
    real_start = scheduler.start

    class FailingExecutor:
        def execute(self, task) -> TaskExecutionOutcome:
            raise termination

    receiver = Stage4TaskReceiver(
        config=config,
        clock=scheduler._processor._clock,
        registry=app.state.runtime.registry,
        router=MediaRouter(dict.fromkeys(MediaType, FailingExecutor())),
        queue=scheduler,
    )
    owner = CountingOwner(tmp_path / "temp")

    def run_worker_then_fail_caller() -> None:
        submit(receiver, owner, "lifespan-worker-termination")
        assert scheduler.wait_until_not_accepting(5)
        assert scheduler._termination is termination
        assert not scheduler.is_running
        assert not scheduler.is_stopped
        if primary is not None:
            raise primary

    if failure_point == "post-start":

        def start_then_fail() -> None:
            real_start()
            run_worker_then_fail_caller()

        monkeypatch.setattr(scheduler, "start", start_then_fail)

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            if failure_point == "body":
                run_worker_then_fail_caller()
            else:
                assert primary is None

    expected = primary if primary is not None else termination
    try:
        with pytest.raises(BaseException) as captured:
            asyncio.run(run_lifespan())

        assert captured.value is expected
        assert type(captured.value) is type(expected)
        assert len(created) == len(MediaType)
        assert joined == created
        assert all(not thread.is_alive() for thread in created)
        assert not scheduler.is_running
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
        snapshot = app.state.runtime.registry.snapshot("lifespan-worker-termination")
        assert snapshot.status is AnalysisStatus.FAILED
        assert snapshot.stage is ProcessingStage.FINISHED
        assert owner.cleanup_calls("lifespan-worker-termination") == 1
    finally:
        stop_scheduler_test_threads(scheduler, created)


@pytest.mark.parametrize("failure_point", ["post-start", "body"])
@pytest.mark.parametrize("cleanup_type", [RuntimeError, KeyboardInterrupt])
def test_production_lifespan_does_not_hide_unfinished_shutdown_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
    cleanup_type: type[BaseException],
) -> None:
    primary = SystemExit("primary caller failure")
    cleanup_failure = cleanup_type("join interrupted before cleanup completed")
    created, joined = install_scheduler_thread_tracking(monkeypatch)
    app = create_app(make_config(tmp_path / "temp"))
    scheduler = app.state.runtime.scheduler
    real_start = scheduler.start

    def start_with_failing_join() -> None:
        real_start()
        tracked_join = created[0].join

        def fail_join_once(timeout: float | None = None) -> None:
            created[0].join = tracked_join
            raise cleanup_failure

        monkeypatch.setattr(created[0], "join", fail_join_once)
        if failure_point == "post-start":
            raise primary

    monkeypatch.setattr(scheduler, "start", start_with_failing_join)

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            raise primary

    try:
        with pytest.raises(BaseException) as captured:
            asyncio.run(run_lifespan())

        assert captured.value is cleanup_failure
        assert captured.value.__context__ is primary
        assert not scheduler.is_stopped
        assert not scheduler.is_running
        assert scheduler._threads == created
        assert joined == []
    finally:
        stop_scheduler_test_threads(scheduler, created)


def test_production_lifespan_post_loop_interruption_leaves_no_started_workers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interruption = KeyboardInterrupt("production scheduler interrupted before commit")
    joined: list[Thread] = []
    created, trace = install_scheduler_post_loop_interruption(
        monkeypatch,
        interruption,
        worker_count=len(MediaType),
        joined=joined,
        before_statement="self._threads = threads",
    )
    app = create_app(make_config(tmp_path / "temp"))
    scheduler = app.state.runtime.scheduler

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            raise AssertionError("lifespan body must not run after failed startup")

    previous_trace = sys.gettrace()
    sys.settrace(trace)
    try:
        with pytest.raises(KeyboardInterrupt) as captured:
            asyncio.run(run_lifespan())

        assert captured.value is interruption
        assert len(created) == len(MediaType)
        assert all(thread.ident is not None for thread in created)
        assert joined == created
        assert all(not thread.is_alive() for thread in created)
        assert not scheduler.is_running
        assert scheduler.is_stopped
        assert scheduler._threads == []
        assert not any(thread.name.startswith("stage4-") for thread in enumerate_threads())
    finally:
        sys.settrace(previous_trace)
        stop_scheduler_test_threads(scheduler, created)


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
