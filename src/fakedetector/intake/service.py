"""Application service for controlled, adapter-neutral binary intake."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
        owned_source: OwnedSource | None = None
        try:
            registered_at = self._clock.now()
            analysis_id = self._analysis_id_generator.generate()
            owned_source = self._temporary_input_owner.create(analysis_id)
            measurements = self._temporary_input_owner.ingest(
                owned_source,
                stream,
                self._hard_limit_bytes,
            )
            input_file = InputFileDescriptor(
                original_name=original_name,
                declared_content_type=declared_content_type,
                size_bytes=measurements.size_bytes,
                received_at=registered_at,
            )
            return ControlledInput(
                analysis_id=analysis_id,
                registered_at=registered_at,
                source=source,
                input_file=input_file,
                sha256=measurements.sha256,
                owned_source=owned_source,
            )
        except (FileTooLargeError, IntakeSystemError) as error:
            primary_error: PrimaryIntakeError = error
        except Exception:
            primary_error = IntakeSystemError("unexpected")

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
