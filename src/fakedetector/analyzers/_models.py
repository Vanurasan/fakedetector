"""Worker-local analyzer contracts and trusted registration metadata."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import BinaryIO, ClassVar, Protocol

from pydantic import BaseModel

from fakedetector.analyzers._errors import _AnalyzerInputReadError
from fakedetector.domain import AnalyzerResult, MediaType, ValidatedFileDescriptor
from fakedetector.preprocessing._requirements import PreprocessingRequirements

_SAFE_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True, slots=True)
class ApplicabilityResult:
    """Deterministic applicability decision with a bounded machine-safe reason."""

    applicable: bool
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.applicable, bool):
            raise TypeError("applicable must be a boolean")
        if self.applicable and self.reason_code is not None:
            raise ValueError("applicable decision cannot contain a reason")
        if not self.applicable and (
            self.reason_code is None or _SAFE_REASON_CODE.fullmatch(self.reason_code) is None
        ):
            raise ValueError("non-applicable decision requires a safe reason code")


@dataclass(frozen=True, slots=True, repr=False)
class _ReadOnlyAnalyzerInput:
    """Worker-local binary read boundary that does not publish its physical path."""

    _local_path: Path = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self._local_path, Path):
            raise TypeError("worker-local input must use a Path")

    @contextmanager
    def open_for_read(self) -> Iterator[BinaryIO]:
        """Open the controlled worker-local input only in binary read mode."""
        try:
            source = self._local_path.open("rb")
        except OSError:
            raise _AnalyzerInputReadError() from None
        with source:
            yield source


@dataclass(frozen=True, slots=True)
class AnalyzerArtifactInput:
    """Read-only prepared artifact facts available to analyzer code."""

    artifact_id: str
    artifact_type: str
    content: _ReadOnlyAnalyzerInput = field(repr=False)
    format: str
    start_time_seconds: float | None = None
    end_time_seconds: float | None = None
    frame_index: int | None = None

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.artifact_type or not self.format:
            raise ValueError("analyzer artifact facts are incomplete")
        if not isinstance(self.content, _ReadOnlyAnalyzerInput):
            raise TypeError("artifact content must be a read-only input")


@dataclass(frozen=True, slots=True)
class AnalyzerRequest:
    """Capability-free request assembled inside one spawned analyzer worker."""

    analysis_id: str
    media_type: MediaType
    validated_file: ValidatedFileDescriptor
    source: _ReadOnlyAnalyzerInput = field(repr=False)
    settings: BaseModel = field(repr=False)
    timeout_seconds: float
    artifacts: tuple[AnalyzerArtifactInput, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.analysis_id:
            raise ValueError("analysis_id must not be empty")
        if not isinstance(self.source, _ReadOnlyAnalyzerInput):
            raise TypeError("source must be a read-only input")
        if not isinstance(self.settings, BaseModel):
            raise TypeError("settings must be a typed Pydantic model")
        if not isinstance(self.validated_file, ValidatedFileDescriptor):
            raise TypeError("validated_file must be a ValidatedFileDescriptor")
        if self.validated_file.media_type is not self.media_type:
            raise ValueError("validated descriptor media type does not match request")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        artifacts = tuple(self.artifacts)
        warnings = tuple(self.warnings)
        if any(not isinstance(artifact, AnalyzerArtifactInput) for artifact in artifacts):
            raise TypeError("artifacts must contain analyzer artifact inputs")
        if any(not isinstance(warning, str) for warning in warnings):
            raise TypeError("warnings must contain strings")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))
        object.__setattr__(self, "warnings", warnings)


class Analyzer(Protocol):
    """Logical contract implemented by trusted worker-resolvable analyzers."""

    analyzer_id: ClassVar[str]
    analyzer_name: ClassVar[str]
    analyzer_version: ClassVar[str]
    group: ClassVar[str]
    supported_media_types: ClassVar[frozenset[MediaType]]

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        """Return one deterministic worker-side applicability decision."""
        ...

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        """Return the existing canonical domain result for an applicable input."""
        ...


@dataclass(frozen=True, slots=True)
class AnalyzerRegistration:
    """Static metadata binding one analyzer ID to a trusted worker catalog key."""

    analyzer_id: str
    analyzer_name: str
    analyzer_version: str
    group: str
    supported_media_types: frozenset[MediaType]
    worker_key: str
    settings_model: type[BaseModel] = field(repr=False)
    preprocessing_requirements: PreprocessingRequirements = field(
        default_factory=PreprocessingRequirements
    )


def _freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("metadata keys must be strings")
            frozen[key] = _freeze_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (PurePath, bytes, bytearray, memoryview)):
        raise TypeError("metadata cannot contain paths or binary data")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("metadata numbers must be finite")
        return value
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError("metadata contains an unsupported value")
