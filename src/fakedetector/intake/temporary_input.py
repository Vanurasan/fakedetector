"""Local ownership of one controlled temporary input file."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import BinaryIO, Literal, Protocol, TypeVar

_SOURCE_NAME = "source"
_DEFAULT_CHUNK_SIZE = 64 * 1024
_OperationResult = TypeVar("_OperationResult")


class ReadableBinaryStream(Protocol):
    """Caller-owned binary stream supporting only bounded reads."""

    def read(self, size: int, /) -> bytes:
        """Read at most *size* bytes without transferring stream ownership."""
        ...


class FileTooLargeError(Exception):
    """Controlled pre-detection resource-limit condition."""

    code = "file_too_large"
    category = "resource_limit"

    def __init__(self, *, max_size_bytes: int, observed_size_bytes: int) -> None:
        super().__init__("Input exceeds the configured size limit.")
        self.max_size_bytes = max_size_bytes
        self.observed_size_bytes = observed_size_bytes


class IntakeSystemError(Exception):
    """Safe internal failure that does not classify the input as invalid media."""

    def __init__(self, phase: str) -> None:
        super().__init__("Controlled intake failed.")
        self.phase = phase


class TemporaryInputCleanupError(Exception):
    """Safe failure raised when owned temporary data could not be removed."""

    def __init__(
        self,
        *,
        original_file_deleted: bool = False,
        intermediate_files_deleted: bool = False,
    ) -> None:
        super().__init__("Temporary input cleanup did not complete.")
        self.original_file_deleted = original_file_deleted
        self.intermediate_files_deleted = intermediate_files_deleted


@dataclass(frozen=True, slots=True)
class IntakeMeasurements:
    """Size and digest measured during one successful intake pass."""

    size_bytes: int
    sha256: str


class _OwnedResource:
    """Shared private lifecycle state for capabilities referencing one source."""

    __slots__ = ("analysis_id", "owner_token", "source_path", "state", "workspace_path")

    def __init__(
        self,
        *,
        analysis_id: str,
        workspace_path: Path,
        source_path: Path,
        owner_token: object,
    ) -> None:
        self.analysis_id = analysis_id
        self.workspace_path = workspace_path
        self.source_path = source_path
        self.owner_token = owner_token
        self.state: Literal["owned", "handed_off", "released"] = "owned"


class OwnedSource:
    """Opaque internal handle for one source owned by temporary intake."""

    __slots__ = ("_active", "_resource")

    def __init__(
        self,
        *,
        analysis_id: str,
        workspace_path: Path,
        source_path: Path,
        owner_token: object,
        resource: _OwnedResource | None = None,
    ) -> None:
        self._resource = resource or _OwnedResource(
            analysis_id=analysis_id,
            workspace_path=workspace_path,
            source_path=source_path,
            owner_token=owner_token,
        )
        self._active = True

    @property
    def analysis_id(self) -> str:
        """Return the non-path system identifier associated with this source."""
        return self._resource.analysis_id

    @property
    def is_released(self) -> bool:
        """Return whether cleanup has factually released this ownership."""
        return self._resource.state == "released"

    @property
    def is_handed_off(self) -> bool:
        """Return whether this stale capability has been moved downstream."""
        return self._resource.state == "handed_off"


class AcceptedSource:
    """Opaque move-only capability accepted by the downstream lifecycle."""

    __slots__ = ("_owned_source", "_owner")

    def __init__(self, owner: LocalTemporaryInputOwner, owned_source: OwnedSource) -> None:
        self._owner = owner
        self._owned_source = owned_source

    @property
    def analysis_id(self) -> str:
        """Return the system identifier without exposing a filesystem path."""
        return self._owned_source.analysis_id

    @property
    def is_released(self) -> bool:
        """Return whether downstream cleanup factually released the source."""
        return self._owned_source.is_released

    @contextmanager
    def open_for_read(self) -> Iterator[BinaryIO]:
        """Open the active downstream source through controlled ownership."""
        with self._owner.open_for_read(self._owned_source) as source:
            yield source

    def cleanup(self) -> None:
        """Release the downstream source without exposing physical storage."""
        self._owner.cleanup(self._owned_source)


class LocalTemporaryInputOwner:
    """Own exactly one fixed-name source inside each isolated analysis workspace."""

    def __init__(self, root_path: str | os.PathLike[str], *, chunk_size: int = _DEFAULT_CHUNK_SIZE):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        self._root_path = Path(root_path)
        self._chunk_size = chunk_size
        self._owner_token = object()

    def create(self, analysis_id: str) -> OwnedSource:
        """Create and take ownership of a new isolated workspace."""
        workspace_path = self._safe_workspace_path(analysis_id)
        try:
            self._root_path.mkdir(mode=0o700, parents=True, exist_ok=True)
            workspace_path.mkdir(mode=0o700, exist_ok=False)
        except OSError:
            raise IntakeSystemError("workspace") from None

        return OwnedSource(
            analysis_id=analysis_id,
            workspace_path=workspace_path,
            source_path=workspace_path / _SOURCE_NAME,
            owner_token=self._owner_token,
        )

    def validate_analysis_id(self, analysis_id: object) -> None:
        """Validate a generated identifier before registration is established."""
        if not isinstance(analysis_id, str):
            raise IntakeSystemError("analysis_id")
        self._safe_workspace_path(analysis_id)

    def ingest(
        self,
        owned_source: OwnedSource,
        stream: ReadableBinaryStream,
        hard_limit_bytes: int,
    ) -> IntakeMeasurements:
        """Write bounded chunks while measuring exact size and SHA-256 once."""
        self._require_active_handle(owned_source)
        if hard_limit_bytes < 0:
            raise ValueError("hard_limit_bytes must not be negative")

        descriptor = self._open_output(owned_source)
        size_bytes = 0
        digest = hashlib.sha256()

        try:
            while True:
                remaining_bytes = hard_limit_bytes - size_bytes
                read_size = min(self._chunk_size, remaining_bytes + 1)
                try:
                    chunk = stream.read(read_size)
                except Exception:
                    raise IntakeSystemError("stream_read") from None

                if not isinstance(chunk, bytes) or len(chunk) > read_size:
                    raise IntakeSystemError("stream_read")
                if not chunk:
                    break
                if len(chunk) > remaining_bytes:
                    raise FileTooLargeError(
                        max_size_bytes=hard_limit_bytes,
                        observed_size_bytes=size_bytes + len(chunk),
                    )

                self._write_all(descriptor, chunk)
                size_bytes += len(chunk)
                digest.update(chunk)
        except BaseException:
            with suppress(OSError):
                os.close(descriptor)
            raise

        try:
            os.close(descriptor)
        except OSError:
            raise IntakeSystemError("output_write") from None

        return IntakeMeasurements(size_bytes=size_bytes, sha256=digest.hexdigest())

    @contextmanager
    def open_for_read(self, owned_source: OwnedSource) -> Iterator[BinaryIO]:
        """Open an active controlled source without exposing its filesystem path."""
        self._require_active_handle(owned_source)
        try:
            source = owned_source._resource.source_path.open("rb")
        except OSError:
            raise IntakeSystemError("controlled_source_read") from None

        with source:
            yield source

    def with_local_source_path(
        self,
        owned_source: OwnedSource,
        trusted_operation: Callable[[Path], _OperationResult],
    ) -> _OperationResult:
        """Run a trusted seekable-file operation without publishing the source path."""
        self._require_active_handle(owned_source)
        return trusted_operation(owned_source._resource.source_path)

    def transfer(self, owned_source: OwnedSource) -> AcceptedSource:
        """Move one active Stage 3 handle into a downstream capability."""
        self._require_active_handle(owned_source)
        transferred = OwnedSource(
            analysis_id=owned_source._resource.analysis_id,
            workspace_path=owned_source._resource.workspace_path,
            source_path=owned_source._resource.source_path,
            owner_token=self._owner_token,
            resource=owned_source._resource,
        )
        owned_source._resource.state = "handed_off"
        owned_source._active = False
        return AcceptedSource(self, transferred)

    def cleanup(self, owned_source: OwnedSource) -> None:
        """Remove only the fixed source and its now-empty owned workspace."""
        self._require_own_handle(owned_source)
        if not owned_source._active:
            raise IntakeSystemError("ownership")
        if owned_source._resource.state == "released":
            return
        if owned_source._resource.state not in {"owned", "handed_off"}:
            raise IntakeSystemError("ownership")

        original_file_deleted = False
        try:
            owned_source._resource.source_path.unlink(missing_ok=True)
            original_file_deleted = True
            with suppress(FileNotFoundError):
                owned_source._resource.workspace_path.rmdir()
        except OSError:
            raise TemporaryInputCleanupError(
                original_file_deleted=original_file_deleted,
                intermediate_files_deleted=False,
            ) from None

        owned_source._resource.state = "released"

    def _safe_workspace_path(self, analysis_id: str) -> Path:
        """Build one unchanged direct child after cross-platform lexical checks."""
        windows_component = PureWindowsPath(analysis_id)
        if (
            not analysis_id
            or analysis_id in {".", ".."}
            or "/" in analysis_id
            or "\\" in analysis_id
            or ":" in analysis_id
            or "\0" in analysis_id
            or windows_component.drive
            or windows_component.is_reserved()
        ):
            raise IntakeSystemError("analysis_id")

        workspace_path = self._root_path / analysis_id
        if workspace_path.parent != self._root_path:
            raise IntakeSystemError("analysis_id")
        return workspace_path

    def _open_output(self, owned_source: OwnedSource) -> int:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        try:
            return os.open(owned_source._resource.source_path, flags, 0o600)
        except OSError:
            raise IntakeSystemError("output_open") from None

    @staticmethod
    def _write_all(descriptor: int, chunk: bytes) -> None:
        remaining = memoryview(chunk)
        while remaining:
            try:
                written = os.write(descriptor, remaining)
            except OSError:
                raise IntakeSystemError("output_write") from None
            if written <= 0:
                raise IntakeSystemError("output_write")
            remaining = remaining[written:]

    def _require_own_handle(self, owned_source: OwnedSource) -> None:
        if owned_source._resource.owner_token is not self._owner_token:
            raise IntakeSystemError("ownership")

    def _require_active_handle(self, owned_source: OwnedSource) -> None:
        self._require_own_handle(owned_source)
        if not owned_source._active or owned_source._resource.state == "released":
            raise IntakeSystemError("ownership")
