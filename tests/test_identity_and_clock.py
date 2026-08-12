"""Contract tests for opaque analysis IDs and injectable UTC clocks."""

from __future__ import annotations

import inspect
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import fakedetector.core.identity as identity_module
from fakedetector.core import (
    AnalysisIdGenerator,
    Clock,
    UtcClock,
    Uuid4AnalysisIdGenerator,
)
from fakedetector.repositories import JsonFileResultRepository


class FakeClock:
    """A structural test double that does not inherit from Clock."""

    def __init__(self, fixed_time: datetime) -> None:
        self._fixed_time = fixed_time

    def now(self) -> datetime:
        return self._fixed_time


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
