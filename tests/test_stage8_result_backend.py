"""Production-facing integration tests for the Stage 8 result backend."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
import yaml

from fakedetector._runtime import _build_production_runtime
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalysisResult,
    AnalysisStatus,
    CleanupResult,
    CompletenessStatus,
    ProcessingStage,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
)
from fakedetector.intake import (
    LocalTemporaryInputOwner,
    PreRegistrationError,
    Stage3Accepted,
    Stage3Terminal,
)
from fakedetector.lifecycle.models import TerminalSettlementPhase, TerminalTaskFacts
from fakedetector.repositories import ResultRepositoryError
from fakedetector.result_finalization import ResultFinalizationService


class _CapturingFinalizer:
    def __init__(self, delegate: ResultFinalizationService) -> None:
        self._delegate = delegate
        self.facts: TerminalTaskFacts | None = None

    def finalize_accepted(
        self,
        facts: TerminalTaskFacts,
        *,
        finished_at: datetime,
        before_save: Callable[[], None],
    ) -> AnalysisResult:
        self.facts = facts
        return self._delegate.finalize_accepted(
            facts,
            finished_at=finished_at,
            before_save=before_save,
        )


class _FailingIdGenerator:
    def generate(self) -> str:
        raise RuntimeError("PRIVATE identity failure")


def _config(tmp_path: Path, *, include_raw_metrics: bool = False) -> AppConfig:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(tmp_path / "temp")
    raw["result"]["directory"] = str(tmp_path / "results")
    raw["result"]["include_raw_metrics"] = include_raw_metrics
    raw["limits"]["processing_timeout_seconds"] = 60
    return AppConfig.model_validate(raw)


def test_real_production_image_is_persisted_before_finished_and_facts_are_detached(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    expected_snapshot_id = _ConfigSnapshot.capture(config).snapshot_id
    expected_application_version = config.server.application_version
    expected_result_directory = Path(config.result.directory)
    runtime = _build_production_runtime(config)
    config.server.application_version = "PRIVATE-MUTATED-VERSION"
    config.result.directory = str(tmp_path / "mutated-results")
    capturing = _CapturingFinalizer(runtime.result_finalizer)
    runtime.scheduler._processor._result_finalizer = capturing
    save_observations: list[tuple[ProcessingStage, TerminalSettlementPhase]] = []
    real_save = runtime.result_repository.save

    def observe_save(result: AnalysisResult) -> None:
        snapshot_at_save = runtime.registry.snapshot(result.analysis_id)
        task_at_save = runtime.registry._tasks[result.analysis_id]
        assert task_at_save.terminal_settlement is not None
        save_observations.append(
            (snapshot_at_save.stage, task_at_save.terminal_settlement.phase)
        )
        assert snapshot_at_save.cleanup is None
        assert snapshot_at_save.finished_at is None
        real_save(result)

    monkeypatch.setattr(runtime.result_repository, "save", observe_save)

    assert not expected_result_directory.exists()
    runtime.scheduler.start()
    try:
        outcome = runtime.intake.process(
            BytesIO(media_files["png"].read_bytes()),
            original_name="production.png",
            declared_content_type="image/png",
            source=SourceContext(
                channel=SourceChannel.API,
                external_reference="production-reference",
            ),
        )
        assert isinstance(outcome, Stage3Accepted)
    finally:
        runtime.scheduler.shutdown(drain=True)

    snapshot = runtime.registry.snapshot(outcome.analysis_id)
    result = runtime.result_repository.get(outcome.analysis_id)
    assert result is not None
    assert save_observations == [
        (ProcessingStage.PERSISTENCE, TerminalSettlementPhase.FACT_READY)
    ]
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.status is AnalysisStatus.COMPLETED
    assert snapshot.finished_at is not None
    assert snapshot.cleanup is not None
    assert result.status is snapshot.status
    assert result.processing.finished_at == snapshot.finished_at
    assert result.cleanup is not None
    assert result.cleanup.finished_at == snapshot.finished_at
    assert result.processing.config_snapshot_id == expected_snapshot_id
    assert result.processing.application_version == expected_application_version
    assert not (tmp_path / "mutated-results").exists()
    assert isinstance(result.file, ValidatedFileDescriptor)
    assert result.file.original_name == "production.png"
    assert result.completeness.status is CompletenessStatus.COMPLETE
    assert result.risk_assessment is not None
    assert result.recommendation is not None
    assert result.analyzers
    assert all(analyzer.raw_metrics == {} for analyzer in result.analyzers)

    facts = capturing.facts
    assert facts is not None
    with pytest.raises(FrozenInstanceError):
        facts.analysis_id = "mutated"  # type: ignore[misc]
    detached_source = SourceContext.model_validate_json(facts.source_json)
    detached_file = ValidatedFileDescriptor.model_validate_json(facts.file_json)
    task = runtime.registry._tasks[outcome.analysis_id]
    task.context.source.external_reference = "mutated-reference"
    task.validated_file.original_name = "mutated-name.png"
    assert detached_source.external_reference == "production-reference"
    assert detached_file.original_name == "production.png"
    assert SourceContext.model_validate_json(facts.source_json) == detached_source
    assert ValidatedFileDescriptor.model_validate_json(facts.file_json) == detached_file
    assert CleanupResult.model_validate_json(facts.cleanup_json).finished_at is None
    serialized_facts = b"".join(
        (
            facts.source_json,
            facts.file_json,
            *facts.analyzer_results_json,
            *facts.findings_json,
            facts.cleanup_json,
            *facts.errors_json,
        )
    )
    assert b"workspace" not in serialized_facts
    assert b"runtime/temp" not in serialized_facts
    assert "accepted_source" not in repr(facts)
    assert "artifacts" not in repr(facts)


def test_accepted_persistence_failure_keeps_primary_and_cleanup_facts_without_retry(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    runtime = _build_production_runtime(config)
    save_calls = 0
    candidates: list[AnalysisResult] = []
    cleanup_calls: Counter[str] = Counter()
    real_cleanup = LocalTemporaryInputOwner.cleanup

    def fail_save(result: AnalysisResult) -> None:
        nonlocal save_calls
        save_calls += 1
        candidates.append(result.model_copy(deep=True))
        raise ResultRepositoryError("PRIVATE C:\\runtime\\results\\secret.json")

    def count_cleanup(
        owner: LocalTemporaryInputOwner,
        owned_source,
    ) -> None:
        cleanup_calls[owned_source.analysis_id] += 1
        real_cleanup(owner, owned_source)

    monkeypatch.setattr(runtime.result_repository, "save", fail_save)
    monkeypatch.setattr(LocalTemporaryInputOwner, "cleanup", count_cleanup)

    runtime.scheduler.start()
    try:
        outcome = runtime.intake.process(
            BytesIO(media_files["png"].read_bytes()),
            original_name="persistence-failure.png",
            declared_content_type="image/png",
            source=SourceContext(channel=SourceChannel.API),
        )
        assert isinstance(outcome, Stage3Accepted)
    finally:
        runtime.scheduler.shutdown(drain=True)

    snapshot = runtime.registry.snapshot(outcome.analysis_id)
    task = runtime.registry._tasks[outcome.analysis_id]
    authoritative_results = runtime.registry._read_stage5_analyzer_results(task)
    assert snapshot.status is AnalysisStatus.COMPLETED
    assert snapshot.stage is ProcessingStage.PERSISTENCE
    assert snapshot.finished_at is None
    assert snapshot.cleanup is None
    assert [error.code for error in snapshot.errors] == ["result_write_failed"]
    assert save_calls == 1
    assert cleanup_calls[outcome.analysis_id] == 1
    assert outcome.controlled_source.is_released
    assert task.terminal_settlement is not None
    assert task.terminal_settlement.phase is TerminalSettlementPhase.FACT_READY
    assert task.terminal_settlement.facts is not None
    assert task.terminal_settlement.owner_token is None
    assert runtime.result_repository.get(outcome.analysis_id) is None
    assert len(candidates) == 1
    assert candidates[0].status is AnalysisStatus.COMPLETED
    assert candidates[0].cleanup is not None
    assert all(error.code != "result_write_failed" for error in candidates[0].errors)

    runtime.scheduler._sweep_best_effort()

    assert save_calls == 1
    assert cleanup_calls[outcome.analysis_id] == 1
    assert runtime.registry._read_stage5_analyzer_results(task) == authoritative_results
    assert runtime.registry.recoverable_terminal_tasks() == ()


def test_real_stage3_rejection_is_finalized_synchronously_through_shared_backend(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    expected_snapshot_id = _ConfigSnapshot.capture(config).snapshot_id
    runtime = _build_production_runtime(config)

    outcome = runtime.intake.process(
        BytesIO(b"not a supported media file"),
        original_name="unsupported.txt",
        declared_content_type="text/plain",
        source=SourceContext(channel=SourceChannel.API),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.REJECTED
    result = runtime.result_finalizer.finalize_stage3(outcome)
    assert result.status is AnalysisStatus.REJECTED
    assert result.file is not None
    assert result.processing.queued_at is None
    assert result.processing.started_at is None
    assert result.processing.config_snapshot_id == expected_snapshot_id
    assert (
        result.processing.application_version
        == config.server.application_version
    )
    assert result.risk_assessment is None
    assert result.recommendation is None
    assert result.cleanup is not None
    assert runtime.result_repository.get(outcome.analysis_id) == result


def test_pre_registration_failure_does_not_create_or_persist_analysis_result(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    runtime = _build_production_runtime(config)
    runtime.intake._controlled_intake._analysis_id_generator = _FailingIdGenerator()

    with pytest.raises(PreRegistrationError):
        runtime.intake.process(
            BytesIO(b"unused"),
            original_name="unused.png",
            declared_content_type="image/png",
            source=SourceContext(channel=SourceChannel.API),
        )

    assert runtime.result_repository.list_recent(10) == []
    assert not Path(config.result.directory).exists()
