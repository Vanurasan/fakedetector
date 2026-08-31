"""Raw and authoritative testable clock contracts for application services."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock
from time import monotonic_ns
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


class AuthoritativeClockError(Exception):
    """Safe failure when no authoritative lifecycle timestamp can be emitted."""

    def __init__(self) -> None:
        super().__init__("Authoritative lifecycle time is unavailable.")


class AuthoritativeClockInvariantError(AuthoritativeClockError):
    """Report an internal monotonic or lower-bound contract violation."""


class AuthoritativeLifecycleClock:
    """Emit one resilient authoritative UTC domain from untrusted raw samples."""

    def __init__(
        self,
        raw_clock: Clock,
        *,
        monotonic_source: Callable[[], int] = monotonic_ns,
    ) -> None:
        self._raw_clock = raw_clock
        self._monotonic_source = monotonic_source
        self._lock = RLock()
        self._calendar_anchor: datetime | None = None
        self._monotonic_anchor: int | None = None

    def now(self, *, not_before: datetime | None = None) -> datetime:
        """Emit current authoritative time, validating rather than repairing bounds."""
        with self._lock:
            self._validate_lower_bound(not_before)
            raw_sample = self._sample_raw()
            monotonic_sample = self._sample_monotonic()
            if (
                self._monotonic_anchor is not None
                and monotonic_sample < self._monotonic_anchor
            ):
                raise AuthoritativeClockInvariantError()
            if self._valid_raw_sample(raw_sample, not_before=not_before):
                assert isinstance(raw_sample, datetime)
                self._set_anchor(raw_sample, monotonic_sample)
                return raw_sample

            if self._calendar_anchor is None or self._monotonic_anchor is None:
                raise AuthoritativeClockError()
            elapsed_ns = monotonic_sample - self._monotonic_anchor
            if elapsed_ns < 0:
                raise AuthoritativeClockInvariantError()
            emitted = self._calendar_anchor + _nanoseconds_as_timedelta(elapsed_ns)
            if not_before is not None and emitted < not_before:
                raise AuthoritativeClockInvariantError()
            self._set_anchor(emitted, monotonic_sample)
            return emitted

    def terminal_now(self, *, not_before: datetime) -> datetime:
        """Emit a post-workflow terminal timestamp subject to a strict lower bound."""
        return self.now(not_before=not_before)

    def _sample_raw(self) -> object:
        try:
            return self._raw_clock.now()
        except Exception:
            return None

    def _sample_monotonic(self) -> int:
        try:
            sample = self._monotonic_source()
        except Exception:
            raise AuthoritativeClockInvariantError() from None
        if not isinstance(sample, int):
            raise AuthoritativeClockInvariantError()
        return sample

    def _valid_raw_sample(self, sample: object, *, not_before: datetime | None) -> bool:
        if not isinstance(sample, datetime) or sample.tzinfo is None:
            return False
        try:
            offset = sample.utcoffset()
        except Exception:
            return False
        if offset is None or offset.total_seconds() != 0:
            return False
        if self._calendar_anchor is not None and sample < self._calendar_anchor:
            return False
        return not_before is None or sample >= not_before

    @staticmethod
    def _validate_lower_bound(not_before: datetime | None) -> None:
        if not_before is None:
            return
        if not isinstance(not_before, datetime) or not_before.tzinfo is None:
            raise AuthoritativeClockInvariantError()
        try:
            offset = not_before.utcoffset()
        except Exception:
            raise AuthoritativeClockInvariantError() from None
        if offset is None or offset.total_seconds() != 0:
            raise AuthoritativeClockInvariantError()

    def _set_anchor(self, calendar: datetime, monotonic: int) -> None:
        self._calendar_anchor = calendar
        self._monotonic_anchor = monotonic


def _nanoseconds_as_timedelta(value: int) -> timedelta:
    return timedelta(microseconds=value // 1_000)
