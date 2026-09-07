"""Private Stage 5 generated-artifact count and byte-budget capabilities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import BinaryIO, cast

from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.domain import MediaType

_BYTES_PER_MEBIBYTE = 1_048_576
_MAX_STAGE5_ARTIFACTS = 256


class _GeneratedArtifactLimitError(Exception):
    """Signal that a generated artifact would exceed its task-local byte budget."""


class _GeneratedArtifactWriteError(OSError):
    """Signal a safe physical output failure without exposing its path."""


class _GeneratedArtifactBudget:
    """Enforce cumulative maximum physical extents for one task and media type."""

    __slots__ = ("_max_bytes", "_media_type", "_snapshot", "_used_bytes")

    def __init__(self, snapshot: _ConfigSnapshot, media_type: MediaType) -> None:
        if not isinstance(snapshot, _ConfigSnapshot):
            raise TypeError("artifact budget requires a config snapshot")
        if not isinstance(media_type, MediaType):
            raise TypeError("artifact budget requires a media type")
        limits = snapshot.materialize().limits.max_file_size_mb
        max_mebibytes = {
            MediaType.IMAGE: limits.image,
            MediaType.AUDIO: limits.audio,
            MediaType.VIDEO: limits.video,
        }[media_type]
        self._snapshot = snapshot
        self._media_type = media_type
        self._max_bytes = max_mebibytes * _BYTES_PER_MEBIBYTE
        self._used_bytes = 0

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def used_bytes(self) -> int:
        return self._used_bytes

    @property
    def media_type(self) -> MediaType:
        return self._media_type

    @property
    def remaining_bytes(self) -> int:
        return self._max_bytes - self._used_bytes

    def matches(self, snapshot: _ConfigSnapshot, media_type: MediaType) -> bool:
        """Return whether this capability belongs to the authoritative task snapshot."""
        return self._snapshot == snapshot and self._media_type is media_type

    def ensure_feasible(self, estimated_bytes: int) -> None:
        """Reject a conservative preflight estimate without consuming the budget."""
        if not isinstance(estimated_bytes, int) or isinstance(estimated_bytes, bool):
            raise TypeError("artifact estimate must be an integer")
        if estimated_bytes < 0:
            raise ValueError("artifact estimate must not be negative")
        if estimated_bytes > self.remaining_bytes:
            raise _GeneratedArtifactLimitError

    @contextmanager
    def open_output(self, target: Path) -> Iterator[BinaryIO]:
        """Create one exclusive bounded file and retain every claimed extent."""
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = target.open("xb")
        except OSError:
            raise _GeneratedArtifactWriteError from None

        output = _BoundedArtifactWriter(raw, self)
        try:
            yield cast(BinaryIO, output)
        except BaseException:
            with suppress(_GeneratedArtifactWriteError):
                output.close()
            raise
        else:
            output.close()

    def _claim_extent(self, additional_bytes: int) -> None:
        if additional_bytes <= 0:
            return
        if additional_bytes > self.remaining_bytes:
            raise _GeneratedArtifactLimitError
        self._used_bytes += additional_bytes


class _BoundedArtifactWriter:
    """File proxy charging only growth of the maximum physical file extent."""

    __slots__ = ("_budget", "_closed", "_extent", "_stream")

    def __init__(self, stream: BinaryIO, budget: _GeneratedArtifactBudget) -> None:
        self._stream = stream
        self._budget = budget
        self._extent = 0
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def write(self, data: bytes | bytearray | memoryview) -> int:
        try:
            position = self._stream.tell()
        except OSError:
            raise _GeneratedArtifactWriteError from None
        byte_count = memoryview(data).nbytes
        target_extent = max(self._extent, position + byte_count)
        self._budget._claim_extent(target_extent - self._extent)
        self._extent = target_extent
        try:
            written = self._stream.write(data)
        except OSError:
            raise _GeneratedArtifactWriteError from None
        if written != byte_count:
            raise _GeneratedArtifactWriteError
        return written

    def seek(self, offset: int, whence: int = 0) -> int:
        try:
            return self._stream.seek(offset, whence)
        except OSError:
            raise _GeneratedArtifactWriteError from None

    def tell(self) -> int:
        try:
            return self._stream.tell()
        except OSError:
            raise _GeneratedArtifactWriteError from None

    def truncate(self, size: int | None = None) -> int:
        target_size = self.tell() if size is None else size
        if target_size < 0:
            raise ValueError("artifact size must not be negative")
        target_extent = max(self._extent, target_size)
        self._budget._claim_extent(target_extent - self._extent)
        self._extent = target_extent
        try:
            return self._stream.truncate(size)
        except OSError:
            raise _GeneratedArtifactWriteError from None

    def flush(self) -> None:
        try:
            self._stream.flush()
        except OSError:
            raise _GeneratedArtifactWriteError from None

    def fileno(self) -> int:
        try:
            return self._stream.fileno()
        except OSError:
            raise _GeneratedArtifactWriteError from None

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._stream.close()
        except OSError:
            raise _GeneratedArtifactWriteError from None
        finally:
            self._closed = True

    def __enter__(self) -> _BoundedArtifactWriter:
        return self

    def __exit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        self.close()
