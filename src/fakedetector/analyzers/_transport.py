"""Private bounded and spawn-picklable analyzer worker transport values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from fakedetector.domain import MediaType

_MAX_RESPONSE_BYTES = 65_536
_MAX_SETTINGS_BYTES = 8_192
_MAX_METADATA_BYTES = 32_768
_MAX_DESCRIPTOR_BYTES = 16_384
_MAX_PATH_CHARS = 4_096
_MAX_ARTIFACTS = 256
_MAX_WARNINGS = 64
_MAX_WARNING_CHARS = 512


class _WorkerResponseKind(StrEnum):
    RESULT = "result"
    ANALYZER_ERROR = "analyzer_error"
    SERIALIZATION_ERROR = "serialization_error"
    WORKER_ERROR = "worker_error"


@dataclass(frozen=True, slots=True, repr=False)
class _WorkerArtifact:
    artifact_id: str
    artifact_type: str
    local_path: str
    format: str
    start_time_seconds: float | None = None
    end_time_seconds: float | None = None
    frame_index: int | None = None

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.artifact_type or not self.format:
            raise ValueError("worker artifact facts are incomplete")
        if not self.local_path or len(self.local_path) > _MAX_PATH_CHARS:
            raise ValueError("worker artifact path is invalid")


@dataclass(frozen=True, slots=True, repr=False)
class _WorkerRequest:
    """Only transport-safe facts passed from parent to a spawned worker."""

    worker_key: str
    analysis_id: str
    media_type: str
    validated_file_json: str
    source_path: str
    artifacts: tuple[_WorkerArtifact, ...]
    metadata_json: str
    warnings: tuple[str, ...]
    settings_json: str
    timeout_seconds: float

    def __post_init__(self) -> None:
        artifacts = tuple(self.artifacts)
        warnings = tuple(self.warnings)
        if not self.worker_key or not self.analysis_id:
            raise ValueError("worker request identity is incomplete")
        if self.media_type not in {media_type.value for media_type in MediaType}:
            raise ValueError("worker request media type is invalid")
        if not self.source_path or len(self.source_path) > _MAX_PATH_CHARS:
            raise ValueError("worker source path is invalid")
        if len(artifacts) > _MAX_ARTIFACTS:
            raise ValueError("worker request has too many artifacts")
        if len(warnings) > _MAX_WARNINGS or any(
            not isinstance(warning, str) or len(warning) > _MAX_WARNING_CHARS
            for warning in warnings
        ):
            raise ValueError("worker request warnings are invalid")
        for value, limit in (
            (self.validated_file_json, _MAX_DESCRIPTOR_BYTES),
            (self.metadata_json, _MAX_METADATA_BYTES),
            (self.settings_json, _MAX_SETTINGS_BYTES),
        ):
            if len(value.encode("utf-8")) > limit:
                raise ValueError("worker request JSON is too large")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("worker timeout must be finite and positive")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "warnings", warnings)
