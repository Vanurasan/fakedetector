"""Filesystem-backed persistence for validated analysis results."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path, PureWindowsPath
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from fakedetector.domain import AnalysisResult


class ResultRepositoryError(Exception):
    """Base error for safe result repository failures."""


class InvalidAnalysisIdError(ResultRepositoryError, ValueError):
    """Raised when an analysis ID cannot be used as one safe path component."""


class CorruptedResultError(ResultRepositoryError):
    """Raised when stored result data is not a valid AnalysisResult."""


@runtime_checkable
class ResultRepository(Protocol):
    """Currently typeable operations of the canonical result repository.

    ``list_recent`` remains outside this protocol until CONTRACTS.md defines
    ``AnalysisResultSummary`` and its ordering semantics.
    """

    def save(self, result: AnalysisResult) -> None:
        """Persist a validated analysis result."""
        ...

    def get(self, analysis_id: str) -> AnalysisResult | None:
        """Return a validated stored result, or None when it is absent."""
        ...

    def exists(self, analysis_id: str) -> bool:
        """Return whether the expected stored result file exists."""
        ...


class JsonFileResultRepository:
    """Store each AnalysisResult as one atomically replaced UTF-8 JSON file."""

    def __init__(self, result_directory: str | os.PathLike[str]) -> None:
        self._result_directory = Path(result_directory)

    def save(self, result: AnalysisResult) -> None:
        """Atomically save a Pydantic-serialized result under its analysis ID."""
        target_path = self._target_path(result.analysis_id)
        payload = result.model_dump_json(indent=2).encode("utf-8")
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
        if not target_path.is_file() or target_path.is_symlink():
            return None

        try:
            payload = target_path.read_text(encoding="utf-8")
        except UnicodeError:
            raise CorruptedResultError("Stored result is corrupted or invalid.") from None
        except OSError:
            raise ResultRepositoryError("Stored result could not be read.") from None

        try:
            return AnalysisResult.model_validate_json(payload)
        except ValidationError:
            raise CorruptedResultError("Stored result is corrupted or invalid.") from None

    def exists(self, analysis_id: str) -> bool:
        """Check only the expected regular result file for an analysis ID."""
        target_path = self._target_path(analysis_id)
        return target_path.is_file() and not target_path.is_symlink()

    def _target_path(self, analysis_id: str) -> Path:
        """Build a target path from one unchanged, safe analysis ID component."""
        if (
            not analysis_id
            or analysis_id in {".", ".."}
            or "/" in analysis_id
            or "\\" in analysis_id
            or ":" in analysis_id
            or "\0" in analysis_id
            or PureWindowsPath(analysis_id).drive
        ):
            raise InvalidAnalysisIdError("Analysis ID is not a safe path component.")

        return self._result_directory / f"{analysis_id}.json"
