"""Integrated Stage 4 to Stage 5 execution lifecycle tests."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from copy import copy
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from threading import Thread
from typing import NoReturn, cast

import pytest
import yaml

import fakedetector.core._bounded_process as bounded_process_module
import fakedetector.lifecycle as lifecycle
import fakedetector.lifecycle.execution as execution_module
from fakedetector._stage5_resources import _GeneratedArtifactBudget
from fakedetector.analyzers._catalog import _framework_test_registrations
from fakedetector.analyzers._errors import AnalyzerInfrastructureError
from fakedetector.analyzers._orchestrator import AnalyzerOrchestrator, _WorkerRunner
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.analyzers._transport import (
    _MAX_RESPONSE_BYTES,
    _MAX_STAGE5_ANALYZER_RESULT_BYTES,
    _serialize_stage5_analyzer_result,
    _Stage5AnalyzerResultSizeError,
    _WorkerRequest,
    _WorkerResponseKind,
)
from fakedetector.analyzers._worker import (
    _encode_response,
    _execute_worker,
    _WorkerRun,
    _WorkerRunKind,
)
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.core import AuthoritativeLifecycleClock
from fakedetector.domain import (
    AnalysisStatus,
    AnalyzerResult,
    AnalyzerStatus,
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
    Stage3Accepted,
)
from fakedetector.intake.temporary_input import PreparedSourceRef
from fakedetector.lifecycle import (
    AnalysisContext,
    AnalysisStateMachine,
    AnalysisTask,
    DeterministicTaskQueue,
    LifecycleStateError,
    MediaRouter,
    Stage4LifecycleRunner,
    Stage4TaskProcessor,
    Stage4TaskReceiver,
    TaskExecutionOutcome,
    TaskRegistry,
    WorkspaceArtifactRegistry,
    config_snapshot_fingerprint,
)
from fakedetector.lifecycle._stage5 import Stage5ExecutionService
from fakedetector.lifecycle.models import Stage5TaskData, _StoredAnalyzerResult
from fakedetector.preprocessing._errors import PreprocessingError
from fakedetector.preprocessing._media_tools import _FFmpegPreprocessingTool
from fakedetector.preprocessing._models import (
    PreparedArtifact,
    PreparedMedia,
)
from fakedetector.preprocessing._requirements import PreprocessingRequirements
from fakedetector.preprocessing._service import (
    PreprocessingDispatcher,
    PreprocessingRequest,
)

_CREATED_AT = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


class _IncrementingClock:
    def __init__(self, current: datetime = _CREATED_AT) -> None:
        self.current = current

    def now(self) -> datetime:
        result = self.current
        self.current += timedelta(seconds=1)
        return result


class _FixedIdGenerator:
    def __init__(self, analysis_id: str) -> None:
        self._analysis_id = analysis_id

    def generate(self) -> str:
        return self._analysis_id


class _ManualMonotonic:
    def __init__(self, current: float = 0.0) -> None:
        self.current = current
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


class _RecordingRegistry(TaskRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.stage5_events: list[str] = []

    def publish_stage5_prepared(
        self,
        task: AnalysisTask,
        prepared_media: PreparedMedia,
    ) -> None:
        super().publish_stage5_prepared(task, prepared_media)
        self.stage5_events.append("prepared")

    def start_stage5_analysis(self, task: AnalysisTask) -> None:
        super().start_stage5_analysis(task)
        self.stage5_events.append("analysis")

    def append_stage5_analyzer_result(
        self,
        task: AnalysisTask,
        result: AnalyzerResult,
    ) -> None:
        super().append_stage5_analyzer_result(task, result)
        self.stage5_events.append(f"result:{result.analyzer_id}")


class _SnapshotBoundTestComponent:
    def __init__(self) -> None:
        self._test_config_snapshot: _ConfigSnapshot | None = None

    def _bind_config(self, config: AppConfig) -> None:
        self._test_config_snapshot = _ConfigSnapshot.capture(config)

    def _uses_config_snapshot(self, snapshot: _ConfigSnapshot) -> bool:
        return self._test_config_snapshot == snapshot


class _RecordingPreprocessing(_SnapshotBoundTestComponent):
    def __init__(
        self,
        *,
        clock: _ManualMonotonic | None = None,
        consume_seconds: float = 0.0,
        fail: bool = False,
        resource_limit: bool = False,
        create_artifact: bool = False,
        lock_probe: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._clock = clock
        self._consume_seconds = consume_seconds
        self._fail = fail
        self._resource_limit = resource_limit
        self._create_artifact = create_artifact
        self._lock_probe = lock_probe
        self.calls = 0
        self.requirements: list[PreprocessingRequirements] = []
        self.remaining_at_entry: list[float] = []

    def prepare(
        self,
        request: PreprocessingRequest,
        requirements: PreprocessingRequirements,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
    ) -> PreparedMedia:
        self.calls += 1
        self.requirements.append(requirements)
        assert remaining_timeout_seconds is not None
        self.remaining_at_entry.append(remaining_timeout_seconds())
        if self._lock_probe is not None:
            self._lock_probe()

        artifact_ref = request.artifact_registry.register(
            "stage5_test_artifact",
            "preprocessing/test/artifact.bin",
        )
        artifact = PreparedArtifact(
            artifact_id="stage5_test_artifact",
            artifact_type="normalized_input",
            artifact_ref=artifact_ref,
            format="bin",
        )
        if self._create_artifact:
            request.artifact_registry.with_local_artifact_path(
                artifact_ref,
                lambda path: _write_artifact(path),
            )
        if self._clock is not None:
            self._clock.advance(self._consume_seconds)
        if self._resource_limit:
            raise PreprocessingError("resource_limit", "test_budget")
        if self._fail:
            raise PreprocessingError("decode", "test_preprocessing")
        return PreparedMedia(
            analysis_id=request.analysis_id,
            media_type=request.validated_file.media_type,
            source_file_ref=request.source_file_ref,
            artifacts=(artifact,),
        )


class _ControlledSafetyBarrier:
    def __init__(
        self,
        *,
        safe: bool,
        lock_probe: Callable[[], None] | None = None,
        raise_once: bool = False,
    ) -> None:
        self.safe = safe
        self.lock_probe = lock_probe
        self.raise_once = raise_once
        self.calls = 0

    def try_confirm_safe(self) -> bool:
        self.calls += 1
        if self.lock_probe is not None:
            self.lock_probe()
        if self.raise_once:
            self.raise_once = False
            raise RuntimeError("PRIVATE cleanup safety detail")
        return self.safe


class _SequencedRunner:
    def __init__(
        self,
        *kinds: _WorkerRunKind,
        clock: _ManualMonotonic | None = None,
        consume_seconds: tuple[float, ...] = (),
        fatal_barrier: _ControlledSafetyBarrier | None = None,
    ) -> None:
        self._kinds = list(kinds)
        self._clock = clock
        self._consume_seconds = consume_seconds
        self._fatal_barrier = fatal_barrier
        self.requests: list[_WorkerRequest] = []
        self.timeouts: list[float] = []

    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        self.requests.append(request)
        self.timeouts.append(timeout_seconds)
        index = len(self.requests) - 1
        if self._clock is not None and index < len(self._consume_seconds):
            self._clock.advance(self._consume_seconds[index])
        if self._fatal_barrier is not None:
            raise AnalyzerInfrastructureError(
                "worker_reap",
                _cleanup_safety_barrier=self._fatal_barrier,
            )
        kind = self._kinds.pop(0) if self._kinds else _WorkerRunKind.RESPONSE
        if kind is _WorkerRunKind.TIMEOUT:
            return _WorkerRun(kind, duration_ms=1)
        return _WorkerRun(
            kind,
            duration_ms=1,
            response=_execute_worker(request),
        )


class _DeferredProcess:
    def __init__(self) -> None:
        self.safe = False
        self.stdout = _DeferredStdout()
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_timeouts: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout)
        if not self.safe:
            raise subprocess.TimeoutExpired("PRIVATE command", timeout)
        return 0

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1

    def poll(self) -> int | None:
        return 0 if self.safe else None


class _DeferredStdout:
    def read(self, _size: int) -> None:
        return None

    def close(self) -> None:
        pass


class _FFmpegTerminationPreprocessing(_SnapshotBoundTestComponent):
    def __init__(self) -> None:
        super().__init__()
        self._tool = _FFmpegPreprocessingTool(executable="ffmpeg", timeout_seconds=1.0)

    def prepare(
        self,
        request: PreprocessingRequest,
        requirements: PreprocessingRequirements,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
    ) -> PreparedMedia:
        del requirements
        assert remaining_timeout_seconds is not None
        artifact_ref = request.artifact_registry.register(
            "ffmpeg_output",
            "preprocessing/ffmpeg/output.png",
        )

        request.source_file_ref.with_local_source_path(
            lambda source: request.artifact_registry.with_local_artifact_path(
                artifact_ref,
                lambda target: self._tool.sampled_frame(
                    source,
                    target,
                    timestamp_seconds=0.0,
                    artifact_budget=request.artifact_budget,
                    timeout_seconds=remaining_timeout_seconds(),
                ),
            )
        )
        raise AssertionError("unreapable FFmpeg unexpectedly completed")


class _ForbiddenRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, request: _WorkerRequest, timeout_seconds: float) -> NoReturn:
        del request, timeout_seconds
        self.calls += 1
        raise AssertionError("analyzer worker must not start")


class _LockProbeOrchestrator(_SnapshotBoundTestComponent):
    def __init__(self, lock_probe: Callable[[], None]) -> None:
        super().__init__()
        self._lock_probe = lock_probe

    def preprocessing_requirements(self, media_type: MediaType) -> PreprocessingRequirements:
        del media_type
        return PreprocessingRequirements()

    def execute(
        self,
        prepared_media: PreparedMedia,
        validated_file: ValidatedFileDescriptor,
        artifact_registry: WorkspaceArtifactRegistry,
        *,
        remaining_timeout_seconds: Callable[[], float] | None = None,
        result_callback: Callable[[AnalyzerResult], None] | None = None,
    ) -> tuple[AnalyzerResult, ...]:
        del prepared_media, validated_file, artifact_registry, result_callback
        assert remaining_timeout_seconds is not None
        remaining_timeout_seconds()
        self._lock_probe()
        return ()


def _config(
    root: Path,
    *,
    media_type: MediaType = MediaType.IMAGE,
    enabled: list[str] | None = None,
    processing_timeout_seconds: int = 10,
    analyzer_timeout_seconds: int = 8,
    continue_on_failure: bool = True,
) -> AppConfig:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(root)
    raw["limits"]["processing_timeout_seconds"] = processing_timeout_seconds
    for configured_media_type in MediaType:
        raw["analyzers"][configured_media_type.value]["enabled"] = []
    raw["analyzers"][media_type.value]["enabled"] = enabled or []
    raw["analyzers"]["defaults"]["timeout_seconds"] = analyzer_timeout_seconds
    raw["analyzers"]["defaults"]["continue_on_error"] = continue_on_failure
    raw["error_handling"]["continue_if_analyzer_fails"] = continue_on_failure
    return AppConfig.model_validate(raw)


def _descriptor(analysis_id: str) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name=f"{analysis_id}.png",
        extension="png",
        declared_mime_type="image/png",
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=6,
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


def _claimed_task(
    root: Path,
    config: AppConfig,
    *,
    analysis_id: str = "d" * 32,
    registry: TaskRegistry | None = None,
) -> tuple[AnalysisTask, TaskRegistry]:
    owner = LocalTemporaryInputOwner(root)
    owned_source = owner.create(analysis_id)
    owner.ingest(owned_source, BytesIO(b"source"), 100)
    accepted_source = owner.transfer(owned_source)
    descriptor = _descriptor(analysis_id)
    validation = ValidationResult(
        accepted=True,
        checks=[],
        errors=[],
        validated_file=descriptor,
    )
    task = AnalysisTask(
        context=AnalysisContext(
            analysis_id=analysis_id,
            created_at=_CREATED_AT,
            status=AnalysisStatus.QUEUED,
            stage=ProcessingStage.REGISTERED,
            source=SourceContext(channel=SourceChannel.API),
            workspace_path=root / analysis_id,
            media_type=MediaType.IMAGE,
            config_snapshot_id=config_snapshot_fingerprint(config),
        ),
        validation=validation,
        validated_file=descriptor,
        accepted_source=accepted_source,
        artifacts=WorkspaceArtifactRegistry(root / analysis_id),
    )
    active_registry = registry or TaskRegistry()
    active_registry.reserve(task)
    active_registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.ROUTING,
    )
    active_registry.bind_route(analysis_id, MediaType.IMAGE)
    active_registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.QUEUED,
    )
    active_registry.mark_enqueued(analysis_id, _CREATED_AT)
    active_registry.claim(analysis_id, _CREATED_AT)
    return task, active_registry


def _service(
    config: AppConfig,
    registry: TaskRegistry,
    preprocessing: object,
    *,
    runner: _WorkerRunner | None = None,
    monotonic: Callable[[], float],
) -> Stage5ExecutionService:
    if isinstance(preprocessing, _SnapshotBoundTestComponent):
        preprocessing._bind_config(config)
    analyzer_registry = AnalyzerRegistry(config, _framework_test_registrations())
    orchestrator = (
        AnalyzerOrchestrator(analyzer_registry)
        if runner is None
        else AnalyzerOrchestrator(analyzer_registry, runner=runner)
    )
    return Stage5ExecutionService(
        config=config,
        registry=registry,
        preprocessing=cast(PreprocessingDispatcher, preprocessing),
        orchestrator=orchestrator,
        monotonic=monotonic,
    )


def _write_artifact(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"artifact")


def _cleanup_task(task: AnalysisTask) -> None:
    task.artifacts.cleanup_once()
    if not task.accepted_source.is_released:
        task.accepted_source.cleanup()


def _assert_registry_unlocked(registry: TaskRegistry, analysis_id: str) -> None:
    completed: list[bool] = []

    def read_snapshot() -> None:
        registry.snapshot(analysis_id)
        completed.append(True)

    thread = Thread(target=read_snapshot)
    thread.start()
    thread.join(timeout=1.0)
    assert not thread.is_alive()
    assert completed == [True]


def _failure_result(
    analyzer_id: str,
    status: AnalyzerStatus,
) -> AnalyzerResult:
    definition = next(
        registration
        for registration in _framework_test_registrations()
        if registration.analyzer_id == analyzer_id
    )
    return AnalyzerResult(
        analyzer_id=analyzer_id,
        analyzer_version=definition.analyzer_version,
        media_type=MediaType.IMAGE,
        group=definition.group,
        status=status,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=1,
        score=None,
        score_name=None,
        summary="Analyzer failed safely.",
        raw_metrics={},
        candidate_findings=[],
        warnings=[],
        errors=[
            ErrorDetail(
                code=("analyzer_timeout" if status is AnalyzerStatus.TIMEOUT else "analyzer_error"),
                category="analyzer",
                message="Analyzer failed safely.",
                retryable=True,
                analyzer_id=analyzer_id,
            )
        ],
    )


@pytest.mark.parametrize(
    (
        "media_key",
        "media_type",
        "original_name",
        "declared_content_type",
        "analyzer_id",
        "required_artifact_types",
    ),
    [
        (
            "png",
            MediaType.IMAGE,
            "sample.png",
            "image/png",
            "fake_image_analyzer",
            {"normalized_image"},
        ),
        (
            "wav",
            MediaType.AUDIO,
            "sample.wav",
            "audio/wav",
            "fake_audio_analyzer",
            {"normalized_audio", "audio_fragment", "spectrogram"},
        ),
        (
            "mp4",
            MediaType.VIDEO,
            "sample.mp4",
            "video/mp4",
            "fake_video_analyzer",
            {"sampled_frame"},
        ),
    ],
)
def test_integrated_stage3_stage4_stage5_production_path(
    tmp_path: Path,
    media_files: dict[str, Path],
    media_key: str,
    media_type: MediaType,
    original_name: str,
    declared_content_type: str,
    analyzer_id: str,
    required_artifact_types: set[str],
) -> None:
    analysis_id = media_type.value[0] * 32
    root = tmp_path / media_type.value / "temp"
    config = _config(
        root,
        media_type=media_type,
        enabled=[analyzer_id],
        processing_timeout_seconds=30,
        analyzer_timeout_seconds=10,
    )
    lifecycle_clock = AuthoritativeLifecycleClock(_IncrementingClock())
    registry = _RecordingRegistry()
    queue = DeterministicTaskQueue()
    executor = Stage5ExecutionService(
        config=config,
        registry=registry,
        preprocessing=PreprocessingDispatcher(config),
        orchestrator=AnalyzerOrchestrator(
            AnalyzerRegistry(config, _framework_test_registrations())
        ),
    )
    receiver = Stage4TaskReceiver(
        config=config,
        clock=lifecycle_clock,
        registry=registry,
        router=MediaRouter(dict.fromkeys(MediaType, executor)),
        queue=queue,
    )
    owner = LocalTemporaryInputOwner(root)
    intake = FileIntakeService(
        controlled_intake=ControlledIntakeService(
            config=config,
            analysis_id_generator=_FixedIdGenerator(analysis_id),
            clock=lifecycle_clock,
            temporary_input_owner=owner,
        ),
        validator=FileValidator(config=config, temporary_input_owner=owner),
        temporary_input_owner=owner,
        accepted_receiver=receiver,
        clock=lifecycle_clock,
    )

    accepted = intake.process(
        BytesIO(media_files[media_key].read_bytes()),
        original_name=original_name,
        declared_content_type=declared_content_type,
        source=SourceContext(channel=SourceChannel.API),
    )
    assert isinstance(accepted, Stage3Accepted)
    task = registry._tasks[analysis_id]
    final = Stage4LifecycleRunner(
        config=config,
        clock=lifecycle_clock,
        registry=registry,
        queue=queue,
    ).run_next()

    assert final is not None
    assert final.status is AnalysisStatus.COMPLETED
    assert final.stage is ProcessingStage.FINISHED
    assert final.cleanup is not None and final.cleanup.original_file_deleted
    assert final.cleanup.intermediate_files_deleted
    assert not hasattr(final, "stage5_data")
    assert task.stage5_data is not None
    assert task.stage5_data.prepared_media.media_type is media_type
    assert [result.analyzer_id for result in task.stage5_data.analyzer_results] == [analyzer_id]
    assert required_artifact_types <= {
        artifact.artifact_type for artifact in task.stage5_data.prepared_media.artifacts
    }
    assert registry.stage5_events == [
        "prepared",
        "analysis",
        f"result:{analyzer_id}",
    ]
    assert task.accepted_source.is_released
    assert all(not path.exists() for path in task.artifacts.cleanup_obligations())


def test_state_machine_and_registry_enforce_stage5_publication_order(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path / "temp")
    task, registry = _claimed_task(tmp_path / "temp", config)
    preprocessing = _RecordingPreprocessing()
    request = PreprocessingRequest(
        analysis_id=task.context.analysis_id,
        validated_file=task.validated_file,
        source_file_ref=PreparedSourceRef(task.accepted_source),
        artifact_registry=task.artifacts,
        artifact_budget=_GeneratedArtifactBudget(
            _ConfigSnapshot.capture(config),
            task.validated_file.media_type,
        ),
    )
    prepared = preprocessing.prepare(
        request,
        PreprocessingRequirements(),
        remaining_timeout_seconds=lambda: 1.0,
    )
    result = _failure_result("fake_error_analyzer", AnalyzerStatus.ERROR)

    state_machine_task = copy(task)
    AnalysisStateMachine().transition(
        state_machine_task,
        status=AnalysisStatus.RUNNING,
        stage=ProcessingStage.ANALYSIS,
    )
    assert state_machine_task.context.stage is ProcessingStage.ANALYSIS
    with pytest.raises(LifecycleStateError):
        AnalysisStateMachine().transition(
            state_machine_task,
            status=AnalysisStatus.COMPLETED,
            stage=ProcessingStage.FINISHED,
            finished_at=_CREATED_AT,
        )

    with pytest.raises(LifecycleStateError):
        registry.start_stage5_analysis(task)
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(task, result)
    with pytest.raises(LifecycleStateError):
        registry.transition(
            task.context.analysis_id,
            status=AnalysisStatus.RUNNING,
            stage=ProcessingStage.ANALYSIS,
        )

    registry.publish_stage5_prepared(task, prepared)
    with pytest.raises(LifecycleStateError):
        registry.publish_stage5_prepared(task, prepared)
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(task, result)
    registry.start_stage5_analysis(task)
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(
            task,
            result.model_copy(update={"summary": "x" * 70_000}),
        )
    assert task.stage5_data is not None
    assert task.stage5_data.analyzer_results == ()
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(
            task,
            result.model_copy(update={"media_type": MediaType.AUDIO}),
        )
    registry.append_stage5_analyzer_result(task, result)
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(task, result)
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(copy(task), result)

    assert task.stage5_data is not None
    assert task.stage5_data.prepared_media is prepared
    assert registry._read_stage5_analyzer_results(task) == (result,)

    registry.record_outcome(task.context.analysis_id, TaskExecutionOutcome.completed())
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(task, result)
    final = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    ).settle_terminal(task.context.analysis_id)
    assert final.stage is ProcessingStage.FINISHED
    with pytest.raises(LifecycleStateError):
        registry.publish_stage5_prepared(task, prepared)
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(task, result)
    assert registry._read_stage5_analyzer_results(task) == (result,)


def _start_result_publication(task: AnalysisTask, registry: TaskRegistry) -> None:
    registry.publish_stage5_prepared(
        task,
        PreparedMedia(
            analysis_id=task.context.analysis_id,
            media_type=task.context.media_type,
            source_file_ref=PreparedSourceRef(task.accepted_source),
        ),
    )
    registry.start_stage5_analysis(task)


def _mutate_nested_result(result: AnalyzerResult) -> None:
    result.summary = "Changed summary"
    metrics = cast(dict[str, object], result.raw_metrics["nested"])
    cast(list[object], metrics["values"]).append({"changed": True})
    metrics["added"] = ["changed"]
    finding = cast(dict[str, object], result.candidate_findings[0])
    cast(list[object], finding["values"]).append({"changed": True})
    result.candidate_findings.append({"added": ["changed"]})
    result.warnings.append("Changed warning")
    result.errors[0].message = "Changed error"
    details = cast(list[object], result.errors[0].safe_details["values"])
    details.append({"changed": True})
    result.errors.append(result.errors[0].model_copy(deep=True))


@pytest.mark.parametrize("mutate_original", [True, False], ids=["original", "reader"])
@pytest.mark.parametrize("fatal_outcome", [False, True], ids=["completed", "failed"])
def test_authoritative_results_remain_immutable_through_terminal_settlement(
    tmp_path: Path,
    mutate_original: bool,
    fatal_outcome: bool,
) -> None:
    root = tmp_path / "temp"
    config = _config(root)
    task, registry = _claimed_task(root, config)
    assert registry._read_stage5_analyzer_results(task) == ()
    _start_result_publication(task, registry)
    original = _failure_result("fake_error_analyzer", AnalyzerStatus.ERROR)
    original.raw_metrics = {"nested": {"values": [1, {"signal": [0.42]}]}}
    original.candidate_findings = [{"values": [{"signal": [0.42]}]}]
    original.warnings = ["Initial warning"]
    original.errors[0].safe_details = {"values": [{"signal": [0.42]}]}
    expected = original.model_dump(mode="json")
    payload = _serialize_stage5_analyzer_result(original)
    registry.append_stage5_analyzer_result(task, original)
    assert task.stage5_data is not None
    stored_data = task.stage5_data
    stored = stored_data.analyzer_results[0]
    assert isinstance(stored, _StoredAnalyzerResult)
    assert isinstance(stored.canonical_json, bytes)
    assert stored.canonical_json == payload
    assert not any(
        isinstance(getattr(stored, model_field.name), AnalyzerResult)
        for model_field in fields(stored)
    )
    with pytest.raises(FrozenInstanceError):
        stored.canonical_json = b"changed"
    with pytest.raises(TypeError, match="stored analyzer results"):
        Stage5TaskData(
            prepared_media=stored_data.prepared_media,
            analyzer_results=cast(tuple[_StoredAnalyzerResult, ...], (original,)),
        )

    for phase in (ProcessingStage.ANALYSIS, ProcessingStage.CLEANUP, ProcessingStage.FINISHED):
        if phase is ProcessingStage.CLEANUP:
            outcome = (
                TaskExecutionOutcome.failed(
                    ErrorDetail(
                        code="internal_error",
                        category="internal",
                        message="Later infrastructure failure.",
                        retryable=True,
                    )
                )
                if fatal_outcome
                else TaskExecutionOutcome.completed()
            )
            registry.record_outcome(task.context.analysis_id, outcome)
        elif phase is ProcessingStage.FINISHED:
            Stage4TaskProcessor(
                config=config,
                clock=AuthoritativeLifecycleClock(
                    _IncrementingClock(_CREATED_AT + timedelta(minutes=1))
                ),
                registry=registry,
            ).settle_terminal(task.context.analysis_id)
        assert task.context.stage is phase
        first_read = registry._read_stage5_analyzer_results(task)[0]
        second_read = registry._read_stage5_analyzer_results(task)[0]
        assert first_read is not second_read
        assert first_read.model_dump(mode="json") == expected
        _mutate_nested_result(original if mutate_original else first_read)
        assert second_read.model_dump(mode="json") == expected
        assert registry._read_stage5_analyzer_results(task)[0].model_dump(mode="json") == expected
        assert task.stage5_data is stored_data
        assert stored.canonical_json == payload
        snapshot = registry.snapshot(task.context.analysis_id)
        assert not {"stage5_data", "analyzer_results", "canonical_json"} & {
            model_field.name for model_field in fields(snapshot)
        }
        assert "Initial warning" not in repr(snapshot)
        with pytest.raises(LifecycleStateError):
            registry._read_stage5_analyzer_results(copy(task))

    assert task.context.status is (
        AnalysisStatus.FAILED if fatal_outcome else AnalysisStatus.COMPLETED
    )


@pytest.mark.parametrize("suffix", ["x", "Ж", "🙂"])
def test_storage_reuses_exact_r2_result_bytes_at_utf8_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
) -> None:
    root = tmp_path / "temp"
    task, registry = _claimed_task(root, _config(root))
    _start_result_publication(task, registry)
    result = _failure_result("fake_image_analyzer", AnalyzerStatus.COMPLETED)
    result.errors.clear()
    result.score = 0.42
    result.score_name = "contract_signal"
    result.raw_metrics = {"nested": ["Ж", {"signal": 0.42}]}
    result.candidate_findings = [{"values": ["🙂", 0.42]}]
    result.summary = suffix
    padding = _MAX_STAGE5_ANALYZER_RESULT_BYTES - len(_serialize_stage5_analyzer_result(result))
    result.summary += "x" * padding
    payload = _serialize_stage5_analyzer_result(result)
    response = _encode_response(_WorkerResponseKind.RESULT, result=result)
    assert len(payload) == _MAX_STAGE5_ANALYZER_RESULT_BYTES
    assert len(response) == _MAX_RESPONSE_BYTES
    assert response == b'{"kind":"result","result":' + payload + b"}"
    calls: list[bytes] = []

    def encode_unlocked(value: AnalyzerResult) -> bytes:
        _assert_registry_unlocked(registry, task.context.analysis_id)
        encoded = _serialize_stage5_analyzer_result(value)
        calls.append(encoded)
        return encoded

    monkeypatch.setattr(execution_module, "_serialize_stage5_analyzer_result", encode_unlocked)
    registry.append_stage5_analyzer_result(task, result)
    assert calls == [payload]
    assert task.stage5_data is not None
    stored_data = task.stage5_data
    assert stored_data.analyzer_results[0].canonical_json == payload
    materialize = AnalyzerResult.model_validate_json

    def materialize_unlocked(_cls: type[AnalyzerResult], value: bytes) -> AnalyzerResult:
        _assert_registry_unlocked(registry, task.context.analysis_id)
        return materialize(value)

    monkeypatch.setattr(AnalyzerResult, "model_validate_json", classmethod(materialize_unlocked))
    assert registry._read_stage5_analyzer_results(task) == (result,)
    assert (
        _serialize_stage5_analyzer_result(registry._read_stage5_analyzer_results(task)[0])
        == payload
    )

    oversized = result.model_copy(update={"analyzer_id": "fake_error_analyzer"})
    # Keep the same identity byte length, then exceed the result bound by one byte.
    oversized.summary += "x" * (len(result.analyzer_id) - len(oversized.analyzer_id) + 1)
    with pytest.raises(_Stage5AnalyzerResultSizeError):
        _encode_response(_WorkerResponseKind.RESULT, result=oversized)
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(task, oversized)
    assert task.stage5_data is stored_data
    assert registry._read_stage5_analyzer_results(task) == (result,)
    _cleanup_task(task)


@pytest.mark.parametrize("invalid", ["status", "nested", "type"])
def test_publication_revalidates_mutated_canonical_results_without_state_change(
    tmp_path: Path,
    invalid: str,
) -> None:
    root = tmp_path / "temp"
    task, registry = _claimed_task(root, _config(root))
    _start_result_publication(task, registry)
    result = _failure_result("fake_error_analyzer", AnalyzerStatus.ERROR)
    if invalid == "status":
        result.errors.clear()
    elif invalid == "nested":
        result.raw_metrics["nested"] = [float("nan")]
    else:
        result = cast(AnalyzerResult, object())
    before = task.stage5_data
    with pytest.raises(LifecycleStateError):
        registry.append_stage5_analyzer_result(task, result)
    assert task.stage5_data is before
    assert registry._read_stage5_analyzer_results(task) == ()
    _cleanup_task(task)


def test_registry_rejects_stale_and_foreign_stage5_capabilities(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    config = _config(root)
    task, registry = _claimed_task(root, config)
    stale = AnalysisTask(
        context=task.context,
        validation=task.validation,
        validated_file=task.validated_file,
        accepted_source=task.accepted_source,
        artifacts=task.artifacts,
        queued_at=task.queued_at,
        execution_claimed=True,
    )
    with pytest.raises(LifecycleStateError):
        registry.validate_stage5_execution(stale)

    foreign_owner = LocalTemporaryInputOwner(tmp_path / "foreign")
    foreign_owned = foreign_owner.create(task.context.analysis_id)
    foreign_owner.ingest(foreign_owned, BytesIO(b"foreign"), 100)
    foreign_source = foreign_owner.transfer(foreign_owned)
    foreign_source_prepared = PreparedMedia(
        analysis_id=task.context.analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=PreparedSourceRef(foreign_source),
    )
    with pytest.raises(LifecycleStateError):
        registry.publish_stage5_prepared(task, foreign_source_prepared)

    foreign_artifacts = WorkspaceArtifactRegistry(tmp_path / "foreign-artifacts")
    foreign_ref = foreign_artifacts.register("foreign_artifact", "foreign.bin")
    foreign_artifact_prepared = PreparedMedia(
        analysis_id=task.context.analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=PreparedSourceRef(task.accepted_source),
        artifacts=(
            PreparedArtifact(
                artifact_id="foreign_artifact",
                artifact_type="normalized_input",
                artifact_ref=foreign_ref,
                format="bin",
            ),
        ),
    )
    with pytest.raises(LifecycleStateError):
        registry.publish_stage5_prepared(task, foreign_artifact_prepared)

    foreign_artifacts.cleanup_once()
    foreign_source.cleanup()
    _cleanup_task(task)


@pytest.mark.parametrize(
    ("first_analyzer", "first_kind", "expected_status"),
    [
        ("fake_error_analyzer", _WorkerRunKind.RESPONSE, AnalyzerStatus.ERROR),
        ("fake_hang_analyzer", _WorkerRunKind.TIMEOUT, AnalyzerStatus.TIMEOUT),
    ],
)
@pytest.mark.parametrize("continue_on_failure", [True, False])
def test_individual_analyzer_failures_remain_results_and_execution_completes(
    tmp_path: Path,
    first_analyzer: str,
    first_kind: _WorkerRunKind,
    expected_status: AnalyzerStatus,
    continue_on_failure: bool,
) -> None:
    root = tmp_path / expected_status.value
    config = _config(
        root,
        enabled=[first_analyzer, "fake_image_analyzer"],
        continue_on_failure=continue_on_failure,
    )
    registry = _RecordingRegistry()
    task, _registry = _claimed_task(root, config, registry=registry)
    runner = _SequencedRunner(first_kind, _WorkerRunKind.RESPONSE)
    preprocessing = _RecordingPreprocessing(create_artifact=True)
    outcome = _service(
        config,
        registry,
        preprocessing,
        runner=runner,
        monotonic=_ManualMonotonic(),
    ).execute(task)

    assert outcome == TaskExecutionOutcome.completed()
    assert task.stage5_data is not None
    results = registry._read_stage5_analyzer_results(task)
    assert [result.status for result in results] == [
        expected_status,
        AnalyzerStatus.COMPLETED if continue_on_failure else AnalyzerStatus.SKIPPED,
    ]
    assert [result.analyzer_id for result in results] == [first_analyzer, "fake_image_analyzer"]
    assert registry.stage5_events == [
        "prepared",
        "analysis",
        f"result:{first_analyzer}",
        "result:fake_image_analyzer",
    ]
    assert len(runner.requests) == (2 if continue_on_failure else 1)
    assert preprocessing.calls == len(preprocessing.requirements) == 1
    assert [stored.canonical_json for stored in task.stage5_data.analyzer_results] == [
        _serialize_stage5_analyzer_result(result) for result in results
    ]
    _cleanup_task(task)


def test_preprocessing_failure_uses_stage4_terminal_cleanup(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(root)
    task, registry = _claimed_task(root, config)
    service = _service(
        config,
        registry,
        _RecordingPreprocessing(fail=True),
        monotonic=_ManualMonotonic(),
    )
    processor = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    )

    final = processor.execute_claimed(task, service)

    assert final.status is AnalysisStatus.FAILED
    assert final.stage is ProcessingStage.FINISHED
    assert final.errors[0].code == "internal_error"
    assert final.errors[0].category == "internal"
    assert final.cleanup is not None and final.cleanup.intermediate_files_deleted
    assert task.stage5_data is None
    assert task.accepted_source.is_released
    assert all(not path.exists() for path in task.artifacts.cleanup_obligations())


def test_preprocessing_resource_limit_is_safe_non_retryable_and_prevents_worker(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(root, enabled=["fake_image_analyzer"])
    task, registry = _claimed_task(root, config)
    runner = _ForbiddenRunner()

    outcome = _service(
        config,
        registry,
        _RecordingPreprocessing(resource_limit=True),
        runner=runner,
        monotonic=_ManualMonotonic(),
    ).execute(task)

    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.errors[0].code == "stage5_resource_limit"
    assert outcome.errors[0].category == "resource_limit"
    assert outcome.errors[0].retryable is False
    assert outcome.errors[0].safe_details == {
        "phase": "preprocessing",
        "limit": "test_budget",
    }
    assert runner.calls == 0
    assert task.stage5_data is None
    _cleanup_task(task)


def test_exhausted_deadline_has_precedence_over_resource_limit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(root, processing_timeout_seconds=5)
    task, registry = _claimed_task(root, config)
    monotonic = _ManualMonotonic()

    outcome = _service(
        config,
        registry,
        _RecordingPreprocessing(
            clock=monotonic,
            consume_seconds=5,
            resource_limit=True,
        ),
        monotonic=monotonic,
    ).execute(task)

    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.errors[0].code == "processing_timeout"
    assert outcome.errors[0].category == "processing"
    _cleanup_task(task)


def test_stage5_rejects_a_different_config_snapshot_before_preprocessing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    task_config = _config(root)
    task, registry = _claimed_task(root, task_config)
    different_config = task_config.model_copy(deep=True)
    different_config.server.port += 1
    preprocessing = _RecordingPreprocessing()

    outcome = _service(
        different_config,
        registry,
        preprocessing,
        monotonic=_ManualMonotonic(),
    ).execute(task)

    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.errors[0].code == "internal_error"
    assert outcome.errors[0].category == "internal"
    assert outcome.errors[0].safe_details == {"phase": "configuration_snapshot"}
    assert preprocessing.calls == 0
    assert task.context.stage is ProcessingStage.PREPROCESSING
    assert task.stage5_data is None
    _cleanup_task(task)


def test_equal_distinct_configs_share_one_stage5_snapshot_identity(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path / "temp")
    dispatcher_config = AppConfig.model_validate(config.model_dump(mode="python"))
    registry_config = AppConfig.model_validate(config.model_dump(mode="python"))

    service = Stage5ExecutionService(
        config=config,
        registry=TaskRegistry(),
        preprocessing=PreprocessingDispatcher(dispatcher_config),
        orchestrator=AnalyzerOrchestrator(
            AnalyzerRegistry(registry_config, _framework_test_registrations())
        ),
    )

    assert service._config_snapshot.snapshot_id == config_snapshot_fingerprint(config)


def test_stage5_constructor_rejects_mixed_dispatcher_snapshot(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path / "temp")
    different = config.model_copy(deep=True)
    different.preprocessing.audio.fragment_duration_seconds += 1

    with pytest.raises(ValueError, match="different config snapshots"):
        Stage5ExecutionService(
            config=config,
            registry=TaskRegistry(),
            preprocessing=PreprocessingDispatcher(different),
            orchestrator=AnalyzerOrchestrator(
                AnalyzerRegistry(config, _framework_test_registrations())
            ),
        )


def test_stage5_constructor_rejects_mixed_analyzer_snapshot(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path / "temp")
    different = config.model_copy(deep=True)
    different.analyzers.defaults.timeout_seconds += 1

    with pytest.raises(ValueError, match="different config snapshots"):
        Stage5ExecutionService(
            config=config,
            registry=TaskRegistry(),
            preprocessing=PreprocessingDispatcher(config),
            orchestrator=AnalyzerOrchestrator(
                AnalyzerRegistry(different, _framework_test_registrations())
            ),
        )


def test_fatal_analyzer_infrastructure_failure_cleans_after_safety_confirmation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(root, enabled=["fake_image_analyzer"])
    task, registry = _claimed_task(root, config)
    barrier = _ControlledSafetyBarrier(safe=True)
    service = _service(
        config,
        registry,
        _RecordingPreprocessing(create_artifact=True),
        runner=_SequencedRunner(fatal_barrier=barrier),
        monotonic=_ManualMonotonic(),
    )
    final = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    ).execute_claimed(task, service)

    assert final.status is AnalysisStatus.FAILED
    assert final.errors[0].code == "internal_error"
    assert final.errors[0].category == "internal"
    assert final.cleanup is not None and final.cleanup.intermediate_files_deleted
    assert task.stage5_data is not None
    assert task.stage5_data.analyzer_results == ()
    assert task.accepted_source.is_released
    assert barrier.calls == 1


def test_unreapable_worker_defers_cleanup_until_recovery_confirms_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    config = _config(root, enabled=["fake_image_analyzer"])
    task, registry = _claimed_task(root, config)
    barrier = _ControlledSafetyBarrier(safe=False)
    barrier.lock_probe = lambda: _assert_registry_unlocked(
        registry,
        task.context.analysis_id,
    )
    service = _service(
        config,
        registry,
        _RecordingPreprocessing(create_artifact=True),
        runner=_SequencedRunner(fatal_barrier=barrier),
        monotonic=_ManualMonotonic(),
    )
    processor = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    )
    cleanup_calls = 0
    settlement_events: list[str] = []
    real_cleanup = processor._cleanup.cleanup_task
    real_mark_facts_ready = registry.mark_terminal_facts_ready
    real_finalize = registry.finalize_terminal_settlement

    def count_cleanup(*args: object, **kwargs: object):
        nonlocal cleanup_calls
        cleanup_calls += 1
        return real_cleanup(*args, **kwargs)

    def record_facts_ready(*args: object, **kwargs: object) -> None:
        real_mark_facts_ready(*args, **kwargs)
        settlement_events.append("fact_ready")

    def record_finished(*args: object, **kwargs: object) -> None:
        assert settlement_events == ["fact_ready"]
        real_finalize(*args, **kwargs)
        settlement_events.append("finished")

    monkeypatch.setattr(processor._cleanup, "cleanup_task", count_cleanup)
    monkeypatch.setattr(registry, "mark_terminal_facts_ready", record_facts_ready)
    monkeypatch.setattr(registry, "finalize_terminal_settlement", record_finished)

    first = processor.execute_claimed(task, service)
    artifact_paths = task.artifacts.cleanup_obligations()

    assert first.status is AnalysisStatus.FAILED
    assert first.stage is ProcessingStage.CLEANUP
    assert first.finished_at is None
    assert first.cleanup is None
    assert first.errors[0].code == "internal_error"
    assert first.errors[0].category == "internal"
    assert barrier.calls == 1
    assert cleanup_calls == 0
    assert settlement_events == []
    assert not task.accepted_source.is_released
    assert artifact_paths and all(path.is_file() for path in artifact_paths)
    assert registry.recoverable_terminal_tasks() == (task.context.analysis_id,)

    second = processor.settle_terminal(task.context.analysis_id)

    assert second.status is AnalysisStatus.FAILED
    assert second.stage is ProcessingStage.CLEANUP
    assert second.finished_at is None
    assert second.cleanup is None
    assert barrier.calls == 2
    assert cleanup_calls == 0
    assert settlement_events == []
    assert not task.accepted_source.is_released
    assert all(path.is_file() for path in artifact_paths)

    barrier.safe = True
    final = processor.settle_terminal(task.context.analysis_id)

    assert final.status is AnalysisStatus.FAILED
    assert final.stage is ProcessingStage.FINISHED
    assert final.finished_at is not None
    assert final.cleanup is not None
    assert final.cleanup.finished_at == final.finished_at
    assert barrier.calls == 3
    assert cleanup_calls == 1
    assert settlement_events == ["fact_ready", "finished"]
    assert task.accepted_source.is_released
    assert all(not path.exists() for path in artifact_paths)
    assert registry.recoverable_terminal_tasks() == ()


def test_cleanup_safety_confirmation_exception_defers_and_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    config = _config(root, enabled=["fake_image_analyzer"])
    task, registry = _claimed_task(root, config)
    barrier = _ControlledSafetyBarrier(safe=True, raise_once=True)
    barrier.lock_probe = lambda: _assert_registry_unlocked(
        registry,
        task.context.analysis_id,
    )
    service = _service(
        config,
        registry,
        _RecordingPreprocessing(create_artifact=True),
        runner=_SequencedRunner(fatal_barrier=barrier),
        monotonic=_ManualMonotonic(),
    )
    processor = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    )
    cleanup_calls = 0
    real_cleanup = processor._cleanup.cleanup_task

    def count_cleanup(*args: object, **kwargs: object):
        nonlocal cleanup_calls
        cleanup_calls += 1
        return real_cleanup(*args, **kwargs)

    monkeypatch.setattr(processor._cleanup, "cleanup_task", count_cleanup)

    deferred = processor.execute_claimed(task, service)
    artifact_paths = task.artifacts.cleanup_obligations()

    assert deferred.status is AnalysisStatus.FAILED
    assert deferred.stage is ProcessingStage.CLEANUP
    assert deferred.finished_at is None
    assert deferred.cleanup is None
    assert "PRIVATE" not in repr(deferred)
    assert barrier.calls == 1
    assert cleanup_calls == 0
    assert not task.accepted_source.is_released
    assert artifact_paths and all(path.is_file() for path in artifact_paths)
    assert registry.recoverable_terminal_tasks() == (task.context.analysis_id,)

    final = processor.settle_terminal(task.context.analysis_id)

    assert final.status is AnalysisStatus.FAILED
    assert final.stage is ProcessingStage.FINISHED
    assert final.cleanup is not None
    assert barrier.calls == 2
    assert cleanup_calls == 1
    assert task.accepted_source.is_released
    assert all(not path.exists() for path in artifact_paths)
    assert registry.recoverable_terminal_tasks() == ()


def test_ffmpeg_termination_barrier_defers_stage4_cleanup_and_beats_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    config = _config(root, processing_timeout_seconds=5)
    task, registry = _claimed_task(root, config)
    process = _DeferredProcess()
    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: process,
    )
    monkeypatch.setattr(
        bounded_process_module,
        "_make_stdout_nonblocking",
        lambda _stdout: None,
    )
    service = _service(
        config,
        registry,
        _FFmpegTerminationPreprocessing(),
        monotonic=_ManualMonotonic(),
    )
    processor = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    )

    first = processor.execute_claimed(task, service)

    assert first.status is AnalysisStatus.FAILED
    assert first.stage is ProcessingStage.CLEANUP
    assert first.finished_at is None
    assert first.cleanup is None
    assert first.errors[0].code == "internal_error"
    assert first.errors[0].category == "internal"
    assert task.errors[0].safe_details == {"phase": "preprocessing"}
    assert process.terminate_calls == 2
    assert process.kill_calls == 2
    assert not task.accepted_source.is_released
    assert registry.recoverable_terminal_tasks() == (task.context.analysis_id,)

    repeated = processor.settle_terminal(task.context.analysis_id)

    assert repeated.stage is ProcessingStage.CLEANUP
    assert repeated.cleanup is None
    assert process.terminate_calls == 3
    assert process.kill_calls == 3
    assert process.wait_timeouts
    assert all(timeout is not None and timeout <= 1.0 for timeout in process.wait_timeouts)
    assert not task.accepted_source.is_released

    process.safe = True
    final = processor.settle_terminal(task.context.analysis_id)

    assert final.status is AnalysisStatus.FAILED
    assert final.stage is ProcessingStage.FINISHED
    assert final.cleanup is not None
    assert final.cleanup.original_file_deleted
    assert final.cleanup.intermediate_files_deleted
    assert task.accepted_source.is_released


def test_overall_deadline_before_analysis_prevents_analyzer_and_cleans(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(
        root,
        enabled=["fake_image_analyzer"],
        processing_timeout_seconds=5,
    )
    registry = _RecordingRegistry()
    task, _registry = _claimed_task(root, config, registry=registry)
    monotonic = _ManualMonotonic()
    forbidden_runner = _ForbiddenRunner()
    service = _service(
        config,
        registry,
        _RecordingPreprocessing(clock=monotonic, consume_seconds=5),
        runner=forbidden_runner,
        monotonic=monotonic,
    )
    final = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    ).execute_claimed(task, service)

    assert final.status is AnalysisStatus.FAILED
    assert final.errors[0].code == "processing_timeout"
    assert final.errors[0].category == "processing"
    assert forbidden_runner.calls == 0
    assert registry.stage5_events == []
    assert task.stage5_data is None
    assert task.accepted_source.is_released


def test_single_deadline_caps_analyzers_and_stops_launch_between_them(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(
        root,
        enabled=["fake_image_analyzer", "fake_image_second_analyzer"],
        processing_timeout_seconds=10,
        analyzer_timeout_seconds=8,
    )
    registry = _RecordingRegistry()
    task, _registry = _claimed_task(root, config, registry=registry)
    monotonic = _ManualMonotonic()
    preprocessing = _RecordingPreprocessing(
        clock=monotonic,
        consume_seconds=3,
        create_artifact=True,
    )
    analyzer_runner = _SequencedRunner(
        _WorkerRunKind.RESPONSE,
        _WorkerRunKind.RESPONSE,
        clock=monotonic,
        consume_seconds=(7,),
    )
    service = _service(
        config,
        registry,
        preprocessing,
        runner=analyzer_runner,
        monotonic=monotonic,
    )
    final = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    ).execute_claimed(task, service)

    assert final.status is AnalysisStatus.FAILED
    assert final.errors[0].code == "processing_timeout"
    assert final.errors[0].category == "processing"
    assert preprocessing.remaining_at_entry == [10.0]
    assert analyzer_runner.timeouts == [7.0]
    assert len(analyzer_runner.requests) == 1
    assert task.stage5_data is not None
    assert [result.analyzer_id for result in task.stage5_data.analyzer_results] == [
        "fake_image_analyzer"
    ]
    assert registry.stage5_events == [
        "prepared",
        "analysis",
        "result:fake_image_analyzer",
    ]
    assert task.accepted_source.is_released


def test_single_deadline_decreases_between_successful_analyzers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(
        root,
        enabled=["fake_image_analyzer", "fake_image_second_analyzer"],
        processing_timeout_seconds=10,
        analyzer_timeout_seconds=8,
    )
    task, registry = _claimed_task(root, config)
    monotonic = _ManualMonotonic()
    analyzer_runner = _SequencedRunner(
        _WorkerRunKind.RESPONSE,
        _WorkerRunKind.RESPONSE,
        clock=monotonic,
        consume_seconds=(2,),
    )
    service = _service(
        config,
        registry,
        _RecordingPreprocessing(
            clock=monotonic,
            consume_seconds=3,
            create_artifact=True,
        ),
        runner=analyzer_runner,
        monotonic=monotonic,
    )
    final = Stage4TaskProcessor(
        config=config,
        clock=AuthoritativeLifecycleClock(_IncrementingClock(_CREATED_AT + timedelta(minutes=1))),
        registry=registry,
    ).execute_claimed(task, service)

    assert final.status is AnalysisStatus.COMPLETED
    assert final.stage is ProcessingStage.FINISHED
    assert analyzer_runner.timeouts == [7.0, 5.0]
    assert task.stage5_data is not None
    assert [result.analyzer_id for result in task.stage5_data.analyzer_results] == [
        "fake_image_analyzer",
        "fake_image_second_analyzer",
    ]
    assert task.accepted_source.is_released


def test_stage5_runs_filesystem_and_analyzer_work_without_registry_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    config = _config(root)
    task, registry = _claimed_task(root, config)

    def lock_probe() -> None:
        _assert_registry_unlocked(registry, task.context.analysis_id)

    preprocessing = _RecordingPreprocessing(
        create_artifact=True,
        lock_probe=lock_probe,
    )
    preprocessing._bind_config(config)
    orchestrator = _LockProbeOrchestrator(lock_probe)
    orchestrator._bind_config(config)
    service = Stage5ExecutionService(
        config=config,
        registry=registry,
        preprocessing=cast(PreprocessingDispatcher, preprocessing),
        orchestrator=cast(AnalyzerOrchestrator, orchestrator),
        monotonic=_ManualMonotonic(),
    )

    outcome = service.execute(task)

    assert outcome == TaskExecutionOutcome.completed()
    assert not task.accepted_source.is_released
    assert any(path.is_file() for path in task.artifacts.cleanup_obligations())
    _cleanup_task(task)


def test_stage5_service_does_not_expand_public_lifecycle_facade() -> None:
    assert not hasattr(lifecycle, "Stage5ExecutionService")
