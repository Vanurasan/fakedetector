"""Minimal controlled-workspace artifact cleanup obligations for Stage 4."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePath, PureWindowsPath

_SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_COMPONENT = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


class ArtifactRegistrationError(Exception):
    """Safe rejection of an invalid or duplicate application artifact obligation."""

    def __init__(self) -> None:
        super().__init__("Artifact cleanup obligation is invalid.")


@dataclass(frozen=True, slots=True)
class ArtifactCleanupOutcome:
    """Factual result of one immediate artifact cleanup pass."""

    completed: bool


class WorkspaceArtifactRegistry:
    """Track application-named files constrained to one controlled workspace."""

    def __init__(self, workspace_path: Path) -> None:
        self._workspace_path = workspace_path
        self._obligations: dict[str, Path] = {}

    def register(self, artifact_id: str, relative_path: str) -> None:
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
                or _SAFE_COMPONENT.fullmatch(component) is None
                or PureWindowsPath(component).is_reserved()
                for component in components
            )
        )
        if invalid:
            raise ArtifactRegistrationError()
        candidate = self._workspace_path.joinpath(*components)
        if candidate == self._workspace_path or self._workspace_path not in candidate.parents:
            raise ArtifactRegistrationError()
        self._obligations[artifact_id] = candidate

    def cleanup_obligations(self) -> tuple[Path, ...]:
        """Return deterministic internal paths for lifecycle-owned cleanup."""
        return tuple(self._obligations[key] for key in sorted(self._obligations))

    def cleanup_once(self) -> ArtifactCleanupOutcome:
        """Attempt each registered file exactly once without following directories."""
        completed = True
        parent_directories: set[Path] = set()
        for path in self.cleanup_obligations():
            try:
                path.unlink(missing_ok=True)
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
                continue
            except OSError:
                completed = False
        return ArtifactCleanupOutcome(completed=completed)
