"""Production execution integration for Stage 7 assessment and lifecycle outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import NoReturn, cast

import numpy as np
import pytest
import yaml
from PIL import Image

import fakedetector.analyzers._orchestrator as orchestrator_module
from fakedetector._runtime import _ProductionRuntime
from fakedetector.analyzers._transport import _WorkerRequest, _WorkerResponseKind
from fakedetector.analyzers._worker import (
    _encode_response,
    _execute_worker,
    _WorkerRun,
    _WorkerRunKind,
)
from fakedetector.app import create_app
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalysisCompleteness,
    AnalysisStatus,
    AnalyzerResult,
    AnalyzerStatus,
    CleanupStatus,
    CompletenessStatus,
    Finding,
    FindingSeverity,
    ProcessingStage,
    Recommendation,
    RiskAssessment,
    RiskLevel,
    SourceChannel,
    SourceContext,
)
from fakedetector.intake import Stage3Accepted
from fakedetector.lifecycle._stage7 import (
    Stage7AssessmentError,
    Stage7AssessmentService,
)
from fakedetector.lifecycle.models import AnalysisTask, TaskExecutionOutcome

_EXAMPLE_CONFIG = Path("config/config.example.yaml")


class _ControlledRunner:
    """Use the existing analyzer runner boundary without spawning test workers."""

    def __init__(self, *directives: str) -> None:
        self._directives = list(directives)
        self.requests: list[_WorkerRequest] = []

    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        del timeout_seconds
        self.requests.append(request)
        directive = self._directives.pop(0)
        if directive == "timeout":
            return _WorkerRun(_WorkerRunKind.TIMEOUT, duration_ms=1)
        if directive == "error":
            return _WorkerRun(
                _WorkerRunKind.RESPONSE,
                duration_ms=1,
                response=_encode_response(_WorkerResponseKind.ANALYZER_ERROR),
            )
        if directive == "completed":
            return _WorkerRun(
                _WorkerRunKind.RESPONSE,
                duration_ms=1,
                response=_execute_worker(request),
            )
        raise AssertionError("unknown controlled runner directive")


def _config(
    tmp_path: Path,
    *,
    continue_on_failure: bool = True,
) -> AppConfig:
    raw = yaml.safe_load(_EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(tmp_path / "temp")
    raw["logging"]["jsonl_path"] = str(tmp_path / "logs" / "application.jsonl")
    raw["result"]["directory"] = str(tmp_path / "results")
    raw["limits"]["max_parallel_tasks"] = {"image": 1, "audio": 1, "video": 1}
    raw["limits"]["processing_timeout_seconds"] = 60
    raw["analyzers"]["defaults"]["timeout_seconds"] = 30
    raw["analyzers"]["defaults"]["continue_on_error"] = continue_on_failure
    raw["error_handling"]["continue_if_analyzer_fails"] = continue_on_failure
    return AppConfig.model_validate(raw)


def _production_runtime(config: AppConfig) -> _ProductionRuntime:
    app = create_app(config)
    return cast(_ProductionRuntime, app.state.runtime)


def _run(runtime: _ProductionRuntime, payload: bytes) -> tuple[Stage3Accepted, AnalysisTask]:
    runtime.scheduler.start()
    try:
        accepted = runtime.intake.process(
            BytesIO(payload),
            original_name="stage7.png",
            declared_content_type="image/png",
            source=SourceContext(channel=SourceChannel.API),
        )
        assert isinstance(accepted, Stage3Accepted)
    finally:
        runtime.scheduler.shutdown(drain=True)
    return accepted, runtime.registry._tasks[accepted.analysis_id]


def _plain_png(size: int) -> bytes:
    output = BytesIO()
    with Image.fromarray(np.full((size, size, 3), 127, dtype=np.uint8)) as image:
        image.save(output, format="PNG")
    return output.getvalue()


def _assessment(
    runtime: _ProductionRuntime,
    task: AnalysisTask,
) -> tuple[AnalysisCompleteness, RiskAssessment, Recommendation]:
    assessment = runtime.registry._read_stage7_assessment(task)
    assert assessment is not None
    return assessment


def _use_controlled_runner(
    monkeypatch: pytest.MonkeyPatch,
    runner: _ControlledRunner,
) -> None:
    monkeypatch.setattr(
        orchestrator_module,
        "_SpawnedWorkerRunner",
        lambda: runner,
    )


def test_production_complete_image_publishes_stage7_before_cleanup_and_retains_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_worker_processes: list[BaseProcess],
) -> None:
    config = _config(tmp_path)
    runtime = _production_runtime(config)
    events: list[str] = []
    publish = runtime.registry.publish_stage7_assessment
    record_outcome = runtime.registry.record_outcome

    def record_publication(
        task: AnalysisTask,
        completeness: AnalysisCompleteness,
        risk_assessment: RiskAssessment,
        recommendation: Recommendation,
    ) -> None:
        assert task.context.stage is ProcessingStage.RISK_ASSESSMENT
        assert not task.accepted_source.is_released
        events.append("stage7")
        publish(task, completeness, risk_assessment, recommendation)

    def record_terminal_outcome(
        analysis_id: str,
        outcome: TaskExecutionOutcome,
    ) -> None:
        assert events == ["stage7"]
        assert not runtime.registry._tasks[analysis_id].accepted_source.is_released
        events.append(f"outcome:{outcome.status.value}")
        record_outcome(analysis_id, outcome)

    monkeypatch.setattr(runtime.registry, "publish_stage7_assessment", record_publication)
    monkeypatch.setattr(runtime.registry, "record_outcome", record_terminal_outcome)

    accepted, task = _run(runtime, _plain_png(256))
    completeness, risk, recommendation = _assessment(runtime, task)
    results = runtime.registry._read_stage5_analyzer_results(task)

    assert [result.status for result in results] == [
        AnalyzerStatus.COMPLETED,
        AnalyzerStatus.COMPLETED,
    ]
    assert runtime.registry._read_stage6_findings(task) == ()
    assert completeness.status is CompletenessStatus.COMPLETE
    assert completeness.coverage_ratio == 1.0
    assert risk.score == 0
    assert risk.final_level is RiskLevel.LOW
    assert risk.probability is None and risk.probability_method is None
    assert recommendation.primary_action == "no_additional_action"
    assert recommendation.additional_actions == []
    assert not recommendation.requires_manual_review
    snapshot = runtime.registry.snapshot(accepted.analysis_id)
    assert snapshot.status is AnalysisStatus.COMPLETED
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.cleanup is not None
    assert snapshot.cleanup.status is CleanupStatus.COMPLETED
    assert task.accepted_source.is_released
    assert events == ["stage7", "outcome:completed"]
    assert runtime.registry._read_stage7_assessment(task) == (
        completeness,
        risk,
        recommendation,
    )
    assert len(real_worker_processes) == 2


def test_production_copy_move_uses_one_weak_bucket_and_is_deterministic(
    tmp_path: Path,
    copy_move_png_bytes: bytes,
    real_worker_processes: list[BaseProcess],
) -> None:
    config = _config(tmp_path)
    runtime = _production_runtime(config)
    _, task = _run(runtime, copy_move_png_bytes)

    results = runtime.registry._read_stage5_analyzer_results(task)
    findings = runtime.registry._read_stage6_findings(task)
    stored = _assessment(runtime, task)
    completeness, risk, _recommendation = stored
    correlation_groups = {finding.correlation_group for finding in findings}

    assert len(findings) == 2
    assert len(correlation_groups) == 1 and None not in correlation_groups
    assert all(
        finding.severity is FindingSeverity.WEAK
        and not finding.critical_override_eligible
        for finding in findings
    )
    assert completeness.status is CompletenessStatus.COMPLETE
    assert risk.score == 5
    assert risk.final_level is RiskLevel.LOW
    assert not risk.critical_override_applied
    assert risk.critical_finding_ids == []
    assert risk.probability is None and risk.probability_method is None
    assert config.risk_assessment.critical_override.enabled is False
    assert config.risk_assessment.critical_override.allowed_finding_types == []
    plan = tuple(
        active.registration.analyzer_id
        for active in runtime.analyzer_registry.active_plan(task.context.media_type)
    )
    service = Stage7AssessmentService(config.risk_assessment)
    assert service.assess(plan, results, findings) == stored
    assert service.assess(plan, results, findings) == stored
    snapshot = runtime.registry.snapshot(task.context.analysis_id)
    assert snapshot.status is AnalysisStatus.COMPLETED
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.cleanup is not None and snapshot.cleanup.status is CleanupStatus.COMPLETED
    assert len(real_worker_processes) == 2


def test_production_not_applicable_is_a_missing_capability_without_failure(
    tmp_path: Path,
    real_worker_processes: list[BaseProcess],
) -> None:
    runtime = _production_runtime(_config(tmp_path))
    accepted, task = _run(runtime, _plain_png(64))

    results = runtime.registry._read_stage5_analyzer_results(task)
    completeness, risk, _recommendation = _assessment(runtime, task)

    assert [result.status for result in results] == [
        AnalyzerStatus.COMPLETED,
        AnalyzerStatus.NOT_APPLICABLE,
    ]
    assert completeness.status is CompletenessStatus.COMPLETE
    assert completeness.planned_analyzers == 2
    assert completeness.applicable_analyzers == 1
    assert completeness.completed_analyzers == 1
    assert completeness.not_applicable_analyzers == 1
    assert completeness.coverage_ratio == 1.0
    assert completeness.missing_capabilities == ["image_copy_move_correspondence"]
    assert risk.score == 0 and risk.final_level is RiskLevel.LOW
    snapshot = runtime.registry.snapshot(accepted.analysis_id)
    assert snapshot.status is AnalysisStatus.COMPLETED
    assert snapshot.errors == ()
    assert len(real_worker_processes) == 2


def test_production_one_completed_and_one_error_is_partial_at_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _ControlledRunner("completed", "error")
    _use_controlled_runner(monkeypatch, runner)
    runtime = _production_runtime(_config(tmp_path))
    accepted, task = _run(runtime, _plain_png(256))

    results = runtime.registry._read_stage5_analyzer_results(task)
    completeness, risk, recommendation = _assessment(runtime, task)

    assert [result.status for result in results] == [
        AnalyzerStatus.COMPLETED,
        AnalyzerStatus.ERROR,
    ]
    assert completeness.status is CompletenessStatus.PARTIAL
    assert completeness.coverage_ratio == 0.5
    assert completeness.failed_analyzers == 1
    assert completeness.missing_capabilities == ["image_copy_move_correspondence"]
    assert risk.score == 0 and risk.final_level is RiskLevel.LOW
    assert recommendation.additional_actions == ["retry_analysis"]
    snapshot = runtime.registry.snapshot(accepted.analysis_id)
    assert snapshot.status is AnalysisStatus.PARTIAL
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.cleanup is not None and snapshot.cleanup.status is CleanupStatus.COMPLETED


def test_production_zero_completed_is_insufficient_and_finishes_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _ControlledRunner("error", "error")
    _use_controlled_runner(monkeypatch, runner)
    runtime = _production_runtime(_config(tmp_path))
    accepted, task = _run(runtime, _plain_png(256))

    completeness, risk, recommendation = _assessment(runtime, task)

    assert completeness.status is CompletenessStatus.INSUFFICIENT
    assert completeness.completed_analyzers == 0
    assert completeness.coverage_ratio == 0.0
    assert risk.score is None
    assert risk.score_based_level is None
    assert risk.final_level is None
    assert risk.probability is None and risk.probability_method is None
    assert recommendation.primary_action == "manual_review"
    assert recommendation.additional_actions == ["retry_analysis"]
    snapshot = runtime.registry.snapshot(accepted.analysis_id)
    assert snapshot.status is AnalysisStatus.PARTIAL
    assert snapshot.stage is ProcessingStage.FINISHED


def test_production_timeout_then_policy_skip_are_counted_as_insufficient(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _ControlledRunner("timeout")
    _use_controlled_runner(monkeypatch, runner)
    runtime = _production_runtime(_config(tmp_path, continue_on_failure=False))
    accepted, task = _run(runtime, _plain_png(256))

    results = runtime.registry._read_stage5_analyzer_results(task)
    completeness, risk, _recommendation = _assessment(runtime, task)

    assert [result.status for result in results] == [
        AnalyzerStatus.TIMEOUT,
        AnalyzerStatus.SKIPPED,
    ]
    assert len(runner.requests) == 1
    assert completeness.status is CompletenessStatus.INSUFFICIENT
    assert completeness.timed_out_analyzers == 1
    assert completeness.skipped_analyzers == 1
    assert completeness.missing_capabilities == [
        "image_metadata_consistency",
        "image_copy_move_correspondence",
    ]
    assert risk.score is None and risk.final_level is None
    assert runtime.registry.snapshot(accepted.analysis_id).status is AnalysisStatus.PARTIAL


def test_production_stage7_internal_failure_is_safe_and_uses_existing_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_worker_processes: list[BaseProcess],
) -> None:
    private_detail = "PRIVATE C:\\stage7\\source.png"

    def fail_assessment(
        _self: Stage7AssessmentService,
        _planned_analyzer_ids: Sequence[str],
        _analyzer_results: Sequence[AnalyzerResult],
        _findings: Sequence[Finding],
    ) -> NoReturn:
        raise Stage7AssessmentError(private_detail)

    monkeypatch.setattr(Stage7AssessmentService, "assess", fail_assessment)
    runtime = _production_runtime(_config(tmp_path))
    accepted, task = _run(runtime, _plain_png(256))

    snapshot = runtime.registry.snapshot(accepted.analysis_id)
    assert snapshot.status is AnalysisStatus.FAILED
    assert snapshot.stage is ProcessingStage.FINISHED
    assert snapshot.cleanup is not None and snapshot.cleanup.status is CleanupStatus.COMPLETED
    assert task.stage6_data is not None
    assert task.stage7_data is None
    assert task.accepted_source.is_released
    assert len(task.errors) == 1
    assert task.errors[0].code == "internal_error"
    assert task.errors[0].category == "internal"
    assert task.errors[0].safe_details == {
        "phase": "risk_assessment",
        "reason_code": "assessment_failure",
    }
    assert private_detail not in task.errors[0].model_dump_json()
    assert len(real_worker_processes) == 2


def test_production_not_assessed_from_stage7_is_an_internal_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _ControlledRunner("completed", "completed")
    _use_controlled_runner(monkeypatch, runner)
    not_assessed = AnalysisCompleteness(
        status=CompletenessStatus.NOT_ASSESSED,
        planned_analyzers=0,
        applicable_analyzers=0,
        completed_analyzers=0,
        failed_analyzers=0,
        timed_out_analyzers=0,
        skipped_analyzers=0,
        not_applicable_analyzers=0,
        coverage_ratio=0.0,
        missing_capabilities=[],
        explanation="Рабочая оценка ошибочно не выполнена.",
    )
    risk = RiskAssessment(
        model_id="score_model_v1",
        model_version="0.1.0",
        score=None,
        score_based_level=None,
        critical_override_applied=False,
        critical_finding_ids=[],
        final_level=None,
        probability=None,
        probability_method=None,
        summary="Оценка отсутствует.",
        explanation="Оценка отсутствует.",
        limitations=[],
    )
    recommendation = Recommendation(
        primary_action="manual_review",
        additional_actions=["retry_analysis"],
        text="Рекомендуется повторить анализ.",
        requires_manual_review=True,
    )

    def return_not_assessed(
        _self: Stage7AssessmentService,
        _planned_analyzer_ids: Sequence[str],
        _analyzer_results: Sequence[AnalyzerResult],
        _findings: Sequence[Finding],
    ) -> tuple[AnalysisCompleteness, RiskAssessment, Recommendation]:
        return not_assessed, risk, recommendation

    monkeypatch.setattr(Stage7AssessmentService, "assess", return_not_assessed)
    runtime = _production_runtime(_config(tmp_path))
    accepted, task = _run(runtime, _plain_png(256))

    snapshot = runtime.registry.snapshot(accepted.analysis_id)
    assert snapshot.status is AnalysisStatus.FAILED
    assert snapshot.stage is ProcessingStage.FINISHED
    assert task.stage7_data is None
    assert task.errors[0].safe_details == {
        "phase": "risk_assessment",
        "reason_code": "unexpected_completeness_status",
    }
