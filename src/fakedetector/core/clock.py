"""Testable clock contracts for application services."""

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Provide the current time through structural dependency injection."""

    def now(self) -> datetime:
        """Return the current time."""
        ...


class UtcClock:
    """Provide timezone-aware current UTC timestamps."""

    def now(self) -> datetime:
        """Return an aware datetime whose timezone is strictly UTC."""
        return datetime.now(UTC)
