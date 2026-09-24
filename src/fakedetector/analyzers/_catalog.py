"""Closed trusted first-party production analyzer catalog."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel

from fakedetector.analyzers._audio_pcm import (
    AudioPcmQualityAnalyzer,
    AudioPcmQualitySettings,
)
from fakedetector.analyzers._image_copy_move import (
    ImageCopyMoveCorrespondenceAnalyzer,
    ImageCopyMoveCorrespondenceSettings,
)
from fakedetector.analyzers._image_jpeg_dq import (
    ImageJpegDoubleQuantizationAnalyzer,
    ImageJpegDoubleQuantizationSettings,
)
from fakedetector.analyzers._image_metadata import (
    ImageMetadataConsistencyAnalyzer,
    ImageMetadataConsistencySettings,
)
from fakedetector.analyzers._models import (
    Analyzer,
    AnalyzerRegistration,
)
from fakedetector.analyzers._real_common import _MAX_REAL_ANALYZER_CANDIDATES
from fakedetector.analyzers._video_frames import (
    VideoSampledFrameQualityAnalyzer,
    VideoSampledFrameQualitySettings,
)
from fakedetector.domain import MediaType
from fakedetector.preprocessing._requirements import ForensicCapability, PreprocessingRequirements


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


_WorkerDefinitionResolver = Callable[[str], _WorkerAnalyzerDefinition | None]


def _definition(
    worker_key: str,
    analyzer_type: type[Analyzer],
    *,
    settings_model: type[BaseModel],
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
    _definition(
        "stage12.image_jpeg_double_quantization.v1",
        ImageJpegDoubleQuantizationAnalyzer,
        settings_model=ImageJpegDoubleQuantizationSettings,
        preprocessing_requirements=PreprocessingRequirements(
            forensic=frozenset({ForensicCapability.JPEG_COEFFICIENTS}),
        ),
        candidate_finding_types=frozenset({"jpeg_recompression_pattern"}),
        max_candidate_findings=1,
    ),
)

_WORKER_DEFINITIONS = MappingProxyType(
    {
        definition.worker_key: definition
        for definition in _BUILT_IN_ANALYZER_DEFINITIONS
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
