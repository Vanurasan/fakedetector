"""Filesystem-backed persistence for validated analysis results."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path, PureWindowsPath
from typing import Protocol, runtime_checkable

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.domain import AnalysisResult, AnalysisResultSummary


class ResultRepositoryError(Exception):
    """Base error for safe result repository failures."""


class InvalidAnalysisIdError(ResultRepositoryError, ValueError):
    """Raised when an analysis ID cannot be used as one safe path component."""


class CorruptedResultError(ResultRepositoryError):
    """Raised when stored result data is not a valid AnalysisResult."""


@runtime_checkable
class ResultRepository(Protocol):
    """Canonical operations of the result repository."""

    def save(self, result: AnalysisResult) -> None:
        """Persist a validated analysis result."""
        ...

    def get(self, analysis_id: str) -> AnalysisResult | None:
        """Return a validated stored result, or None when it is absent."""
        ...

    def exists(self, analysis_id: str) -> bool:
        """Return whether the expected stored result file exists."""
        ...

    def list_recent(self, limit: int) -> list[AnalysisResultSummary]:
        """Return safe summaries ordered by creation time and analysis ID."""
        ...


class JsonFileResultRepository:
    """Store each AnalysisResult as one atomically replaced UTF-8 JSON file."""

    def __init__(self, result_directory: str | os.PathLike[str]) -> None:
        self._result_directory = Path(result_directory)

    def save(self, result: AnalysisResult) -> None:
        """Atomically save a Pydantic-serialized result under its analysis ID."""
        try:
            validated_result = AnalysisResult.model_validate(
                result.model_dump(mode="python", round_trip=True, warnings="error")
            )
            target_path = self._target_path(validated_result.analysis_id)
            payload = validated_result.model_dump_json(indent=2, warnings="error").encode("utf-8")
        except (ValidationError, PydanticSerializationError):
            raise ResultRepositoryError("Result could not be saved.") from None

        temporary_path: Path | None = None

        try:
            self._result_directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self._result_directory,
                prefix=".result-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, target_path)
        except OSError:
            raise ResultRepositoryError("Result could not be saved.") from None
        finally:
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)

    def get(self, analysis_id: str) -> AnalysisResult | None:
        """Read and validate only the expected UTF-8 result JSON file."""
        target_path = self._target_path(analysis_id)
        if target_path.is_symlink() or not target_path.is_file():
            return None

        try:
            payload = target_path.read_text(encoding="utf-8")
        except UnicodeError:
            raise CorruptedResultError("Stored result is corrupted or invalid.") from None
        except OSError:
            raise ResultRepositoryError("Stored result could not be read.") from None

        try:
            result = AnalysisResult.model_validate_json(payload)
        except ValidationError:
            raise CorruptedResultError("Stored result is corrupted or invalid.") from None

        if result.analysis_id != analysis_id:
            raise CorruptedResultError("Stored result is corrupted or invalid.")
        return result

    def exists(self, analysis_id: str) -> bool:
        """Check only the expected regular result file for an analysis ID."""
        target_path = self._target_path(analysis_id)
        return not target_path.is_symlink() and target_path.is_file()

    def list_recent(self, limit: int) -> list[AnalysisResultSummary]:
        """List valid direct result files using deterministic domain ordering."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        try:
            entries = list(self._result_directory.iterdir())
        except FileNotFoundError:
            return []
        except OSError:
            raise ResultRepositoryError("Stored results could not be listed.") from None

        summaries: list[AnalysisResultSummary] = []
        for entry in entries:
            try:
                is_candidate_file = not entry.is_symlink() and entry.is_file()
            except OSError:
                raise ResultRepositoryError("Stored results could not be listed.") from None
            if not is_candidate_file or entry.suffix != ".json":
                continue

            analysis_id = entry.stem
            try:
                self._target_path(analysis_id)
            except InvalidAnalysisIdError:
                continue

            try:
                payload = entry.read_text(encoding="utf-8")
            except UnicodeError:
                continue
            except OSError:
                raise ResultRepositoryError("Stored results could not be listed.") from None

            try:
                result = AnalysisResult.model_validate_json(payload)
            except ValidationError:
                continue
            if result.analysis_id != analysis_id:
                continue

            summaries.append(AnalysisResultSummary.from_result(result))

        summaries.sort(key=lambda summary: summary.analysis_id)
        summaries.sort(key=lambda summary: summary.created_at, reverse=True)
        return summaries[:limit]

    def _target_path(self, analysis_id: str) -> Path:
        """Build a target path from one unchanged, safe analysis ID component."""
        windows_target = PureWindowsPath(f"{analysis_id}.json")
        if (
            not analysis_id
            or analysis_id in {".", ".."}
            or "/" in analysis_id
            or "\\" in analysis_id
            or ":" in analysis_id
            or "\0" in analysis_id
            or PureWindowsPath(analysis_id).drive
            or windows_target.is_reserved()
        ):
            raise InvalidAnalysisIdError("Analysis ID is not a safe path component.")

        return self._result_directory / f"{analysis_id}.json"
