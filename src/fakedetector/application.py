"""Adapter-neutral application boundary for analysis submission and reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from fakedetector.domain import (
    AnalysisResult,
    AnalysisStatus,
    ErrorDetail,
    ProcessingStage,
    SourceContext,
)
from fakedetector.intake import (
    PreRegistrationError,
    ReadableBinaryStream,
    Stage3Accepted,
    Stage3Outcome,
    Stage3Terminal,
)
from fakedetector.lifecycle import TaskNotFoundError, TaskSnapshot
from fakedetector.repositories import (
    InvalidAnalysisIdError,
    ResultRepository,
    ResultRepositoryError,
)
from fakedetector.result_finalization import ResultFinalizationError


class AnalysisApplicationError(Exception):
    """Base class for safe application-boundary failures."""


class AnalysisSubmissionError(AnalysisApplicationError):
    """A submission failed before a factual analysis identity was available."""

    def __init__(self) -> None:
        super().__init__("Analysis submission failed.")


class AnalysisNotFoundError(AnalysisApplicationError):
    """Neither live state nor a persisted result exists for an analysis ID."""

    def __init__(self) -> None:
        super().__init__("Analysis was not found.")


class AnalysisStorageError(AnalysisApplicationError):
    """Persisted result storage could not be read safely."""

    def __init__(self) -> None:
        super().__init__("Analysis result storage is unavailable.")


class AnalysisInternalError(AnalysisApplicationError):
    """An internal application contract could not be satisfied."""

    def __init__(self) -> None:
        super().__init__("Analysis state is unavailable.")


class AnalysisPersistenceUnavailableError(AnalysisApplicationError):
    """A known analysis failed while persisting its canonical result."""

    def __init__(self) -> None:
        super().__init__("Analysis result persistence is unavailable.")


class AnalysisPendingError(AnalysisApplicationError):
    """A known live analysis has not published FINISHED yet."""

    def __init__(self, status: AnalysisStatusView) -> None:
        super().__init__("Analysis is still in progress.")
        self.status = status


@dataclass(frozen=True, slots=True)
class AnalysisSubmission:
    """Factual state sampled immediately after one submission."""

    analysis_id: str
    status: AnalysisStatus
    stage: ProcessingStage
    terminal_result: AnalysisResult | None


@dataclass(frozen=True, slots=True)
class AnalysisStatusView:
    """Transport-neutral factual status projection."""

    analysis_id: str
    status: AnalysisStatus
    stage: ProcessingStage
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    result_available: bool
    errors: tuple[ErrorDetail, ...]

    @property
    def persistence_failed(self) -> bool:
        """Return whether live persistence failed after accepted processing."""
        return self.stage is ProcessingStage.PERSISTENCE and any(
            error.code == "result_write_failed" for error in self.errors
        )


class _IntakeService(Protocol):
    def process(
        self,
        stream: ReadableBinaryStream,
        *,
        original_name: str,
        declared_content_type: str | None,
        source: SourceContext,
    ) -> Stage3Outcome: ...


class _TaskRegistry(Protocol):
    def snapshot(self, analysis_id: str) -> TaskSnapshot: ...


class _Stage3Finalizer(Protocol):
    def finalize_stage3(self, terminal: Stage3Terminal) -> AnalysisResult: ...


class AnalysisApplicationService:
    """Coordinate both external channels through one runtime and read policy."""

    def __init__(
        self,
        *,
        intake: _IntakeService,
        registry: _TaskRegistry,
        result_finalizer: _Stage3Finalizer,
        result_repository: ResultRepository,
    ) -> None:
        self._intake = intake
        self._registry = registry
        self._result_finalizer = result_finalizer
        self._result_repository = result_repository

    def submit(
        self,
        stream: ReadableBinaryStream,
        *,
        original_name: str,
        declared_content_type: str | None,
        source: SourceContext,
    ) -> AnalysisSubmission:
        """Submit adapted transport data and return only factual sampled state."""
        try:
            outcome = self._intake.process(
                stream,
                original_name=original_name,
                declared_content_type=declared_content_type,
                source=source,
            )
        except PreRegistrationError:
            raise AnalysisSubmissionError() from None
        except Exception:
            raise AnalysisSubmissionError() from None

        if isinstance(outcome, Stage3Accepted):
            snapshot = self._live_snapshot(outcome.analysis_id)
            return AnalysisSubmission(
                analysis_id=snapshot.analysis_id,
                status=snapshot.status,
                stage=snapshot.stage,
                terminal_result=None,
            )

        try:
            result = self._result_finalizer.finalize_stage3(outcome)
        except ResultFinalizationError:
            raise AnalysisPersistenceUnavailableError() from None
        except Exception:
            raise AnalysisInternalError() from None
        return AnalysisSubmission(
            analysis_id=result.analysis_id,
            status=result.status,
            stage=result.stage,
            terminal_result=result,
        )

    def get_status(self, analysis_id: str) -> AnalysisStatusView:
        """Read live state first, falling back to a persisted terminal result."""
        try:
            snapshot = self._registry.snapshot(analysis_id)
        except TaskNotFoundError:
            result = self._stored_result(analysis_id)
            if result is None:
                raise AnalysisNotFoundError() from None
            return _status_from_result(result)
        except Exception:
            raise AnalysisInternalError() from None
        return _status_from_snapshot(snapshot)

    def get_result(self, analysis_id: str) -> AnalysisResult:
        """Return a canonical persisted result only when live precedence permits it."""
        try:
            snapshot = self._registry.snapshot(analysis_id)
        except TaskNotFoundError:
            result = self._stored_result(analysis_id)
            if result is None:
                raise AnalysisNotFoundError() from None
            return result
        except Exception:
            raise AnalysisInternalError() from None

        status = _status_from_snapshot(snapshot)
        if status.persistence_failed:
            raise AnalysisPersistenceUnavailableError() from None
        if snapshot.stage is not ProcessingStage.FINISHED:
            raise AnalysisPendingError(status)

        result = self._stored_result(analysis_id)
        if result is None:
            raise AnalysisInternalError() from None
        return result

    def _live_snapshot(self, analysis_id: str) -> TaskSnapshot:
        try:
            return self._registry.snapshot(analysis_id)
        except Exception:
            raise AnalysisInternalError() from None

    def _stored_result(self, analysis_id: str) -> AnalysisResult | None:
        try:
            return self._result_repository.get(analysis_id)
        except InvalidAnalysisIdError:
            return None
        except ResultRepositoryError:
            raise AnalysisStorageError() from None
        except Exception:
            raise AnalysisStorageError() from None


def _status_from_snapshot(snapshot: TaskSnapshot) -> AnalysisStatusView:
    return AnalysisStatusView(
        analysis_id=snapshot.analysis_id,
        status=snapshot.status,
        stage=snapshot.stage,
        created_at=snapshot.created_at,
        queued_at=snapshot.queued_at,
        started_at=snapshot.started_at,
        finished_at=snapshot.finished_at,
        result_available=snapshot.stage is ProcessingStage.FINISHED,
        errors=tuple(
            ErrorDetail.model_validate(
                {
                    "code": error.code,
                    "category": error.category,
                    "message": error.message,
                    "retryable": error.retryable,
                }
            )
            for error in snapshot.errors
        ),
    )


def _status_from_result(result: AnalysisResult) -> AnalysisStatusView:
    return AnalysisStatusView(
        analysis_id=result.analysis_id,
        status=result.status,
        stage=result.stage,
        created_at=result.created_at,
        queued_at=result.processing.queued_at,
        started_at=result.processing.started_at,
        finished_at=result.processing.finished_at,
        result_available=True,
        errors=tuple(error.model_copy(deep=True) for error in result.errors),
    )
