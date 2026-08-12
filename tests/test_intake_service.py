"""Application-level tests for controlled Stage 3 intake."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import NoReturn

import pytest

import fakedetector.intake.temporary_input as temporary_input_module
from fakedetector.config.models import AppConfig
from fakedetector.domain import SourceChannel, SourceContext
from fakedetector.intake import (
    ControlledIntakeService,
    FileTooLargeError,
    IntakeCleanupError,
    IntakeSystemError,
    LocalTemporaryInputOwner,
)


class FixedIdGenerator:
    def __init__(self, *analysis_ids: str) -> None:
        self._analysis_ids = iter(analysis_ids)
        self.calls = 0

    def generate(self) -> str:
        self.calls += 1
        return next(self._analysis_ids)


class FixedClock:
    def __init__(self, timestamp: datetime) -> None:
        self.timestamp = timestamp
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.timestamp


class TrackingStream(BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.requests: list[int] = []

    def read(self, size: int = -1, /) -> bytes:
        if size <= 0:
            raise AssertionError("intake must make only positive bounded reads")
        self.requests.append(size)
        return super().read(size)


class PartialThenFailStream:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, size: int, /) -> bytes:
        self.calls += 1
        if self.calls == 1:
            return b"partial"[:size]
        raise OSError("PRIVATE READ FAILURE")


def make_config(
    temporary_root: Path,
    *,
    image_limit: int = 1,
    audio_limit: int = 1,
    video_limit: int = 1,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {
                "max_file_size_mb": {
                    "image": image_limit,
                    "audio": audio_limit,
                    "video": video_limit,
                }
            },
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {"root_path": str(temporary_root)},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {},
            "error_handling": {},
            "logging": {},
            "external_systems": {},
        }
    )


def make_service(
    tmp_path: Path,
    analysis_id_generator: FixedIdGenerator,
    clock: FixedClock,
    *,
    image_limit: int = 1,
    audio_limit: int = 1,
    video_limit: int = 1,
) -> tuple[ControlledIntakeService, LocalTemporaryInputOwner]:
    root = tmp_path / "temp"
    owner = LocalTemporaryInputOwner(root, chunk_size=4)
    service = ControlledIntakeService(
        config=make_config(
            root,
            image_limit=image_limit,
            audio_limit=audio_limit,
            video_limit=video_limit,
        ),
        analysis_id_generator=analysis_id_generator,
        clock=clock,
        temporary_input_owner=owner,
    )
    return service, owner


def test_normal_controlled_intake_registers_measures_hashes_and_preserves_stream(
    tmp_path: Path,
) -> None:
    timestamp = datetime(2026, 8, 13, 12, 34, 56, tzinfo=UTC)
    generator = FixedIdGenerator("analysis-safe-001")
    clock = FixedClock(timestamp)
    service, owner = make_service(tmp_path, generator, clock)
    stream = TrackingStream(b"controlled-content")
    source = SourceContext(
        channel=SourceChannel.API,
        connector="mail_connector",
        external_system="gateway",
        external_reference="message-1",
    )

    controlled = service.intake(
        stream,
        original_name="message.bin",
        declared_content_type=None,
        source=source,
    )

    assert generator.calls == 1
    assert clock.calls == 1
    assert controlled.analysis_id == "analysis-safe-001"
    assert controlled.registered_at is timestamp
    assert controlled.source is source
    assert controlled.input_file.original_name == "message.bin"
    assert controlled.input_file.declared_content_type is None
    assert controlled.input_file.received_at is timestamp
    assert controlled.input_file.size_bytes == len(b"controlled-content")
    assert controlled.sha256 == hashlib.sha256(b"controlled-content").hexdigest()
    assert stream.requests and max(stream.requests) <= 4
    assert not stream.closed
    assert not controlled.owned_source.is_released

    with owner.open_for_read(controlled.owned_source) as reader:
        assert reader.read() == b"controlled-content"
        assert not reader.closed
    assert reader.closed

    owner.cleanup(controlled.owned_source)


def test_empty_stream_is_measured_without_early_validation_rejection(tmp_path: Path) -> None:
    service, owner = make_service(
        tmp_path,
        FixedIdGenerator("empty-input"),
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
    )

    controlled = service.intake(
        TrackingStream(b""),
        original_name="no-extension",
        declared_content_type=None,
        source=SourceContext(channel=SourceChannel.WEBUI),
    )

    assert controlled.input_file.size_bytes == 0
    assert controlled.sha256 == hashlib.sha256(b"").hexdigest()
    owner.cleanup(controlled.owned_source)


def test_initial_hard_limit_is_maximum_configured_media_limit(tmp_path: Path) -> None:
    service, owner = make_service(
        tmp_path,
        FixedIdGenerator("configured-limit", "configured-limit-oversized"),
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
        image_limit=1,
        audio_limit=3,
        video_limit=2,
    )
    stream = TrackingStream(b"tiny")

    controlled = service.intake(
        stream,
        original_name="claims-image.jpg",
        declared_content_type="image/jpeg",
        source=SourceContext(channel=SourceChannel.API),
    )

    assert stream.requests[0] == 4
    assert controlled.input_file.size_bytes == 4
    # The concrete owner has a 4-byte test chunk, so prove the configured limit
    # independently through the controlled error's byte value.
    oversized = TrackingStream(b"x" * (3 * 1024 * 1024 + 1))
    with pytest.raises(FileTooLargeError) as error_info:
        service.intake(
            oversized,
            original_name="claims-video.mp4",
            declared_content_type="video/mp4",
            source=SourceContext(channel=SourceChannel.API),
        )
    assert error_info.value.max_size_bytes == 3 * 1024 * 1024
    owner.cleanup(controlled.owned_source)


def test_above_limit_is_resource_condition_and_service_cleans_partial_input(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    service, _owner = make_service(
        tmp_path,
        FixedIdGenerator("above-service-limit"),
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
    )
    stream = TrackingStream(b"x" * (1024 * 1024 + 20))

    with pytest.raises(FileTooLargeError) as error_info:
        service.intake(
            stream,
            original_name="anything.bin",
            declared_content_type=None,
            source=SourceContext(channel=SourceChannel.API),
        )

    assert not isinstance(error_info.value, IntakeSystemError)
    assert error_info.value.observed_size_bytes == 1024 * 1024 + 1
    assert stream.tell() == 1024 * 1024 + 1
    assert not stream.closed
    assert not (root / "above-service-limit").exists()


def test_workspaces_are_isolated_and_user_metadata_never_enters_paths(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    generator = FixedIdGenerator("first-safe-id", "second-safe-id")
    service, owner = make_service(
        tmp_path,
        generator,
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
    )
    dangerous = "../first-safe-id/source"
    source = SourceContext(
        channel=SourceChannel.API,
        connector="../../connector",
        external_system="..\\system",
        external_reference=dangerous,
    )

    first = service.intake(
        TrackingStream(b"one"),
        original_name=dangerous,
        declared_content_type="../../mime",
        source=source,
    )
    second = service.intake(
        TrackingStream(b"two"),
        original_name=dangerous,
        declared_content_type="../../mime",
        source=source,
    )

    assert (root / "first-safe-id" / "source").read_bytes() == b"one"
    assert (root / "second-safe-id" / "source").read_bytes() == b"two"
    assert {path.name for path in root.iterdir()} == {"first-safe-id", "second-safe-id"}
    assert [path.name for path in (root / "first-safe-id").iterdir()] == ["source"]
    assert [path.name for path in (root / "second-safe-id").iterdir()] == ["source"]
    owner.cleanup(first.owned_source)
    owner.cleanup(second.owned_source)


def test_output_open_failure_is_cleaned_by_service(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "PRIVATE-TEMP"
    service, _owner = make_service(
        tmp_path,
        FixedIdGenerator("open-system-failure"),
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
    )

    def fail_open(_path: os.PathLike[str], _flags: int, _mode: int) -> NoReturn:
        raise OSError("PRIVATE OPEN FAILURE")

    monkeypatch.setattr(temporary_input_module.os, "open", fail_open)

    with pytest.raises(IntakeSystemError) as error_info:
        service.intake(
            TrackingStream(b"content"),
            original_name="private-name.bin",
            declared_content_type=None,
            source=SourceContext(channel=SourceChannel.API),
        )

    assert error_info.value.phase == "output_open"
    assert "PRIVATE" not in str(error_info.value)
    assert not (tmp_path / "temp" / "open-system-failure").exists()
    assert not root.exists()


def test_partial_read_failure_is_cleaned_and_safe(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    service, _owner = make_service(
        tmp_path,
        FixedIdGenerator("read-system-failure"),
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
    )

    with pytest.raises(IntakeSystemError) as error_info:
        service.intake(
            PartialThenFailStream(),
            original_name="PRIVATE-NAME.bin",
            declared_content_type=None,
            source=SourceContext(channel=SourceChannel.API),
        )

    assert error_info.value.phase == "stream_read"
    assert "PRIVATE" not in str(error_info.value)
    assert not (root / "read-system-failure").exists()


def test_partial_write_failure_is_cleaned_and_safe(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "temp"
    service, _owner = make_service(
        tmp_path,
        FixedIdGenerator("write-system-failure"),
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
    )
    real_write = temporary_input_module.os.write
    calls = 0

    def fail_after_partial_write(descriptor: int, data: bytes | memoryview) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(descriptor, data[:2])
        raise OSError("PRIVATE WRITE FAILURE")

    monkeypatch.setattr(temporary_input_module.os, "write", fail_after_partial_write)

    with pytest.raises(IntakeSystemError) as error_info:
        service.intake(
            TrackingStream(b"content"),
            original_name="PRIVATE-NAME.bin",
            declared_content_type=None,
            source=SourceContext(channel=SourceChannel.API),
        )

    assert error_info.value.phase == "output_write"
    assert "PRIVATE" not in str(error_info.value)
    assert not (root / "write-system-failure").exists()


@pytest.mark.parametrize("primary_kind", ["system", "resource_limit"])
def test_cleanup_failure_preserves_primary_error_and_active_ownership(
    tmp_path: Path,
    monkeypatch,
    primary_kind: str,
) -> None:
    root = tmp_path / "temp"
    service, _owner = make_service(
        tmp_path,
        FixedIdGenerator("cleanup-failure"),
        FixedClock(datetime(2026, 8, 13, tzinfo=UTC)),
    )
    source_path = root / "cleanup-failure" / "source"
    real_unlink = Path.unlink

    def fail_owned_unlink(path: Path, *, missing_ok: bool = False) -> None:
        if path == source_path:
            raise OSError("PRIVATE CLEANUP FAILURE")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_owned_unlink)

    stream = (
        PartialThenFailStream()
        if primary_kind == "system"
        else TrackingStream(b"x" * (1024 * 1024 + 1))
    )

    with pytest.raises(IntakeCleanupError) as error_info:
        service.intake(
            stream,
            original_name="PRIVATE-NAME.bin",
            declared_content_type=None,
            source=SourceContext(channel=SourceChannel.API),
        )

    error = error_info.value
    if primary_kind == "system":
        assert isinstance(error.primary_error, IntakeSystemError)
        assert error.primary_error.phase == "stream_read"
    else:
        assert isinstance(error.primary_error, FileTooLargeError)
        assert error.primary_error.code == "file_too_large"
        assert error.primary_error.category == "resource_limit"
    assert not error.owned_source.is_released
    assert source_path.exists()
    assert "PRIVATE" not in str(error)
