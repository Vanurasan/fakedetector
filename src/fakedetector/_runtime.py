"""Private production composition for the implemented analysis lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

from fakedetector.analyzers._catalog import _real_analyzer_registrations
from fakedetector.analyzers._orchestrator import AnalyzerOrchestrator
from fakedetector.analyzers._registry import AnalyzerRegistry
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
from fakedetector.lifecycle.execution import MediaRouter, TaskRegistry
from fakedetector.lifecycle.receiver import Stage4TaskReceiver
from fakedetector.lifecycle.scheduler import BoundedLocalScheduler
from fakedetector.preprocessing._service import PreprocessingDispatcher


@dataclass(frozen=True, slots=True)
class _ProductionRuntime:
    """Owned production services needed by current and future external adapters."""

    analyzer_registry: AnalyzerRegistry
    intake: FileIntakeService
    registry: TaskRegistry
    scheduler: BoundedLocalScheduler


def _build_production_runtime(config: AppConfig) -> _ProductionRuntime:
    """Build the closed deterministic production graph from one config snapshot."""
    clock = AuthoritativeLifecycleClock(UtcClock())
    task_registry = TaskRegistry()
    analyzer_registry = AnalyzerRegistry(config, _real_analyzer_registrations())
    executor = Stage5ExecutionService(
        config=config,
        registry=task_registry,
        preprocessing=PreprocessingDispatcher(config),
        orchestrator=AnalyzerOrchestrator(analyzer_registry),
        finding_service=Stage6FindingService(),
    )
    scheduler = BoundedLocalScheduler(
        config=config,
        clock=clock,
        registry=task_registry,
    )
    receiver = Stage4TaskReceiver(
        config=config,
        clock=clock,
        registry=task_registry,
        router=MediaRouter(dict.fromkeys(MediaType, executor)),
        queue=scheduler,
    )
    temporary_input_owner = LocalTemporaryInputOwner(config.temporary_storage.root_path)
    intake = FileIntakeService(
        controlled_intake=ControlledIntakeService(
            config=config,
            analysis_id_generator=Uuid4AnalysisIdGenerator(),
            clock=clock,
            temporary_input_owner=temporary_input_owner,
        ),
        validator=FileValidator(
            config=config,
            temporary_input_owner=temporary_input_owner,
        ),
        temporary_input_owner=temporary_input_owner,
        accepted_receiver=receiver,
        clock=clock,
    )
    return _ProductionRuntime(
        analyzer_registry=analyzer_registry,
        intake=intake,
        registry=task_registry,
        scheduler=scheduler,
    )
