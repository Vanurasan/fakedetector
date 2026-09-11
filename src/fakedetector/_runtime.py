"""Private production composition for the implemented analysis lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

from fakedetector.analyzers._catalog import _real_analyzer_registrations
from fakedetector.analyzers._orchestrator import AnalyzerOrchestrator
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.application import AnalysisApplicationService
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.core import AuthoritativeLifecycleClock, UtcClock, Uuid4AnalysisIdGenerator
from fakedetector.domain import MediaType
from fakedetector.intake import (
    ControlledIntakeService,
    FileIntakeService,
    FileValidator,
    LocalTemporaryInputOwner,
)
from fakedetector.lifecycle._stage5 import Stage5ExecutionService
from fakedetector.lifecycle._stage6 import Stage6FindingService
from fakedetector.lifecycle._stage7 import Stage7AssessmentService
from fakedetector.lifecycle.execution import MediaRouter, TaskRegistry
from fakedetector.lifecycle.receiver import Stage4TaskReceiver
from fakedetector.lifecycle.scheduler import BoundedLocalScheduler
from fakedetector.preprocessing._service import PreprocessingDispatcher
from fakedetector.repositories import JsonFileResultRepository
from fakedetector.result_finalization import ResultFinalizationService


@dataclass(frozen=True, slots=True)
class _ProductionRuntime:
    """Owned production services needed by current and future external adapters."""

    application_service: AnalysisApplicationService
    analyzer_registry: AnalyzerRegistry
    intake: FileIntakeService
    registry: TaskRegistry
    result_finalizer: ResultFinalizationService
    result_repository: JsonFileResultRepository
    scheduler: BoundedLocalScheduler


def _build_production_runtime(config: AppConfig) -> _ProductionRuntime:
    """Build the closed deterministic production graph from one config snapshot."""
    config_snapshot = _ConfigSnapshot.capture(config)
    captured_config = config_snapshot.materialize()
    clock = AuthoritativeLifecycleClock(UtcClock())
    task_registry = TaskRegistry()
    result_repository = JsonFileResultRepository(captured_config.result.directory)
    result_finalizer = ResultFinalizationService(
        config=captured_config,
        clock=clock,
        repository=result_repository,
    )
    analyzer_registry = AnalyzerRegistry(captured_config, _real_analyzer_registrations())
    executor = Stage5ExecutionService(
        config=captured_config,
        registry=task_registry,
        preprocessing=PreprocessingDispatcher(captured_config),
        orchestrator=AnalyzerOrchestrator(analyzer_registry),
        finding_service=Stage6FindingService(),
        assessment_service=Stage7AssessmentService(captured_config.risk_assessment),
    )
    scheduler = BoundedLocalScheduler(
        config=captured_config,
        clock=clock,
        registry=task_registry,
        result_finalizer=result_finalizer,
    )
    receiver = Stage4TaskReceiver(
        config=captured_config,
        clock=clock,
        registry=task_registry,
        router=MediaRouter(dict.fromkeys(MediaType, executor)),
        queue=scheduler,
    )
    temporary_input_owner = LocalTemporaryInputOwner(
        captured_config.temporary_storage.root_path
    )
    intake = FileIntakeService(
        controlled_intake=ControlledIntakeService(
            config=captured_config,
            analysis_id_generator=Uuid4AnalysisIdGenerator(),
            clock=clock,
            temporary_input_owner=temporary_input_owner,
        ),
        validator=FileValidator(
            config=captured_config,
            temporary_input_owner=temporary_input_owner,
        ),
        temporary_input_owner=temporary_input_owner,
        accepted_receiver=receiver,
        clock=clock,
    )
    application_service = AnalysisApplicationService(
        intake=intake,
        registry=task_registry,
        result_finalizer=result_finalizer,
        result_repository=result_repository,
    )
    return _ProductionRuntime(
        application_service=application_service,
        analyzer_registry=analyzer_registry,
        intake=intake,
        registry=task_registry,
        result_finalizer=result_finalizer,
        result_repository=result_repository,
        scheduler=scheduler,
    )
