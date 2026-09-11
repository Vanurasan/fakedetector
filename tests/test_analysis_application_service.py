"""Tests for the adapter-neutral Stage 8 application boundary."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from stage8_helpers import FINISHED, NOW, make_completed_result, make_error, make_rejected_result

from fakedetector.application import (
    AnalysisApplicationService,
    AnalysisInternalError,
    AnalysisNotFoundError,
    AnalysisPendingError,
    AnalysisPersistenceUnavailableError,
    AnalysisStorageError,
    AnalysisSubmissionError,
)
from fakedetector.domain import (
    AnalysisStatus,
    ImageTechnicalParameters,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.intake import (
    AcceptedSource,
    LocalTemporaryInputOwner,
    OwnedSource,
    PreRegistrationError,
    Stage3Accepted,
    Stage3Terminal,
)
from fakedetector.lifecycle import (
    ErrorSnapshot,
    SourceSnapshot,
    TaskNotFoundError,
    TaskSnapshot,
)
from fakedetector.repositories import CorruptedResultError
from fakedetector.result_finalization import ResultFinalizationError


class FakeIntake:
    def __init__(self, outcome: Stage3Accepted | Stage3Terminal | Exception) -> None:
        self.outcome = outcome

    def process(self, *args: object, **kwargs: object) -> Stage3Accepted | Stage3Terminal:
        del args, kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeRegistry:
    def __init__(self, snapshot: TaskSnapshot | Exception) -> None:
        self.value = snapshot
        self.calls: list[str] = []

    def snapshot(self, analysis_id: str) -> TaskSnapshot:
        self.calls.append(analysis_id)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeRepository:
    def __init__(self, result: object = None) -> None:
        self.result = result
        self.calls: list[str] = []

    def get(self, analysis_id: str):
        self.calls.append(analysis_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def save(self, result: object) -> None:
        del result

    def exists(self, analysis_id: str) -> bool:
        del analysis_id
        return False

    def list_recent(self, limit: int) -> list[object]:
        del limit
        return []


class FakeFinalizer:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[Stage3Terminal] = []

    def finalize_stage3(self, terminal: Stage3Terminal):
        self.calls.append(terminal)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _snapshot(
    *,
    status: AnalysisStatus = AnalysisStatus.RUNNING,
    stage: ProcessingStage = ProcessingStage.ANALYSIS,
    errors: tuple[ErrorSnapshot, ...] = (),
) -> TaskSnapshot:
    return TaskSnapshot(
        analysis_id="analysis-001",
        created_at=NOW,
        status=status,
        stage=stage,
        source=SourceSnapshot("api", None, None, None),
        media_type=MediaType.IMAGE,
        config_snapshot_id="snapshot",
        queued_at=NOW,
        started_at=NOW,
        finished_at=FINISHED if stage is ProcessingStage.FINISHED else None,
        route=MediaType.IMAGE,
        cleanup=None,
        errors=errors,
    )


def _accepted(tmp_path: Path) -> Stage3Accepted:
    descriptor = ValidatedFileDescriptor(
        original_name="sample.png",
        extension="png",
        declared_mime_type="image/png",
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=8,
        sha256="digest",
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
    validation = ValidationResult(
        accepted=True,
        checks=[],
        errors=[],
        validated_file=descriptor,
    )
    owner = LocalTemporaryInputOwner(tmp_path)
    owned = OwnedSource(
        analysis_id="analysis-001",
        workspace_path=tmp_path / "analysis-001",
        source_path=tmp_path / "analysis-001" / "input.bin",
        owner_token=object(),
    )
    return Stage3Accepted(
        analysis_id="analysis-001",
        registered_at=NOW,
        source=SourceContext(channel=SourceChannel.API),
        validation=validation,
        validated_file=descriptor,
        controlled_source=AcceptedSource(owner, owned),
    )


def _terminal(*, status: AnalysisStatus = AnalysisStatus.REJECTED) -> Stage3Terminal:
    error = (
        make_error("unsupported_extension", "unsupported_media")
        if status is AnalysisStatus.REJECTED
        else make_error()
    )
    return Stage3Terminal(
        analysis_id="analysis-rejected",
        registered_at=NOW,
        source=SourceContext(channel=SourceChannel.API),
        input_file=None,
        validation=None,
        validated_file=None,
        status=status,
        cleanup=None,
        errors=[error],
    )


def _service(
    *,
    intake: FakeIntake,
    registry: FakeRegistry,
    repository: FakeRepository,
    finalizer: FakeFinalizer | None = None,
) -> AnalysisApplicationService:
    return AnalysisApplicationService(
        intake=intake,
        registry=registry,
        result_finalizer=finalizer or FakeFinalizer(make_rejected_result()),
        result_repository=repository,
    )


def test_accepted_submit_samples_actual_live_status(tmp_path: Path) -> None:
    registry = FakeRegistry(
        _snapshot(status=AnalysisStatus.COMPLETED, stage=ProcessingStage.PERSISTENCE)
    )
    service = _service(
        intake=FakeIntake(_accepted(tmp_path)),
        registry=registry,
        repository=FakeRepository(),
    )

    submission = service.submit(
        BytesIO(b"png"),
        original_name="sample.png",
        declared_content_type="image/png",
        source=SourceContext(channel=SourceChannel.API),
    )

    assert submission.analysis_id == "analysis-001"
    assert submission.status is AnalysisStatus.COMPLETED
    assert submission.stage is ProcessingStage.PERSISTENCE
    assert submission.terminal_result is None


@pytest.mark.parametrize("status", [AnalysisStatus.REJECTED, AnalysisStatus.FAILED])
def test_stage3_terminal_submit_returns_only_persisted_result(status: AnalysisStatus) -> None:
    result = make_rejected_result(
        status=status,
        code="unsupported_extension" if status is AnalysisStatus.REJECTED else "internal_error",
        category="unsupported_media" if status is AnalysisStatus.REJECTED else "internal",
    )
    finalizer = FakeFinalizer(result)
    service = _service(
        intake=FakeIntake(_terminal(status=status)),
        registry=FakeRegistry(TaskNotFoundError()),
        repository=FakeRepository(),
        finalizer=finalizer,
    )

    submission = service.submit(
        BytesIO(b"bad"),
        original_name="bad.bin",
        declared_content_type=None,
        source=SourceContext(channel=SourceChannel.API),
    )

    assert submission.terminal_result is result
    assert submission.status is status
    assert len(finalizer.calls) == 1


def test_stage3_persistence_failure_has_no_fake_submission() -> None:
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(TaskNotFoundError()),
        repository=FakeRepository(),
        finalizer=FakeFinalizer(ResultFinalizationError("analysis-rejected")),
    )

    with pytest.raises(AnalysisPersistenceUnavailableError):
        service.submit(
            BytesIO(b"bad"),
            original_name="bad.bin",
            declared_content_type=None,
            source=SourceContext(channel=SourceChannel.API),
        )


def test_unexpected_stage3_finalization_failure_is_safe_internal_error() -> None:
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(TaskNotFoundError()),
        repository=FakeRepository(),
        finalizer=FakeFinalizer(ValueError("PRIVATE finalization detail")),
    )

    with pytest.raises(AnalysisInternalError) as error_info:
        service.submit(
            BytesIO(b"bad"),
            original_name="bad.bin",
            declared_content_type=None,
            source=SourceContext(channel=SourceChannel.API),
        )

    assert "PRIVATE" not in str(error_info.value)


def test_pre_registration_failure_is_safe_without_id() -> None:
    service = _service(
        intake=FakeIntake(PreRegistrationError()),
        registry=FakeRegistry(TaskNotFoundError()),
        repository=FakeRepository(),
    )

    with pytest.raises(AnalysisSubmissionError) as error_info:
        service.submit(
            BytesIO(b"data"),
            original_name="sample.png",
            declared_content_type="image/png",
            source=SourceContext(channel=SourceChannel.API),
        )

    assert not hasattr(error_info.value, "analysis_id")


def test_get_status_projects_live_registry_without_repository_read() -> None:
    repository = FakeRepository(make_completed_result())
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(_snapshot()),
        repository=repository,
    )

    status = service.get_status("analysis-001")

    assert status.stage is ProcessingStage.ANALYSIS
    assert not status.result_available
    assert repository.calls == []


def test_get_status_falls_back_to_persisted_result_after_restart() -> None:
    result = make_completed_result()
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(TaskNotFoundError()),
        repository=FakeRepository(result),
    )

    status = service.get_status("analysis-001")

    assert status.stage is ProcessingStage.FINISHED
    assert status.finished_at == FINISHED
    assert status.result_available


def test_get_result_reports_pending_for_live_analysis() -> None:
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(_snapshot()),
        repository=FakeRepository(make_completed_result()),
    )

    with pytest.raises(AnalysisPendingError) as error_info:
        service.get_result("analysis-001")

    assert error_info.value.status.stage is ProcessingStage.ANALYSIS


def test_get_result_reads_repository_only_after_live_finished() -> None:
    result = make_completed_result()
    repository = FakeRepository(result)
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(
            _snapshot(status=AnalysisStatus.COMPLETED, stage=ProcessingStage.FINISHED)
        ),
        repository=repository,
    )

    assert service.get_result("analysis-001") is result
    assert repository.calls == ["analysis-001"]


def test_live_persistence_precedes_already_written_json() -> None:
    repository = FakeRepository(make_completed_result())
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(
            _snapshot(status=AnalysisStatus.COMPLETED, stage=ProcessingStage.PERSISTENCE)
        ),
        repository=repository,
    )

    with pytest.raises(AnalysisPendingError):
        service.get_result("analysis-001")

    assert repository.calls == []


def test_live_result_write_failure_is_status_visible_and_result_unavailable() -> None:
    snapshot = _snapshot(
        status=AnalysisStatus.COMPLETED,
        stage=ProcessingStage.PERSISTENCE,
        errors=(
            ErrorSnapshot(
                code="result_write_failed",
                category="storage",
                message="Не удалось сохранить итоговый результат анализа.",
                retryable=True,
            ),
        ),
    )
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(snapshot),
        repository=FakeRepository(make_completed_result()),
    )

    status = service.get_status("analysis-001")
    assert status.persistence_failed
    assert not status.result_available
    with pytest.raises(AnalysisPersistenceUnavailableError):
        service.get_result("analysis-001")


def test_unknown_id_is_not_found() -> None:
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(TaskNotFoundError()),
        repository=FakeRepository(),
    )

    with pytest.raises(AnalysisNotFoundError):
        service.get_status("unknown")
    with pytest.raises(AnalysisNotFoundError):
        service.get_result("unknown")


def test_repository_corruption_is_safe_typed_storage_failure() -> None:
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(TaskNotFoundError()),
        repository=FakeRepository(CorruptedResultError("PRIVATE PATH")),
    )

    with pytest.raises(AnalysisStorageError) as error_info:
        service.get_result("analysis-001")

    assert "PRIVATE PATH" not in str(error_info.value)


def test_finished_without_persisted_result_is_internal_contract_failure() -> None:
    service = _service(
        intake=FakeIntake(_terminal()),
        registry=FakeRegistry(
            _snapshot(status=AnalysisStatus.COMPLETED, stage=ProcessingStage.FINISHED)
        ),
        repository=FakeRepository(),
    )

    with pytest.raises(AnalysisInternalError):
        service.get_result("analysis-001")
