"""Minimal controlled-workspace artifact cleanup obligations for Stage 4."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath, PureWindowsPath
from typing import TypeVar

_SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_COMPONENT = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_OperationResult = TypeVar("_OperationResult")


class ArtifactRegistrationError(Exception):
    """Safe rejection of an invalid or duplicate application artifact obligation."""

    def __init__(self) -> None:
        super().__init__("Artifact cleanup obligation is invalid.")


@dataclass(frozen=True, slots=True)
class ArtifactCleanupOutcome:
    """Factual result of one immediate artifact cleanup pass."""

    completed: bool


@dataclass(frozen=True, slots=True, repr=False)
class WorkspaceArtifactRef:
    """Opaque capability for one registry-owned artifact obligation."""

    _registry_token: object
    _artifact_id: str

    def __repr__(self) -> str:
        return "WorkspaceArtifactRef()"


class WorkspaceArtifactRegistry:
    """Track application-named files constrained to one controlled workspace."""

    def __init__(self, workspace_path: Path) -> None:
        self._workspace_path = workspace_path
        self._registry_token = object()
        self._obligations: dict[str, Path] = {}
        self._windows_targets: set[tuple[str, ...]] = set()
        self._completed: set[str] = set()
        self._pending_directories: set[Path] = set()

    def register(self, artifact_id: str, relative_path: str) -> WorkspaceArtifactRef:
        """Register one safe application-generated relative file obligation."""
        pure_path = PurePath(relative_path)
        windows_path = PureWindowsPath(relative_path)
        components = pure_path.parts
        invalid = (
            _SAFE_ID.fullmatch(artifact_id) is None
            or artifact_id in self._obligations
            or not components
            or pure_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or any(
                component in {".", ".."}
                or component != component.rstrip(" .")
                or _SAFE_COMPONENT.fullmatch(component) is None
                or PureWindowsPath(component).is_reserved()
                for component in components
            )
        )
        if invalid:
            raise ArtifactRegistrationError()
        candidate = self._workspace_path.joinpath(*components)
        windows_target = tuple(component.lower() for component in components)
        if (
            candidate == self._workspace_path
            or self._workspace_path not in candidate.parents
            or windows_target in self._windows_targets
        ):
            raise ArtifactRegistrationError()
        self._obligations[artifact_id] = candidate
        self._windows_targets.add(windows_target)
        return WorkspaceArtifactRef(self._registry_token, artifact_id)

    def with_local_artifact_path(
        self,
        artifact_ref: WorkspaceArtifactRef,
        trusted_operation: Callable[[Path], _OperationResult],
    ) -> _OperationResult:
        """Run one trusted operation for an active registered artifact target."""
        artifact_id = self._require_active_ref(artifact_ref)
        return trusted_operation(self._obligations[artifact_id])

    def cleanup_obligations(self) -> tuple[Path, ...]:
        """Return deterministic internal paths for lifecycle-owned cleanup."""
        return tuple(self._obligations[key] for key in sorted(self._obligations))

    def cleanup_once(self) -> ArtifactCleanupOutcome:
        """Attempt each registered file exactly once without following directories."""
        completed = True
        parent_directories = set(self._pending_directories)
        for artifact_id in sorted(self._obligations):
            if artifact_id in self._completed:
                continue
            path = self._obligations[artifact_id]
            try:
                path.unlink(missing_ok=True)
                self._completed.add(artifact_id)
                parent_directories.update(
                    parent
                    for parent in path.parents
                    if parent != self._workspace_path and self._workspace_path in parent.parents
                )
            except OSError:
                completed = False
        for directory in sorted(parent_directories, key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except FileNotFoundError:
                self._pending_directories.discard(directory)
            except OSError:
                completed = False
                self._pending_directories.add(directory)
            else:
                self._pending_directories.discard(directory)
        return ArtifactCleanupOutcome(completed=completed)

    def _require_active_ref(self, artifact_ref: WorkspaceArtifactRef) -> str:
        if not self._matches_registered_artifact(artifact_ref):
            raise ArtifactRegistrationError()
        return artifact_ref._artifact_id

    def _matches_registered_artifact(
        self,
        artifact_ref: object,
        artifact_id: str | None = None,
    ) -> bool:
        """Confirm one active ref and optional ID without exposing registry internals."""
        return (
            isinstance(artifact_ref, WorkspaceArtifactRef)
            and artifact_ref._registry_token is self._registry_token
            and artifact_ref._artifact_id in self._obligations
            and artifact_ref._artifact_id not in self._completed
            and (artifact_id is None or artifact_ref._artifact_id == artifact_id)
        )
