"""Immutable internal values shared by Stage 5 preprocessing."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePath
from types import MappingProxyType

from fakedetector.domain import MediaType
from fakedetector.intake.temporary_input import PreparedSourceRef
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRef


@dataclass(frozen=True, slots=True)
class PreparedArtifact:
    """One registered Stage 5 artifact without a physical path or media bytes."""

    artifact_id: str
    artifact_type: str
    artifact_ref: WorkspaceArtifactRef = field(repr=False)
    format: str
    start_time_seconds: float | None = None
    end_time_seconds: float | None = None
    frame_index: int | None = None
    cleanup_required: bool = True

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("artifact_id must not be empty")
        if not self.artifact_type:
            raise ValueError("artifact_type must not be empty")
        if not isinstance(self.artifact_ref, WorkspaceArtifactRef):
            raise TypeError("artifact_ref must be a WorkspaceArtifactRef")
        if not self.format:
            raise ValueError("format must not be empty")
        if not self.cleanup_required:
            raise ValueError("prepared artifacts must remain cleanup obligations")
        if self.frame_index is not None and self.frame_index < 0:
            raise ValueError("frame_index must not be negative")
        for field_name, value in (
            ("start_time_seconds", self.start_time_seconds),
            ("end_time_seconds", self.end_time_seconds),
        ):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{field_name} must be finite and non-negative")
        if (
            self.start_time_seconds is not None
            and self.end_time_seconds is not None
            and self.end_time_seconds < self.start_time_seconds
        ):
            raise ValueError("artifact time interval must not regress")


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    """Defensively immutable Stage 5 state for one accepted media source."""

    analysis_id: str
    media_type: MediaType
    source_file_ref: PreparedSourceRef = field(repr=False)
    artifacts: tuple[PreparedArtifact, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.analysis_id:
            raise ValueError("analysis_id must not be empty")
        if not isinstance(self.source_file_ref, PreparedSourceRef):
            raise TypeError("source_file_ref must be a PreparedSourceRef")
        if self.source_file_ref.analysis_id != self.analysis_id:
            raise ValueError("prepared source identity does not match media")

        artifacts = tuple(self.artifacts)
        if any(not isinstance(artifact, PreparedArtifact) for artifact in artifacts):
            raise TypeError("artifacts must contain only PreparedArtifact values")
        artifact_ids = [artifact.artifact_id for artifact in artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("prepared artifacts contain conflicting IDs")

        warnings = tuple(self.warnings)
        if any(not isinstance(warning, str) for warning in warnings):
            raise TypeError("warnings must contain only strings")

        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        object.__setattr__(self, "warnings", warnings)


def _freeze_metadata(metadata: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping")
    frozen: dict[str, object] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise TypeError("metadata keys must be strings")
        frozen[key] = _freeze_metadata_value(value)
    return MappingProxyType(frozen)


def _freeze_metadata_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_metadata(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_metadata_value(item) for item in value)
    if isinstance(value, (PurePath, bytes, bytearray, memoryview)):
        raise TypeError("metadata cannot contain paths or binary data")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise TypeError("metadata contains an unsupported value")
