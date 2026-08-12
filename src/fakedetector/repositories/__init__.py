"""Result repository contracts and implementations."""

from fakedetector.repositories.result_repository import (
    CorruptedResultError,
    InvalidAnalysisIdError,
    JsonFileResultRepository,
    ResultRepository,
    ResultRepositoryError,
)

__all__ = [
    "CorruptedResultError",
    "InvalidAnalysisIdError",
    "JsonFileResultRepository",
    "ResultRepository",
    "ResultRepositoryError",
]
