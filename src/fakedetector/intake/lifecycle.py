"""Integrated application lifecycle for one adapter-neutral Stage 3 input."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from fakedetector.core import Clock
from fakedetector.domain import (
    AnalysisStatus,
    CleanupResult,
    CleanupStatus,
    CompletenessStatus,
    ErrorDetail,
    InputFileDescriptor,
    ProcessingStage,
    RiskLevel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.intake.service import (
    ControlledInput,
    ControlledIntakeService,
    IntakeCleanupError,
    RegisteredInput,
    RegisteredIntakeError,
)
from fakedetector.intake.temporary_input import (
    AcceptedSource,
    FileTooLargeError,
    LocalTemporaryInputOwner,
    OwnedSource,
    ReadableBinaryStream,
    TemporaryInputCleanupError,
)
from fakedetector.intake.validation import FileValidator


class PreRegistrationError(Exception):
    """Safe application failure raised before a factual Stage 3 identity exists."""

    def __init__(self) -> None:
        super().__init__("Stage 3 registration failed.")


@dataclass(frozen=True, slots=True)
class Stage3Accepted:
    """Factual accepted outcome whose controlled source moved downstream."""

    analysis_id: str
    registered_at: datetime
    source: SourceContext
    validation: ValidationResult
    validated_file: ValidatedFileDescriptor
    controlled_source: AcceptedSource

    def __post_init__(self) -> None:
        if not self.validation.accepted or self.validation.validated_file is None:
            raise ValueError("accepted outcome requires successful validation")
        if self.validation.validated_file != self.validated_file:
            raise ValueError("accepted descriptor must match validation")


@dataclass(frozen=True, slots=True)
class Stage3Terminal:
    """Factual rejected or failed outcome before specialized analysis."""

    analysis_id: str
    registered_at: datetime
    source: SourceContext
    input_file: InputFileDescriptor | None
    validation: ValidationResult | None
    validated_file: ValidatedFileDescriptor | None
    status: AnalysisStatus
    cleanup: CleanupResult | None
    errors: list[ErrorDetail]
    stage: ProcessingStage = field(default=ProcessingStage.FINISHED, init=False)
    analyzers: list[object] = field(default_factory=list, init=False)
    findings: list[object] = field(default_factory=list, init=False)
    completeness: CompletenessStatus = field(
        default=CompletenessStatus.NOT_ASSESSED,
        init=False,
    )
    final_risk_level: RiskLevel | None = field(default=None, init=False)
    recommendation: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.status not in {AnalysisStatus.REJECTED, AnalysisStatus.FAILED}:
            raise ValueError("Stage 3 terminal status must be rejected or failed")
        if not self.errors:
            raise ValueError("Stage 3 terminal outcome requires a primary error")


type Stage3Outcome = Stage3Accepted | Stage3Terminal


class AcceptedInputReceiver(Protocol):
    """Narrow port confirming that downstream accepted controlled ownership."""

    def accept(self, accepted: Stage3Accepted) -> None:
        """Return normally only after ownership has been accepted."""
        ...


class FileIntakeService:
    """Coordinate registration, intake, validation, cleanup, and handoff."""

    def __init__(
        self,
        *,
        controlled_intake: ControlledIntakeService,
        validator: FileValidator,
        temporary_input_owner: LocalTemporaryInputOwner,
        accepted_receiver: AcceptedInputReceiver,
        clock: Clock,
    ) -> None:
        self._controlled_intake = controlled_intake
        self._validator = validator
        self._owner = temporary_input_owner
        self._accepted_receiver = accepted_receiver
        self._clock = clock

    def process(
        self,
        stream: ReadableBinaryStream,
        *,
        original_name: str,
        declared_content_type: str | None,
        source: SourceContext,
    ) -> Stage3Outcome:
        """Return one accepted handoff or factual pre-analysis terminal outcome."""
        try:
            registered = self._controlled_intake.register(source)
        except Exception:
            raise PreRegistrationError() from None

        controlled: ControlledInput | None = None
        validation: ValidationResult | None = None
        owned_source: OwnedSource | None = None
        pending_source: AcceptedSource | None = None
        cleanup_attempted = False
        handoff_confirmed = False

        try:
            try:
                controlled = self._controlled_intake.intake_registered(
                    registered,
                    stream,
                    original_name=original_name,
                    declared_content_type=declared_content_type,
                )
                owned_source = controlled.owned_source
                validation = self._validator.validate(controlled)

                if not validation.accepted:
                    cleanup_attempted = True
                    cleanup = self._cleanup_owned(owned_source)
                    return self._terminal(
                        registered=registered,
                        controlled=controlled,
                        validation=validation,
                        status=AnalysisStatus.REJECTED,
                        cleanup=cleanup,
                        errors=validation.errors,
                    )

                validated_file = validation.validated_file
                if validated_file is None:
                    raise RuntimeError("accepted validation omitted descriptor")

                pending_source = self._owner.transfer(owned_source)
                accepted = Stage3Accepted(
                    analysis_id=registered.analysis_id,
                    registered_at=registered.registered_at,
                    source=registered.source,
                    validation=validation,
                    validated_file=validated_file,
                    controlled_source=pending_source,
                )
                self._accepted_receiver.accept(accepted)
                handoff_confirmed = True
                return accepted
            except RegisteredIntakeError as error:
                owned_source = error.owned_source
                cleanup_attempted = owned_source is not None
                intake_cleanup = (
                    self._cleanup_owned(owned_source) if owned_source is not None else None
                )
                status = (
                    AnalysisStatus.REJECTED
                    if isinstance(error.primary_error, FileTooLargeError)
                    else AnalysisStatus.FAILED
                )
                return self._terminal(
                    registered=registered,
                    controlled=None,
                    validation=None,
                    status=status,
                    cleanup=intake_cleanup,
                    errors=[self._intake_error(error.primary_error)],
                )
            except IntakeCleanupError as error:
                owned_source = error.owned_source
                cleanup_attempted = True
                status = (
                    AnalysisStatus.REJECTED
                    if isinstance(error.primary_error, FileTooLargeError)
                    else AnalysisStatus.FAILED
                )
                return self._terminal(
                    registered=registered,
                    controlled=None,
                    validation=None,
                    status=status,
                    cleanup=self._cleanup_failure(error.cleanup_error),
                    errors=[self._intake_error(error.primary_error)],
                )
            except Exception:
                cleanup_attempted = owned_source is not None or pending_source is not None
                failure_cleanup = self._cleanup_current(owned_source, pending_source)
                return self._terminal(
                    registered=registered,
                    controlled=controlled,
                    validation=validation,
                    status=AnalysisStatus.FAILED,
                    cleanup=failure_cleanup,
                    errors=[_internal_error()],
                )
        finally:
            if not handoff_confirmed and not cleanup_attempted:
                self._best_effort_cleanup_current(owned_source, pending_source)

    def _cleanup_current(
        self,
        owned_source: OwnedSource | None,
        pending_source: AcceptedSource | None,
    ) -> CleanupResult | None:
        if pending_source is not None:
            return self._cleanup_accepted(pending_source)
        if owned_source is not None and not owned_source.is_handed_off:
            return self._cleanup_owned(owned_source)
        return None

    def _cleanup_owned(self, owned_source: OwnedSource) -> CleanupResult:
        try:
            self._owner.cleanup(owned_source)
        except TemporaryInputCleanupError as error:
            return self._cleanup_failure(error)
        except Exception:
            return self._cleanup_failure(TemporaryInputCleanupError())
        return self._cleanup_completed()

    def _cleanup_accepted(self, accepted_source: AcceptedSource) -> CleanupResult:
        try:
            accepted_source.cleanup()
        except TemporaryInputCleanupError as error:
            return self._cleanup_failure(error)
        except Exception:
            return self._cleanup_failure(TemporaryInputCleanupError())
        return self._cleanup_completed()

    def _cleanup_completed(self) -> CleanupResult:
        return CleanupResult(
            status=CleanupStatus.COMPLETED,
            original_file_deleted=True,
            intermediate_files_deleted=True,
            quarantine_used=False,
            finished_at=self._cleanup_finished_at(),
            errors=[],
        )

    def _cleanup_failure(self, error: TemporaryInputCleanupError) -> CleanupResult:
        status = (
            CleanupStatus.PARTIAL
            if error.original_file_deleted or error.intermediate_files_deleted
            else CleanupStatus.FAILED
        )
        return CleanupResult(
            status=status,
            original_file_deleted=error.original_file_deleted,
            intermediate_files_deleted=error.intermediate_files_deleted,
            quarantine_used=False,
            finished_at=self._cleanup_finished_at(),
            errors=[
                ErrorDetail(
                    code="cleanup_failed",
                    category="cleanup",
                    message="Не удалось полностью удалить временные данные.",
                    retryable=True,
                )
            ],
        )

    def _cleanup_finished_at(self) -> datetime | None:
        try:
            return self._clock.now()
        except Exception:
            return None

    def _best_effort_cleanup_current(
        self,
        owned_source: OwnedSource | None,
        pending_source: AcceptedSource | None,
    ) -> None:
        with suppress(BaseException):
            if pending_source is not None and not pending_source.is_released:
                pending_source.cleanup()
            elif (
                owned_source is not None
                and not owned_source.is_released
                and not owned_source.is_handed_off
            ):
                self._owner.cleanup(owned_source)

    @staticmethod
    def _terminal(
        *,
        registered: RegisteredInput,
        controlled: ControlledInput | None,
        validation: ValidationResult | None,
        status: AnalysisStatus,
        cleanup: CleanupResult | None,
        errors: list[ErrorDetail],
    ) -> Stage3Terminal:
        return Stage3Terminal(
            analysis_id=registered.analysis_id,
            registered_at=registered.registered_at,
            source=registered.source,
            input_file=controlled.input_file if controlled is not None else None,
            validation=validation,
            validated_file=validation.validated_file if validation is not None else None,
            status=status,
            cleanup=cleanup,
            errors=errors,
        )

    @staticmethod
    def _intake_error(error: Exception) -> ErrorDetail:
        if isinstance(error, FileTooLargeError):
            return ErrorDetail(
                code="file_too_large",
                category="resource_limit",
                message="Размер файла превышает допустимый предел.",
                retryable=False,
                field="file",
                safe_details={
                    "max_size_bytes": error.max_size_bytes,
                    "observed_size_bytes": error.observed_size_bytes,
                },
            )
        return _internal_error()


def _internal_error() -> ErrorDetail:
    return ErrorDetail(
        code="internal_error",
        category="internal",
        message="Внутренняя ошибка не позволила завершить приём файла.",
        retryable=True,
    )
