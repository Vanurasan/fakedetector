"""Local ownership of one controlled temporary input file."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PureWindowsPath
from threading import RLock
from typing import BinaryIO, Literal, Protocol, TypeVar

from fakedetector._filesystem import (
    ensure_private_directory,
    open_regular_file_for_read,
    require_direct_child_directory,
    require_missing_path,
    require_regular_file,
    require_safe_tree,
)

_SOURCE_NAME = "source"
_DEFAULT_CHUNK_SIZE = 64 * 1024
_SYSTEM_ANALYSIS_ID = re.compile(r"^[0-9a-f]{32}$")
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


class TemporaryInputQuarantineError(Exception):
    """Safe failure raised when an owned workspace cannot enter quarantine."""

    def __init__(self) -> None:
        super().__init__("Temporary input quarantine did not complete.")


@dataclass(frozen=True, slots=True)
class IntakeMeasurements:
    """Size and digest measured during one successful intake pass."""

    size_bytes: int
    sha256: str


class _OwnedResource:
    """Shared private lifecycle state for capabilities referencing one source."""

    __slots__ = (
        "analysis_id",
        "operation_lock",
        "owner_token",
        "source_path",
        "state",
        "workspace_path",
    )

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
        self.operation_lock = RLock()
        self.state: Literal["owned", "handed_off", "quarantined", "released"] = "owned"


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

    def with_local_source_path(
        self,
        trusted_operation: Callable[[Path], _OperationResult],
    ) -> _OperationResult:
        """Run a trusted local-path operation through the active owner boundary."""
        return self._owner.with_local_source_path(self._owned_source, trusted_operation)

    def cleanup(self) -> None:
        """Release the downstream source without exposing physical storage."""
        self._owner.cleanup(self._owned_source)

    def _commit_handoff(self, accept: Callable[[], _OperationResult]) -> _OperationResult:
        """Keep pre-handoff protection through the receiver's logical commit."""
        return self._owner._commit_handoff(self._owned_source, accept)

    def _quarantine(self, modified_at: datetime) -> None:
        """Move the remaining workspace to the owner's fixed recovery location."""
        self._owner._quarantine(self._owned_source, modified_at)

    def _cleanup_quarantine(self) -> bool:
        """Release this source only when it owns the current quarantine item."""
        return self._owner._cleanup_quarantine(self._owned_source)


@dataclass(frozen=True, slots=True)
class PreparedSourceRef:
    """Narrow internal source capability for media preprocessing."""

    _accepted_source: AcceptedSource = field(repr=False)

    @property
    def analysis_id(self) -> str:
        """Return the source identity without exposing ownership operations."""
        return self._accepted_source.analysis_id

    @contextmanager
    def open_for_read(self) -> Iterator[BinaryIO]:
        """Open the accepted source through its existing controlled boundary."""
        with self._accepted_source.open_for_read() as source:
            yield source

    def with_local_source_path(
        self,
        trusted_operation: Callable[[Path], _OperationResult],
    ) -> _OperationResult:
        """Run one trusted preprocessing operation without retaining its path."""
        return self._accepted_source.with_local_source_path(trusted_operation)

    def _references(self, accepted_source: AcceptedSource) -> bool:
        """Return whether this ref wraps the exact accepted source capability."""
        return self._accepted_source is accepted_source


class LocalTemporaryInputOwner:
    """Own exactly one fixed-name source inside each isolated analysis workspace."""

    def __init__(self, root_path: str | os.PathLike[str], *, chunk_size: int = _DEFAULT_CHUNK_SIZE):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        self._root_path = Path(root_path)
        self._chunk_size = chunk_size
        self._owner_token = object()
        self._ownership_lock = RLock()
        self._pre_handoff_analysis_ids: set[str] = set()
        self._janitor_cleanup_claims: set[str] = set()

    def create(self, analysis_id: str) -> OwnedSource:
        """Create and take ownership of a new isolated workspace."""
        workspace_path = self._safe_workspace_path(analysis_id)
        with self._ownership_lock:
            if (
                analysis_id in self._pre_handoff_analysis_ids
                or analysis_id in self._janitor_cleanup_claims
            ):
                raise IntakeSystemError("ownership")
            self._pre_handoff_analysis_ids.add(analysis_id)

        try:
            ensure_private_directory(self._root_path)
            workspace_path.mkdir(mode=0o700, exist_ok=False)
            require_direct_child_directory(self._root_path, workspace_path)
        except OSError:
            with self._ownership_lock:
                self._pre_handoff_analysis_ids.remove(analysis_id)
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
            self._require_resource_workspace(owned_source._resource)
            source = open_regular_file_for_read(owned_source._resource.source_path)
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
        try:
            self._require_resource_workspace(owned_source._resource)
            require_regular_file(owned_source._resource.source_path)
        except OSError:
            raise IntakeSystemError("controlled_source_read") from None
        return trusted_operation(owned_source._resource.source_path)

    def transfer(self, owned_source: OwnedSource) -> AcceptedSource:
        """Move one active Stage 3 handle into a downstream capability."""
        with owned_source._resource.operation_lock, self._ownership_lock:
            self._require_active_handle(owned_source)
            if owned_source.analysis_id not in self._pre_handoff_analysis_ids:
                raise IntakeSystemError("ownership")
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

    def _commit_handoff(
        self,
        owned_source: OwnedSource,
        accept: Callable[[], _OperationResult],
    ) -> _OperationResult:
        """Atomically replace pre-handoff protection with Stage 4 ownership."""
        with owned_source._resource.operation_lock:
            with self._ownership_lock:
                self._require_active_handle(owned_source)
                analysis_id = owned_source.analysis_id
                if (
                    owned_source._resource.state != "handed_off"
                    or analysis_id not in self._pre_handoff_analysis_ids
                ):
                    raise IntakeSystemError("ownership")
            result = accept()
            with self._ownership_lock:
                self._pre_handoff_analysis_ids.remove(analysis_id)
            return result

    def _cleanup_if_unprotected(
        self,
        analysis_id: str,
        cleanup: Callable[[], _OperationResult],
    ) -> _OperationResult | None:
        """Claim one unprotected identity before running janitor cleanup unlocked."""
        with self._ownership_lock:
            if (
                analysis_id in self._pre_handoff_analysis_ids
                or analysis_id in self._janitor_cleanup_claims
            ):
                return None
            self._janitor_cleanup_claims.add(analysis_id)

        try:
            return cleanup()
        finally:
            with self._ownership_lock:
                self._janitor_cleanup_claims.remove(analysis_id)

    def cleanup(self, owned_source: OwnedSource) -> None:
        """Remove only the fixed source and its now-empty owned workspace."""
        with owned_source._resource.operation_lock:
            self._require_own_handle(owned_source)
            if not owned_source._active:
                raise IntakeSystemError("ownership")
            resource = owned_source._resource
            if resource.state == "released":
                return
            if resource.state == "quarantined":
                self._cleanup_quarantined_resource(resource)
                return
            if resource.state not in {"owned", "handed_off"}:
                raise IntakeSystemError("ownership")

            original_file_deleted = False
            try:
                self._require_resource_workspace(resource)
                require_regular_file(resource.source_path, missing_ok=True)
                resource.source_path.unlink(missing_ok=True)
                original_file_deleted = True
                with suppress(FileNotFoundError):
                    require_direct_child_directory(self._root_path, resource.workspace_path)
                    resource.workspace_path.rmdir()
            except OSError:
                self._finish_pre_handoff_cleanup_attempt(resource.analysis_id)
                raise TemporaryInputCleanupError(
                    original_file_deleted=original_file_deleted,
                    intermediate_files_deleted=False,
                ) from None

            resource.state = "released"
            self._finish_pre_handoff_cleanup_attempt(resource.analysis_id)

    def _cleanup_quarantine(self, owned_source: OwnedSource) -> bool:
        """Clean the canonical quarantine item only when this capability owns it."""
        with owned_source._resource.operation_lock:
            self._require_own_handle(owned_source)
            if not owned_source._active:
                raise IntakeSystemError("ownership")
            if owned_source._resource.state != "quarantined":
                return False
            self.cleanup(owned_source)
            return True

    def _cleanup_quarantined_resource(self, resource: _OwnedResource) -> None:
        quarantine_root = self._root_path.parent / "quarantine"
        workspace_path = quarantine_root / resource.analysis_id
        if (
            _SYSTEM_ANALYSIS_ID.fullmatch(resource.analysis_id) is None
            or workspace_path.parent != quarantine_root
            or resource.workspace_path != workspace_path
            or resource.source_path != workspace_path / _SOURCE_NAME
        ):
            raise TemporaryInputCleanupError()

        try:
            try:
                workspace_path.lstat()
            except FileNotFoundError:
                resource.state = "released"
                self._finish_pre_handoff_cleanup_attempt(resource.analysis_id)
                return
            require_direct_child_directory(quarantine_root, workspace_path)
            require_safe_tree(workspace_path)
            shutil.rmtree(workspace_path)
        except OSError:
            try:
                workspace_path.lstat()
            except FileNotFoundError:
                resource.state = "released"
                self._finish_pre_handoff_cleanup_attempt(resource.analysis_id)
                return
            raise TemporaryInputCleanupError(
                original_file_deleted=False,
                intermediate_files_deleted=False,
            ) from None

        resource.state = "released"
        self._finish_pre_handoff_cleanup_attempt(resource.analysis_id)

    def _quarantine(self, owned_source: OwnedSource, modified_at: datetime) -> None:
        """Move one remaining direct workspace to the fixed sibling quarantine."""
        with owned_source._resource.operation_lock:
            self._require_own_handle(owned_source)
            resource = owned_source._resource
            with self._ownership_lock:
                if (
                    not owned_source._active
                    or resource.state != "handed_off"
                    or resource.analysis_id in self._pre_handoff_analysis_ids
                    or _SYSTEM_ANALYSIS_ID.fullmatch(resource.analysis_id) is None
                ):
                    raise TemporaryInputQuarantineError()

            workspace_path = self._safe_workspace_path(resource.analysis_id)
            quarantine_root = self._root_path.parent / "quarantine"
            destination = quarantine_root / resource.analysis_id
            if (
                resource.workspace_path != workspace_path
                or workspace_path.parent != self._root_path
                or destination.parent != quarantine_root
            ):
                raise TemporaryInputQuarantineError()

            try:
                require_direct_child_directory(self._root_path, workspace_path)
                require_safe_tree(workspace_path)
                ensure_private_directory(quarantine_root)
                require_missing_path(destination)
                workspace_path.rename(destination)
                require_direct_child_directory(quarantine_root, destination)
                require_safe_tree(destination)
            except TemporaryInputQuarantineError:
                raise
            except OSError:
                raise TemporaryInputQuarantineError() from None

            resource.workspace_path = destination
            resource.source_path = destination / _SOURCE_NAME
            resource.state = "quarantined"
            with suppress(OSError):
                timestamp = modified_at.timestamp()
                os.utime(destination, (timestamp, timestamp))

    def _finish_pre_handoff_cleanup_attempt(self, analysis_id: str) -> None:
        """End active Stage 3 ownership after one completed physical attempt."""
        with self._ownership_lock:
            self._pre_handoff_analysis_ids.discard(analysis_id)

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
        flags = (
            os.O_CREAT
            | os.O_EXCL
            | os.O_WRONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            self._require_resource_workspace(owned_source._resource)
            require_regular_file(owned_source._resource.source_path, missing_ok=True)
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

    def _require_resource_workspace(self, resource: _OwnedResource) -> None:
        if resource.state == "quarantined":
            root = self._root_path.parent / "quarantine"
        else:
            root = self._root_path
        expected_workspace = root / resource.analysis_id
        if (
            resource.workspace_path != expected_workspace
            or resource.source_path != expected_workspace / _SOURCE_NAME
        ):
            raise IntakeSystemError("ownership")
        require_direct_child_directory(root, resource.workspace_path)
