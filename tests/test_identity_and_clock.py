"""Contract tests for opaque analysis IDs and injectable UTC clocks."""

from __future__ import annotations

import inspect
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Lock, Thread

import pytest

import fakedetector.core.identity as identity_module
from fakedetector.core import (
    AnalysisIdGenerator,
    AuthoritativeLifecycleClock,
    Clock,
    UtcClock,
    Uuid4AnalysisIdGenerator,
)
from fakedetector.core.clock import AuthoritativeClockError, AuthoritativeClockInvariantError
from fakedetector.repositories import JsonFileResultRepository


class FakeClock:
    """A structural test double that does not inherit from Clock."""

    def __init__(self, fixed_time: datetime) -> None:
        self._fixed_time = fixed_time

    def now(self) -> datetime:
        return self._fixed_time


class SequenceClock:
    def __init__(self, *samples: object) -> None:
        self._samples = list(samples)
        self._lock = Lock()

    def now(self) -> datetime:
        with self._lock:
            sample = self._samples.pop(0)
        if isinstance(sample, Exception):
            raise sample
        return sample  # type: ignore[return-value]


class MonotonicSequence:
    def __init__(self, *samples: int) -> None:
        self._samples = iter(samples)
        self._lock = Lock()

    def __call__(self) -> int:
        with self._lock:
            return next(self._samples)


def test_uuid4_generator_satisfies_protocol_and_returns_safe_hex() -> None:
    generator = Uuid4AnalysisIdGenerator()

    analysis_id = generator.generate()

    assert isinstance(generator, AnalysisIdGenerator)
    assert isinstance(analysis_id, str)
    assert len(analysis_id) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", analysis_id)


def test_uuid4_generator_uses_exact_uuid_hex(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_uuid = uuid.UUID("12345678-90ab-4def-8123-456789abcdef")
    monkeypatch.setattr(identity_module.uuid, "uuid4", lambda: expected_uuid)

    assert Uuid4AnalysisIdGenerator().generate() == expected_uuid.hex


def test_uuid4_generator_accepts_no_user_arguments_or_data() -> None:
    signature = inspect.signature(Uuid4AnalysisIdGenerator.generate)

    assert list(signature.parameters) == ["self"]
    with pytest.raises(TypeError):
        Uuid4AnalysisIdGenerator().generate("private-filename.jpg")  # type: ignore[call-arg]


def test_generated_id_is_accepted_unchanged_by_repository(tmp_path: Path) -> None:
    analysis_id = Uuid4AnalysisIdGenerator().generate()
    repository = JsonFileResultRepository(tmp_path / "results")

    assert repository.exists(analysis_id) is False
    assert not (tmp_path / "results").exists()


def test_utc_clock_satisfies_protocol_and_returns_strict_utc() -> None:
    clock = UtcClock()

    current_time = clock.now()

    assert isinstance(clock, Clock)
    assert current_time.tzinfo is UTC
    assert current_time.utcoffset() == timedelta(0)
    assert current_time.tzinfo is not None
    assert "utcnow" not in inspect.getsource(UtcClock.now)


def test_fake_clock_structurally_satisfies_protocol_and_is_deterministic() -> None:
    fixed_time = datetime(2026, 8, 12, 12, 34, 56, tzinfo=UTC)
    fake_clock = FakeClock(fixed_time)

    assert isinstance(fake_clock, Clock)
    assert fake_clock.now() is fixed_time


def test_authoritative_clock_accepts_valid_strict_utc_sample() -> None:
    timestamp = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
    clock = AuthoritativeLifecycleClock(
        SequenceClock(timestamp),
        monotonic_source=MonotonicSequence(100),
    )

    assert clock.now() == timestamp


@pytest.mark.parametrize(
    "invalid_sample",
    [
        RuntimeError("raw failure"),
        datetime(2026, 8, 31, 10, 0),
        datetime(2026, 8, 31, 13, 0, tzinfo=__import__("datetime").timezone(timedelta(hours=3))),
        datetime(2026, 8, 31, 9, 59, 59, tzinfo=UTC),
    ],
)
def test_authoritative_clock_degrades_from_anchor_for_invalid_raw_samples(
    invalid_sample: object,
) -> None:
    anchor = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
    clock = AuthoritativeLifecycleClock(
        SequenceClock(anchor, invalid_sample),
        monotonic_source=MonotonicSequence(1_000, 2_001_000),
    )

    assert clock.now() == anchor
    assert clock.now() == anchor + timedelta(milliseconds=2)


def test_future_anchor_degradation_does_not_depend_on_process_wall_clock() -> None:
    future = datetime(2099, 1, 1, tzinfo=UTC)
    clock = AuthoritativeLifecycleClock(
        SequenceClock(future, RuntimeError("wall clock is irrelevant")),
        monotonic_source=MonotonicSequence(10, 1_000_010),
    )

    assert clock.now() == future
    assert clock.now() == future + timedelta(milliseconds=1)


@pytest.mark.parametrize(
    "initial_sample",
    [
        RuntimeError("no anchor"),
        datetime(2026, 8, 31, 10, 0),
        "not a datetime",
    ],
)
def test_authoritative_clock_rejects_initial_invalid_sample_without_anchor(
    initial_sample: object,
) -> None:
    clock = AuthoritativeLifecycleClock(
        SequenceClock(initial_sample),
        monotonic_source=MonotonicSequence(1),
    )

    with pytest.raises(AuthoritativeClockError):
        clock.now()


def test_terminal_lower_bound_is_validated_without_hidden_max_repair() -> None:
    anchor = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
    lower_bound = anchor + timedelta(seconds=5)
    clock = AuthoritativeLifecycleClock(
        SequenceClock(anchor, anchor + timedelta(seconds=1)),
        monotonic_source=MonotonicSequence(0, 1_000_000_000),
    )
    assert clock.now() == anchor

    with pytest.raises(AuthoritativeClockInvariantError):
        clock.terminal_now(not_before=lower_bound)


def test_terminal_lower_bound_rejects_invalid_form() -> None:
    clock = AuthoritativeLifecycleClock(
        SequenceClock(datetime(2026, 8, 31, 10, 0, tzinfo=UTC)),
        monotonic_source=MonotonicSequence(0),
    )

    with pytest.raises(AuthoritativeClockInvariantError):
        clock.terminal_now(not_before=datetime(2026, 8, 31, 10, 0))


def test_regressing_monotonic_source_is_never_masked_by_valid_raw_sample() -> None:
    first = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
    clock = AuthoritativeLifecycleClock(
        SequenceClock(first, first + timedelta(seconds=1)),
        monotonic_source=MonotonicSequence(10, 9),
    )
    assert clock.now() == first

    with pytest.raises(AuthoritativeClockInvariantError):
        clock.now()


def test_concurrent_authoritative_calls_are_non_decreasing() -> None:
    timestamp = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
    count = 8
    clock = AuthoritativeLifecycleClock(
        SequenceClock(*([timestamp] * count)),
        monotonic_source=MonotonicSequence(*range(count)),
    )
    barrier = Barrier(count)
    results: list[datetime] = []
    result_lock = Lock()

    def emit() -> None:
        barrier.wait()
        emitted = clock.now()
        with result_lock:
            results.append(emitted)

    threads = [Thread(target=emit) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == count
    assert results == sorted(results)


def test_one_authoritative_instance_shares_stage3_and_stage4_history() -> None:
    registered_at = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
    shared = AuthoritativeLifecycleClock(
        SequenceClock(registered_at, RuntimeError("stage 4 raw failure")),
        monotonic_source=MonotonicSequence(10, 2_000_010),
    )

    stage3_created_at = shared.now()
    stage4_queued_at = shared.now(not_before=stage3_created_at)

    assert stage4_queued_at == registered_at + timedelta(milliseconds=2)
