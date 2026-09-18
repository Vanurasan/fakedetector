"""Closed trusted built-in catalog plus spawn-importable framework test analyzers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from fakedetector.analyzers._audio_pcm import (
    AudioPcmQualityAnalyzer,
    AudioPcmQualitySettings,
)
from fakedetector.analyzers._image_copy_move import (
    ImageCopyMoveCorrespondenceAnalyzer,
    ImageCopyMoveCorrespondenceSettings,
)
from fakedetector.analyzers._image_metadata import (
    ImageMetadataConsistencyAnalyzer,
    ImageMetadataConsistencySettings,
)
from fakedetector.analyzers._models import (
    Analyzer,
    AnalyzerRegistration,
    AnalyzerRequest,
    ApplicabilityResult,
)
from fakedetector.analyzers._real_common import _MAX_REAL_ANALYZER_CANDIDATES
from fakedetector.analyzers._video_frames import (
    VideoSampledFrameQualityAnalyzer,
    VideoSampledFrameQualitySettings,
)
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, MediaType
from fakedetector.preprocessing._requirements import PreprocessingRequirements


class _FakeAnalyzerSettings(BaseModel):
    """Small typed settings contract used only by the framework test analyzers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicable: bool = Field(default=True, strict=True)


class _FakeAnalyzerBase:
    analyzer_id: ClassVar[str]
    analyzer_name: ClassVar[str]
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "framework_test"
    supported_media_types: ClassVar[frozenset[MediaType]]

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        settings = request.settings
        if not isinstance(settings, _FakeAnalyzerSettings):
            raise TypeError("unexpected settings contract")
        if not settings.applicable:
            return ApplicabilityResult(False, "disabled_by_test_setting")
        return ApplicabilityResult(True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        with request.source.open_for_read() as source:
            source.read(1)
        for artifact in request.artifacts:
            with artifact.content.open_for_read() as content:
                content.read(1)
        return _completed_result(self, request)


class _FakeImageAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_image_analyzer"
    analyzer_name = "Stage 5 fake image analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})


class _FakeImageSecondAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_image_second_analyzer"
    analyzer_name = "Stage 5 second fake image analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})


class _FakeAudioAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_audio_analyzer"
    analyzer_name = "Stage 5 fake audio analyzer"
    supported_media_types = frozenset({MediaType.AUDIO})


class _FakeVideoAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_video_analyzer"
    analyzer_name = "Stage 5 fake video analyzer"
    supported_media_types = frozenset({MediaType.VIDEO})


class _FakeErrorAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_error_analyzer"
    analyzer_name = "Stage 5 fake error analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        del request
        raise RuntimeError("worker-only test exception")


class _FakeHangAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_hang_analyzer"
    analyzer_name = "Stage 5 fake hanging analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        del request
        time.sleep(60.0)
        raise AssertionError("hanging analyzer unexpectedly resumed")


class _FakeCrashAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_crash_analyzer"
    analyzer_name = "Stage 5 fake crashing analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        del request
        os._exit(7)


class _FakeSerializationAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_serialization_analyzer"
    analyzer_name = "Stage 5 fake serialization analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        result = _completed_result(self, request)
        result.__dict__["raw_metrics"] = {"unsafe": object()}
        return result


@dataclass(frozen=True, slots=True)
class _WorkerAnalyzerDefinition:
    worker_key: str
    analyzer_id: str
    analyzer_name: str
    analyzer_version: str
    group: str
    supported_media_types: frozenset[MediaType]
    settings_model: type[BaseModel]
    factory: type[Analyzer]
    preprocessing_requirements: PreprocessingRequirements
    candidate_finding_types: frozenset[str]
    max_candidate_findings: int

    def registration(self) -> AnalyzerRegistration:
        return AnalyzerRegistration(
            analyzer_id=self.analyzer_id,
            analyzer_name=self.analyzer_name,
            analyzer_version=self.analyzer_version,
            group=self.group,
            supported_media_types=self.supported_media_types,
            worker_key=self.worker_key,
            settings_model=self.settings_model,
            preprocessing_requirements=self.preprocessing_requirements,
            candidate_finding_types=self.candidate_finding_types,
            max_candidate_findings=self.max_candidate_findings,
        )


def _definition(
    worker_key: str,
    analyzer_type: type[Analyzer],
    *,
    settings_model: type[BaseModel] = _FakeAnalyzerSettings,
    preprocessing_requirements: PreprocessingRequirements | None = None,
    candidate_finding_types: frozenset[str] = frozenset(),
    max_candidate_findings: int = 0,
) -> _WorkerAnalyzerDefinition:
    return _WorkerAnalyzerDefinition(
        worker_key=worker_key,
        analyzer_id=analyzer_type.analyzer_id,
        analyzer_name=analyzer_type.analyzer_name,
        analyzer_version=analyzer_type.analyzer_version,
        group=analyzer_type.group,
        supported_media_types=analyzer_type.supported_media_types,
        settings_model=settings_model,
        factory=analyzer_type,
        preprocessing_requirements=(preprocessing_requirements or PreprocessingRequirements()),
        candidate_finding_types=candidate_finding_types,
        max_candidate_findings=max_candidate_findings,
    )


_FRAMEWORK_TEST_DEFINITIONS = (
    _definition("framework_test.image", _FakeImageAnalyzer),
    _definition("framework_test.image_second", _FakeImageSecondAnalyzer),
    _definition(
        "framework_test.audio",
        _FakeAudioAnalyzer,
        preprocessing_requirements=PreprocessingRequirements(audio_spectrogram=True),
    ),
    _definition(
        "framework_test.video",
        _FakeVideoAnalyzer,
        preprocessing_requirements=PreprocessingRequirements(video_audio_track=True),
    ),
    _definition("framework_test.error", _FakeErrorAnalyzer),
    _definition("framework_test.hang", _FakeHangAnalyzer),
    _definition("framework_test.crash", _FakeCrashAnalyzer),
    _definition("framework_test.serialization", _FakeSerializationAnalyzer),
)

_BUILT_IN_ANALYZER_DEFINITIONS = (
    _definition(
        "stage6.image_metadata_consistency.v1",
        ImageMetadataConsistencyAnalyzer,
        settings_model=ImageMetadataConsistencySettings,
        candidate_finding_types=frozenset({"image_metadata_dimension_mismatch"}),
        max_candidate_findings=_MAX_REAL_ANALYZER_CANDIDATES,
    ),
    _definition(
        "stage6.audio_pcm_quality.v1",
        AudioPcmQualityAnalyzer,
        settings_model=AudioPcmQualitySettings,
        candidate_finding_types=frozenset({"audio_full_scale_saturation"}),
        max_candidate_findings=_MAX_REAL_ANALYZER_CANDIDATES,
    ),
    _definition(
        "stage6.video_sampled_frame_quality.v1",
        VideoSampledFrameQualityAnalyzer,
        settings_model=VideoSampledFrameQualitySettings,
        candidate_finding_types=frozenset(
            {"video_sample_resolution_change", "repeated_sampled_video_frames"}
        ),
        max_candidate_findings=_MAX_REAL_ANALYZER_CANDIDATES,
    ),
    _definition(
        "stage6.image_copy_move_correspondence.v1",
        ImageCopyMoveCorrespondenceAnalyzer,
        settings_model=ImageCopyMoveCorrespondenceSettings,
        candidate_finding_types=frozenset({"repeated_image_region_correspondence"}),
        max_candidate_findings=8,
    ),
)

_WORKER_DEFINITIONS = MappingProxyType(
    {
        definition.worker_key: definition
        for definition in (*_FRAMEWORK_TEST_DEFINITIONS, *_BUILT_IN_ANALYZER_DEFINITIONS)
    }
)
_BUILT_IN_DEFINITIONS_BY_ID = MappingProxyType(
    {
        definition.analyzer_id: definition
        for definition in _BUILT_IN_ANALYZER_DEFINITIONS
    }
)


def _resolve_worker_definition(worker_key: str) -> _WorkerAnalyzerDefinition | None:
    return _WORKER_DEFINITIONS.get(worker_key)


def _resolve_built_in_analyzer_definition(
    analyzer_id: str,
) -> _WorkerAnalyzerDefinition | None:
    """Resolve only first-party production analyzers by canonical ID."""
    return _BUILT_IN_DEFINITIONS_BY_ID.get(analyzer_id)


def _framework_test_registrations() -> tuple[AnalyzerRegistration, ...]:
    """Return explicit internal registrations; none are active in default config."""
    return tuple(definition.registration() for definition in _FRAMEWORK_TEST_DEFINITIONS)


def _built_in_analyzer_registrations() -> tuple[AnalyzerRegistration, ...]:
    """Return the complete first-party production catalog in canonical order."""
    return tuple(definition.registration() for definition in _BUILT_IN_ANALYZER_DEFINITIONS)


def _built_in_analyzer_ids(media_type: MediaType) -> tuple[str, ...]:
    """Return the catalog order for one supported production media path."""
    if not isinstance(media_type, MediaType):
        raise TypeError("media_type must be MediaType")
    return tuple(
        definition.analyzer_id
        for definition in _BUILT_IN_ANALYZER_DEFINITIONS
        if media_type in definition.supported_media_types
    )


def _completed_result(
    analyzer: _FakeAnalyzerBase,
    request: AnalyzerRequest,
) -> AnalyzerResult:
    return AnalyzerResult(
        analyzer_id=analyzer.analyzer_id,
        analyzer_version=analyzer.analyzer_version,
        media_type=request.media_type,
        group=analyzer.group,
        status=AnalyzerStatus.COMPLETED,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=0,
        score=None,
        score_name=None,
        summary="Stage 5 framework test analyzer completed.",
        raw_metrics={},
        candidate_findings=[],
        warnings=[],
        errors=[],
    )
