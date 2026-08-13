"""Application service for controlled, adapter-neutral binary intake."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta

from fakedetector.config.models import AppConfig
from fakedetector.core import AnalysisIdGenerator, Clock
from fakedetector.domain import InputFileDescriptor, SourceContext
from fakedetector.intake.temporary_input import (
    FileTooLargeError,
    IntakeSystemError,
    LocalTemporaryInputOwner,
    OwnedSource,
    ReadableBinaryStream,
    TemporaryInputCleanupError,
)

_BYTES_PER_MEBIBYTE = 1024 * 1024
PrimaryIntakeError = FileTooLargeError | IntakeSystemError


class IntakeCleanupError(Exception):
    """Preserve both a primary intake problem and a failed cleanup attempt."""

    def __init__(
        self,
        *,
        primary_error: PrimaryIntakeError,
        cleanup_error: TemporaryInputCleanupError,
        owned_source: OwnedSource,
    ) -> None:
        super().__init__("Controlled intake did not complete and cleanup failed.")
        self.primary_error = primary_error
        self.cleanup_error = cleanup_error
        self.owned_source = owned_source


class RegisteredIntakeError(Exception):
    """Report a post-registration intake failure without performing cleanup."""

    def __init__(
        self,
        *,
        primary_error: PrimaryIntakeError,
        owned_source: OwnedSource | None,
    ) -> None:
        super().__init__("Registered controlled intake failed.")
        self.primary_error = primary_error
        self.owned_source = owned_source


@dataclass(frozen=True, slots=True)
class RegisteredInput:
    """Factual Stage 3 registration established before temporary acquisition."""

    analysis_id: str
    registered_at: datetime
    source: SourceContext


@dataclass(frozen=True, slots=True)
class ControlledInput:
    """Internal successful result before media validation and ownership handoff."""

    analysis_id: str
    registered_at: datetime
    source: SourceContext
    input_file: InputFileDescriptor
    sha256: str
    owned_source: OwnedSource


class ControlledIntakeService:
    """Register and stream one untrusted input into temporary Stage 3 ownership."""

    def __init__(
        self,
        *,
        config: AppConfig,
        analysis_id_generator: AnalysisIdGenerator,
        clock: Clock,
        temporary_input_owner: LocalTemporaryInputOwner | None = None,
    ) -> None:
        self._analysis_id_generator = analysis_id_generator
        self._clock = clock
        self._temporary_input_owner = temporary_input_owner or LocalTemporaryInputOwner(
            config.temporary_storage.root_path
        )
        limits = config.limits.max_file_size_mb
        self._hard_limit_bytes = (
            max(limits.image, limits.audio, limits.video) * _BYTES_PER_MEBIBYTE
        )

    def intake(
        self,
        stream: ReadableBinaryStream,
        *,
        original_name: str,
        declared_content_type: str | None,
        source: SourceContext,
    ) -> ControlledInput:
        """Perform one bounded intake without closing the caller-owned stream."""
        try:
            registered = self.register(source)
            return self.intake_registered(
                registered,
                stream,
                original_name=original_name,
                declared_content_type=declared_content_type,
            )
        except RegisteredIntakeError as error:
            primary_error = error.primary_error
            owned_source = error.owned_source
        except IntakeSystemError as error:
            raise error from None
        except Exception:
            raise IntakeSystemError("unexpected") from None

        if owned_source is not None:
            try:
                self._temporary_input_owner.cleanup(owned_source)
            except TemporaryInputCleanupError as cleanup_error:
                raise IntakeCleanupError(
                    primary_error=primary_error,
                    cleanup_error=cleanup_error,
                    owned_source=owned_source,
                ) from None
            except Exception:
                raise IntakeCleanupError(
                    primary_error=primary_error,
                    cleanup_error=TemporaryInputCleanupError(),
                    owned_source=owned_source,
                ) from None

        raise primary_error from None

    def register(self, source: SourceContext) -> RegisteredInput:
        """Establish a safe system identity and UTC registration timestamp."""
        try:
            registered_at = self._clock.now()
            analysis_id = self._analysis_id_generator.generate()
            self._temporary_input_owner.validate_analysis_id(analysis_id)
            if registered_at.utcoffset() != timedelta(0):
                raise IntakeSystemError("registration")
        except IntakeSystemError:
            raise
        except Exception:
            raise IntakeSystemError("registration") from None
        return RegisteredInput(
            analysis_id=analysis_id,
            registered_at=registered_at,
            source=source,
        )

    def intake_registered(
        self,
        registered: RegisteredInput,
        stream: ReadableBinaryStream,
        *,
        original_name: str,
        declared_content_type: str | None,
    ) -> ControlledInput:
        """Acquire one registered source without taking terminal cleanup action."""
        owned_source: OwnedSource | None = None
        try:
            owned_source = self._temporary_input_owner.create(registered.analysis_id)
            measurements = self._temporary_input_owner.ingest(
                owned_source,
                stream,
                self._hard_limit_bytes,
            )
            input_file = InputFileDescriptor(
                original_name=original_name,
                declared_content_type=declared_content_type,
                size_bytes=measurements.size_bytes,
                received_at=registered.registered_at,
            )
            return ControlledInput(
                analysis_id=registered.analysis_id,
                registered_at=registered.registered_at,
                source=registered.source,
                input_file=input_file,
                sha256=measurements.sha256,
                owned_source=owned_source,
            )
        except (FileTooLargeError, IntakeSystemError) as error:
            primary_error: PrimaryIntakeError = error
        except Exception:
            primary_error = IntakeSystemError("unexpected")
        except BaseException:
            if owned_source is not None:
                with suppress(BaseException):
                    self._temporary_input_owner.cleanup(owned_source)
            raise
        raise RegisteredIntakeError(
            primary_error=primary_error,
            owned_source=owned_source,
        ) from None
