"""Filesystem and streaming tests for controlled temporary input ownership."""

from __future__ import annotations

import hashlib
import os
from io import BytesIO
from pathlib import Path
from typing import NoReturn

import pytest

import fakedetector.intake.temporary_input as temporary_input_module
from fakedetector.intake import (
    FileTooLargeError,
    IntakeSystemError,
    LocalTemporaryInputOwner,
    TemporaryInputCleanupError,
)


class SyntheticStream:
    """Generate repeated bytes only when a bounded read requests them."""

    def __init__(self, total_size: int, *, byte: bytes = b"x") -> None:
        self.remaining = total_size
        self.byte = byte
        self.requests: list[int] = []

    def read(self, size: int, /) -> bytes:
        if size <= 0:
            raise AssertionError("intake must make only positive bounded reads")
        self.requests.append(size)
        amount = min(size, self.remaining)
        self.remaining -= amount
        return self.byte * amount


class FailingReadStream:
    """Return one partial chunk and then fail with unsafe details."""

    def __init__(self) -> None:
        self._calls = 0

    def read(self, size: int, /) -> bytes:
        self._calls += 1
        if self._calls == 1:
            return b"partial-data"[:size]
        raise OSError("PRIVATE STREAM FAILURE")


def test_large_synthetic_stream_is_read_and_hashed_in_bounded_chunks(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp", chunk_size=4096)
    owned_source = owner.create("large-safe-id")
    total_size = 2 * 1024 * 1024 + 123
    stream = SyntheticStream(total_size, byte=b"z")

    measurements = owner.ingest(owned_source, stream, total_size + 100)

    expected_digest = hashlib.sha256()
    remaining = total_size
    while remaining:
        amount = min(4096, remaining)
        expected_digest.update(b"z" * amount)
        remaining -= amount
    assert measurements.size_bytes == total_size
    assert measurements.sha256 == expected_digest.hexdigest()
    assert max(stream.requests) <= 4096
    assert len(stream.requests) > 2
    assert stream.remaining == 0

    owner.cleanup(owned_source)


def test_input_exactly_at_limit_is_accepted_with_bounded_eof_probe(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp", chunk_size=4)
    owned_source = owner.create("exact-limit")
    stream = SyntheticStream(8, byte=b"a")

    measurements = owner.ingest(owned_source, stream, 8)

    assert measurements.size_bytes == 8
    assert measurements.sha256 == hashlib.sha256(b"a" * 8).hexdigest()
    assert stream.requests == [4, 4, 1]
    assert not owned_source.is_released
    assert (tmp_path / "temp" / "exact-limit" / "source").read_bytes() == b"a" * 8

    owner.cleanup(owned_source)


def test_above_limit_stops_after_one_overflow_byte_without_writing_it(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp", chunk_size=4)
    owned_source = owner.create("above-limit")
    stream = SyntheticStream(20, byte=b"b")

    with pytest.raises(FileTooLargeError) as error_info:
        owner.ingest(owned_source, stream, 8)

    assert error_info.value.code == "file_too_large"
    assert error_info.value.category == "resource_limit"
    assert error_info.value.max_size_bytes == 8
    assert error_info.value.observed_size_bytes == 9
    assert stream.requests == [4, 4, 1]
    assert stream.remaining == 11
    assert (tmp_path / "temp" / "above-limit" / "source").read_bytes() == b"b" * 8

    owner.cleanup(owned_source)
    assert not (tmp_path / "temp" / "above-limit").exists()


@pytest.mark.parametrize(
    "unsafe_id",
    ["", ".", "..", "../escape", "..\\escape", "/absolute", "folder/name", "C:drive", "CON"],
)
def test_unsafe_analysis_id_is_rejected_before_workspace_creation(
    tmp_path: Path,
    unsafe_id: str,
) -> None:
    root = tmp_path / "temp"
    owner = LocalTemporaryInputOwner(root)

    with pytest.raises(IntakeSystemError) as error_info:
        owner.create(unsafe_id)

    assert error_info.value.phase == "analysis_id"
    assert not root.exists()
    assert not (tmp_path / "escape").exists()


def test_workspace_collision_is_not_reused_or_removed(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    workspace = root / "same-id"
    workspace.mkdir(parents=True)
    marker = workspace / "keep.txt"
    marker.write_text("preserve", encoding="utf-8")
    owner = LocalTemporaryInputOwner(root)

    with pytest.raises(IntakeSystemError) as error_info:
        owner.create("same-id")

    assert error_info.value.phase == "workspace"
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_released_source_cannot_be_read(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    owned_source = owner.create("released-source")
    owner.ingest(owned_source, BytesIO(b"content"), 100)
    owner.cleanup(owned_source)

    assert owned_source.is_released
    with (
        pytest.raises(IntakeSystemError, match="Controlled intake failed"),
        owner.open_for_read(owned_source),
    ):
        pass


def test_trusted_local_path_operation_preserves_opaque_active_ownership(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    owned_source = owner.create("trusted-operation")
    owner.ingest(owned_source, BytesIO(b"content"), 100)

    observed = owner.with_local_source_path(
        owned_source,
        lambda path: (path.name, path.read_bytes()),
    )

    assert observed == ("source", b"content")
    assert not owned_source.is_released
    assert not hasattr(owned_source, "source_path")
    owner.cleanup(owned_source)


def test_trusted_local_path_operation_rejects_foreign_and_released_handles(
    tmp_path: Path,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "first")
    foreign_owner = LocalTemporaryInputOwner(tmp_path / "second")
    owned_source = owner.create("owned")
    owner.ingest(owned_source, BytesIO(b"content"), 100)

    with pytest.raises(IntakeSystemError):
        foreign_owner.with_local_source_path(owned_source, lambda path: path)

    owner.cleanup(owned_source)
    with pytest.raises(IntakeSystemError):
        owner.with_local_source_path(owned_source, lambda path: path)


def test_cleanup_failure_keeps_ownership_active_and_does_not_remove_foreign_data(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temp"
    owner = LocalTemporaryInputOwner(root)
    owned_source = owner.create("foreign-data")
    owner.ingest(owned_source, BytesIO(b"owned"), 100)
    foreign_file = root / "foreign-data" / "foreign.txt"
    foreign_file.write_text("do-not-delete", encoding="utf-8")

    with pytest.raises(TemporaryInputCleanupError):
        owner.cleanup(owned_source)

    assert not owned_source.is_released
    assert foreign_file.read_text(encoding="utf-8") == "do-not-delete"
    assert not (root / "foreign-data" / "source").exists()


def test_stream_read_failure_closes_output_descriptor(tmp_path: Path, monkeypatch) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    owned_source = owner.create("read-failure")
    real_open = temporary_input_module.os.open
    opened_descriptors: list[int] = []

    def recording_open(path: os.PathLike[str], flags: int, mode: int) -> int:
        descriptor = real_open(path, flags, mode)
        opened_descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(temporary_input_module.os, "open", recording_open)

    with pytest.raises(IntakeSystemError) as error_info:
        owner.ingest(owned_source, FailingReadStream(), 100)

    assert error_info.value.phase == "stream_read"
    assert len(opened_descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(opened_descriptors[0])
    owner.cleanup(owned_source)


def test_short_write_is_completed_without_losing_bytes(tmp_path: Path, monkeypatch) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    owned_source = owner.create("short-write")
    real_write = temporary_input_module.os.write
    writes = 0

    def short_write(descriptor: int, data: bytes | memoryview) -> int:
        nonlocal writes
        writes += 1
        return real_write(descriptor, data[:2])

    monkeypatch.setattr(temporary_input_module.os, "write", short_write)

    measurements = owner.ingest(owned_source, BytesIO(b"abcdef"), 100)

    assert writes == 3
    assert measurements.size_bytes == 6
    assert (tmp_path / "temp" / "short-write" / "source").read_bytes() == b"abcdef"
    owner.cleanup(owned_source)


def test_binary_newline_bytes_are_not_translated_on_windows(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    owned_source = owner.create("binary-newlines")
    payload = b"before\ninside\r\nafter\r"

    measurements = owner.ingest(owned_source, BytesIO(payload), 100)

    with owner.open_for_read(owned_source) as source:
        assert source.read() == payload
    assert measurements.size_bytes == len(payload)
    assert measurements.sha256 == hashlib.sha256(payload).hexdigest()
    owner.cleanup(owned_source)


def test_write_failure_closes_descriptor_and_remains_safe(tmp_path: Path, monkeypatch) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "PRIVATE-TEMP")
    owned_source = owner.create("write-failure")
    real_write = temporary_input_module.os.write
    real_open = temporary_input_module.os.open
    opened_descriptor: int | None = None
    write_calls = 0

    def recording_open(path: os.PathLike[str], flags: int, mode: int) -> int:
        nonlocal opened_descriptor
        opened_descriptor = real_open(path, flags, mode)
        return opened_descriptor

    def failing_write(descriptor: int, data: bytes | memoryview) -> int:
        nonlocal write_calls
        write_calls += 1
        if write_calls == 1:
            return real_write(descriptor, data[:2])
        raise OSError("PRIVATE WRITE FAILURE")

    monkeypatch.setattr(temporary_input_module.os, "open", recording_open)
    monkeypatch.setattr(temporary_input_module.os, "write", failing_write)

    with pytest.raises(IntakeSystemError) as error_info:
        owner.ingest(owned_source, BytesIO(b"abcdef"), 100)

    assert error_info.value.phase == "output_write"
    assert "PRIVATE" not in str(error_info.value)
    assert opened_descriptor is not None
    with pytest.raises(OSError):
        os.fstat(opened_descriptor)
    owner.cleanup(owned_source)


def test_output_open_failure_is_safe(tmp_path: Path, monkeypatch) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "PRIVATE-TEMP")
    owned_source = owner.create("open-failure")

    def fail_open(_path: os.PathLike[str], _flags: int, _mode: int) -> NoReturn:
        raise OSError("PRIVATE OPEN FAILURE")

    monkeypatch.setattr(temporary_input_module.os, "open", fail_open)

    with pytest.raises(IntakeSystemError) as error_info:
        owner.ingest(owned_source, BytesIO(b"data"), 100)

    assert error_info.value.phase == "output_open"
    assert "PRIVATE" not in str(error_info.value)
    owner.cleanup(owned_source)
