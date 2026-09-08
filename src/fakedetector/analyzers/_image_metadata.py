"""Objective bounded consistency checks for source image metadata."""

from __future__ import annotations

from contextlib import suppress
from typing import ClassVar

from PIL import Image
from pydantic import BaseModel, ConfigDict

from fakedetector.analyzers._candidates import (
    _ImageMetadataDimensionMismatchCandidate,
    _TypedCandidate,
)
from fakedetector.analyzers._models import AnalyzerRequest, ApplicabilityResult
from fakedetector.analyzers._real_common import _completed_real_result
from fakedetector.domain import (
    AnalyzerResult,
    FileLocalization,
    ImageTechnicalParameters,
    MediaType,
)

_EXIF_IMAGE_WIDTH = 0xA002
_EXIF_IMAGE_HEIGHT = 0xA003
_IMAGE_WIDTH = 0x0100
_IMAGE_HEIGHT = 0x0101
_ORIENTATION = 0x0112
_SOFTWARE = 0x0131
_SUPPORTED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
_XMP_INFO_KEYS = frozenset({"xmp", "xml:com.adobe.xmp", "raw profile type xmp"})
_STRUCTURAL_INFO_KEYS = frozenset(
    {
        "background",
        "dpi",
        "duration",
        "jfif",
        "jfif_density",
        "jfif_unit",
        "jfif_version",
        "loop",
        "progression",
        "progressive",
        "timestamp",
        "transparency",
    }
)


class ImageMetadataConsistencySettings(BaseModel):
    """No configurable policy is needed for the v1 factual checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ImageMetadataConsistencyAnalyzer:
    analyzer_id: ClassVar[str] = "image_metadata_consistency"
    analyzer_name: ClassVar[str] = "Image metadata consistency"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "metadata"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.IMAGE})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        parameters = request.file_facts.technical_parameters
        if request.media_type is not MediaType.IMAGE or not isinstance(
            parameters, ImageTechnicalParameters
        ):
            return ApplicabilityResult(False, "media_type")
        if parameters.format.upper() not in _SUPPORTED_FORMATS:
            return ApplicabilityResult(False, "source_format")
        return ApplicabilityResult(True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        settings = request.settings
        if not isinstance(settings, ImageMetadataConsistencySettings):
            raise TypeError("unexpected settings contract")

        parameters = request.file_facts.technical_parameters
        if not isinstance(parameters, ImageTechnicalParameters):
            raise TypeError("image technical parameters are required")

        with (
            request.source.open_for_read() as source,
            Image.open(source, formats=sorted(_SUPPORTED_FORMATS)) as image,
        ):
            image.load()
            source_format = image.format or parameters.format.upper()
            decoded_width, decoded_height = image.size
            info_keys = {str(key).casefold() for key in image.info}
            icc_present = bool(image.info.get("icc_profile"))
            xmp_present = any(key in _XMP_INFO_KEYS for key in info_keys)
            metadata_info_present = any(key not in _STRUCTURAL_INFO_KEYS for key in info_keys)
            exif = image.getexif()
            exif_present = bool(exif)
            software_tag_present = (
                _present_exif_value(_exif_value(exif, _SOFTWARE)) or "software" in info_keys
            )
            embedded_width = _safe_positive_int(_exif_value(exif, _EXIF_IMAGE_WIDTH, _IMAGE_WIDTH))
            embedded_height = _safe_positive_int(
                _exif_value(exif, _EXIF_IMAGE_HEIGHT, _IMAGE_HEIGHT)
            )
            orientation = _safe_orientation(_exif_value(exif, _ORIENTATION))

        dimensions_available = embedded_width is not None and embedded_height is not None
        dimensions_consistent: bool | None = None
        if dimensions_available and orientation is not None:
            assert embedded_width is not None and embedded_height is not None
            dimensions_consistent = (embedded_width, embedded_height) == (
                decoded_width,
                decoded_height,
            )

        candidates: tuple[_TypedCandidate, ...] = ()
        if dimensions_consistent is False:
            candidates = (
                _ImageMetadataDimensionMismatchCandidate(
                    type="image_metadata_dimension_mismatch",
                    localization=FileLocalization(type="file"),
                    correlation_group="image_metadata_consistency",
                    evidence_refs=(),
                ),
            )

        return _completed_real_result(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            group=self.group,
            request=request,
            summary="Available source image metadata was checked for objective consistency.",
            raw_metrics={
                "source_format": source_format,
                "decoded_width": decoded_width,
                "decoded_height": decoded_height,
                "metadata_present": exif_present or metadata_info_present,
                "exif_present": exif_present,
                "xmp_present": xmp_present,
                "icc_present": icc_present,
                "software_tag_present": software_tag_present,
                "embedded_pixel_width": embedded_width,
                "embedded_pixel_height": embedded_height,
                "orientation": orientation,
                "embedded_dimensions_available": dimensions_available,
                "embedded_dimensions_consistent": dimensions_consistent,
            },
            candidates=candidates,
        )


def _exif_value(exif: Image.Exif, *tags: int) -> object:
    for tag in tags:
        value = exif.get(tag)
        if value is not None:
            return value
    with suppress(AttributeError, KeyError, TypeError, ValueError):
        nested = exif.get_ifd(0x8769)
        for tag in tags:
            value = nested.get(tag)
            if value is not None:
                return value
    return None


def _safe_positive_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _safe_orientation(value: object) -> int | None:
    if value is None:
        return 1
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 8:
        return value
    return None


def _present_exif_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, (bytes, str)):
        return bool(value)
    return True
