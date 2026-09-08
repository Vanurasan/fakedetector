"""Bounded image-region self-correspondence using OpenCV ORB and RANSAC."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, cast

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from fakedetector.analyzers._candidates import (
    _RepeatedImageRegionCorrespondenceCandidate,
    _TypedCandidate,
)
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    ApplicabilityResult,
)
from fakedetector.analyzers._real_common import _artifacts, _completed_real_result
from fakedetector.domain import (
    AnalyzerResult,
    BoundingBoxLocalization,
    ImageTechnicalParameters,
    MediaType,
)

_MIN_AFFINE_MATCHES = 3
_RANSAC_MAX_ITERS = 2_000
_RANSAC_CONFIDENCE = 0.99
_RANSAC_REFINE_ITERS = 10
_DUPLICATE_REGION_IOU = 0.5


class ImageCopyMoveCorrespondenceSettings(BaseModel):
    """Versioned deterministic and resource-bounded v1 analyzer policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    min_dimension_px: int = Field(default=128, ge=32, le=4_096)
    max_pixels: int = Field(default=12_000_000, ge=16_384, le=12_000_000)
    max_keypoints: int = Field(default=5_000, ge=64, le=5_000)
    descriptor_ratio: float = Field(default=0.75, gt=0, lt=1)
    min_spatial_separation_px: float = Field(default=32.0, ge=1, le=4_096)
    ransac_reprojection_threshold_px: float = Field(default=3.0, gt=0, le=32)
    min_cluster_inliers: int = Field(default=12, ge=_MIN_AFFINE_MATCHES, le=5_000)
    min_cluster_inlier_ratio: float = Field(default=0.5, gt=0, le=1)
    max_clusters: int = Field(default=4, ge=1, le=4)


@dataclass(frozen=True, slots=True)
class _FeatureSet:
    points: NDArray[np.float32]
    descriptors: NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class _Correspondence:
    first: tuple[float, float]
    second: tuple[float, float]
    distance: float


@dataclass(frozen=True, slots=True)
class _PixelBox:
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass(frozen=True, slots=True)
class _RegionPair:
    first: _PixelBox
    second: _PixelBox


@dataclass(frozen=True, slots=True)
class _ClusterMetrics:
    geometric_cluster_count: int
    max_cluster_inlier_count: int
    max_cluster_inlier_ratio: float
    capped: bool


class ImageCopyMoveCorrespondenceAnalyzer:
    analyzer_id: ClassVar[str] = "image_copy_move_correspondence"
    analyzer_name: ClassVar[str] = "Image copy-move correspondence"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "content"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.IMAGE})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        settings = request.settings
        parameters = request.file_facts.technical_parameters
        if (
            request.media_type is not MediaType.IMAGE
            or not isinstance(parameters, ImageTechnicalParameters)
            or not isinstance(settings, ImageCopyMoveCorrespondenceSettings)
        ):
            return ApplicabilityResult(False, "media_type")
        if (
            parameters.width < settings.min_dimension_px
            or parameters.height < settings.min_dimension_px
        ):
            return ApplicabilityResult(False, "image_dimensions")
        if parameters.width * parameters.height > settings.max_pixels:
            return ApplicabilityResult(False, "image_pixels")

        normalized = _normalized_artifact(request)
        if normalized is None:
            return ApplicabilityResult(False, "normalized_image_missing")
        facts = _normalized_header(normalized)
        if facts is None:
            return ApplicabilityResult(False, "normalized_image_contract")
        width, height, _mode = facts
        if width < settings.min_dimension_px or height < settings.min_dimension_px:
            return ApplicabilityResult(False, "image_dimensions")
        if width * height > settings.max_pixels:
            return ApplicabilityResult(False, "image_pixels")
        return ApplicabilityResult(True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        settings = request.settings
        if not isinstance(settings, ImageCopyMoveCorrespondenceSettings):
            raise TypeError("unexpected settings contract")
        normalized = _normalized_artifact(request)
        if normalized is None:
            raise ValueError("one normalized image artifact is required")

        grayscale, mask, width, height = _decode_normalized(normalized, settings)
        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)
        orb = cv2.ORB.create(nfeatures=settings.max_keypoints)
        keypoints, descriptors = orb.detectAndCompute(grayscale, mask)
        feature_set = _ordered_features(keypoints, descriptors)
        keypoint_count = len(feature_set.points)
        descriptor_count = len(feature_set.descriptors)
        spatial_separation = max(
            settings.min_spatial_separation_px,
            0.05 * min(width, height),
        )
        correspondences = _self_correspondences(
            feature_set,
            descriptor_ratio=settings.descriptor_ratio,
            min_spatial_separation=spatial_separation,
        )
        region_pairs, cluster_metrics = _geometric_region_pairs(
            correspondences,
            settings,
        )

        candidates: list[_TypedCandidate] = []
        for pair in region_pairs:
            correlation_group = _correlation_group(pair)
            candidates.extend(
                (
                    _candidate(pair.first, width, height, correlation_group),
                    _candidate(pair.second, width, height, correlation_group),
                )
            )

        analysis_capped = keypoint_count >= settings.max_keypoints or cluster_metrics.capped
        return _completed_real_result(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            group=self.group,
            request=request,
            summary=(
                "Geometrically consistent, spatially separated repeated image-region "
                "correspondences were measured with bounded ORB and RANSAC processing."
            ),
            raw_metrics={
                "width": width,
                "height": height,
                "keypoint_count": keypoint_count,
                "descriptor_count": descriptor_count,
                "spatially_separated_match_count": len(correspondences),
                "geometric_cluster_count": cluster_metrics.geometric_cluster_count,
                "accepted_cluster_count": len(region_pairs),
                "max_cluster_inlier_count": cluster_metrics.max_cluster_inlier_count,
                "max_cluster_inlier_ratio": cluster_metrics.max_cluster_inlier_ratio,
                "analysis_capped": analysis_capped,
            },
            candidates=tuple(candidates),
        )


def _normalized_artifact(request: AnalyzerRequest) -> AnalyzerArtifactInput | None:
    artifacts = _artifacts(request, "normalized_image")
    if len(artifacts) != 1 or artifacts[0].format.casefold() != "png":
        return None
    return artifacts[0]


def _normalized_header(
    artifact: AnalyzerArtifactInput,
) -> tuple[int, int, str] | None:
    try:
        with (
            artifact.content.open_for_read() as stream,
            Image.open(stream, formats=["PNG"]) as image,
        ):
            if image.format != "PNG" or image.mode not in {"RGB", "RGBA"}:
                return None
            return image.width, image.height, image.mode
    except (
        EOFError,
        Image.DecompressionBombError,
        OSError,
        SyntaxError,
        UnidentifiedImageError,
        ValueError,
    ):
        return None


def _decode_normalized(
    artifact: AnalyzerArtifactInput,
    settings: ImageCopyMoveCorrespondenceSettings,
) -> tuple[NDArray[np.uint8], NDArray[np.uint8] | None, int, int]:
    with artifact.content.open_for_read() as stream, Image.open(stream, formats=["PNG"]) as image:
        if image.format != "PNG" or image.mode not in {"RGB", "RGBA"}:
            raise ValueError("normalized image contract is invalid")
        width, height = image.size
        if (
            width < settings.min_dimension_px
            or height < settings.min_dimension_px
            or width * height > settings.max_pixels
        ):
            raise ValueError("normalized image dimensions are outside analyzer bounds")
        image.load()
        pixels = np.array(image, dtype=np.uint8, copy=True)

    if pixels.ndim != 3 or pixels.shape[2] not in {3, 4}:
        raise ValueError("normalized image pixels are invalid")
    if pixels.shape[2] == 3:
        grayscale = cast(NDArray[np.uint8], cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY))
        return grayscale, None, width, height

    alpha = pixels[:, :, 3]
    visible = alpha > 0
    rgb = pixels[:, :, :3].copy()
    rgb[~visible] = 0
    grayscale = cast(NDArray[np.uint8], cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    mask = cast(NDArray[np.uint8], np.where(visible, np.uint8(255), np.uint8(0)))
    return grayscale, mask, width, height


def _ordered_features(
    keypoints: Sequence[cv2.KeyPoint],
    descriptors: object,
) -> _FeatureSet:
    if descriptors is None or not keypoints:
        return _FeatureSet(
            points=np.empty((0, 2), dtype=np.float32),
            descriptors=np.empty((0, 32), dtype=np.uint8),
        )
    if not isinstance(descriptors, np.ndarray) or descriptors.dtype != np.uint8:
        raise ValueError("ORB descriptors are invalid")
    descriptor_array = cast(NDArray[np.uint8], descriptors)
    if len(keypoints) != len(descriptor_array):
        raise ValueError("ORB keypoints and descriptors do not align")
    order = sorted(
        range(len(keypoints)),
        key=lambda index: (
            keypoints[index].pt[0],
            keypoints[index].pt[1],
            keypoints[index].size,
            keypoints[index].angle,
            keypoints[index].response,
            keypoints[index].octave,
            keypoints[index].class_id,
            descriptor_array[index].tobytes(),
        ),
    )
    return _FeatureSet(
        points=np.asarray([keypoints[index].pt for index in order], dtype=np.float32),
        descriptors=np.ascontiguousarray(descriptor_array[order], dtype=np.uint8),
    )


def _self_correspondences(
    features: _FeatureSet,
    *,
    descriptor_ratio: float,
    min_spatial_separation: float,
) -> tuple[_Correspondence, ...]:
    if len(features.descriptors) < 3:
        return ()
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    neighbors = matcher.knnMatch(features.descriptors, features.descriptors, k=3)
    selected: dict[tuple[int, int], _Correspondence] = {}
    for query_index, matches in enumerate(neighbors):
        non_self = sorted(
            (match for match in matches if match.trainIdx != query_index),
            key=lambda match: (match.distance, match.trainIdx),
        )
        if len(non_self) < 2:
            continue
        nearest, comparison = non_self[:2]
        if nearest.distance >= descriptor_ratio * comparison.distance:
            continue
        first_index, second_index = sorted((query_index, nearest.trainIdx))
        first_point = (
            float(features.points[first_index, 0]),
            float(features.points[first_index, 1]),
        )
        second_point = (
            float(features.points[second_index, 0]),
            float(features.points[second_index, 1]),
        )
        if math.dist(first_point, second_point) < min_spatial_separation:
            continue
        correspondence = _Correspondence(
            first=first_point,
            second=second_point,
            distance=float(nearest.distance),
        )
        key = (first_index, second_index)
        existing = selected.get(key)
        if existing is None or correspondence.distance < existing.distance:
            selected[key] = correspondence
    return tuple(
        sorted(
            selected.values(),
            key=lambda item: (item.first, item.second, item.distance),
        )
    )


def _geometric_region_pairs(
    correspondences: tuple[_Correspondence, ...],
    settings: ImageCopyMoveCorrespondenceSettings,
) -> tuple[tuple[_RegionPair, ...], _ClusterMetrics]:
    remaining = list(correspondences)
    accepted: list[_RegionPair] = []
    geometric_count = 0
    max_inlier_count = 0
    max_inlier_ratio = 0.0
    attempts = 0

    while (
        len(remaining) >= max(_MIN_AFFINE_MATCHES, settings.min_cluster_inliers)
        and attempts < settings.max_clusters
    ):
        attempts += 1
        source = np.asarray([item.first for item in remaining], dtype=np.float32)
        target = np.asarray([item.second for item in remaining], dtype=np.float32)
        cv2.setRNGSeed(0)
        model, inlier_mask = cv2.estimateAffinePartial2D(
            source,
            target,
            method=cv2.RANSAC,
            ransacReprojThreshold=settings.ransac_reprojection_threshold_px,
            maxIters=_RANSAC_MAX_ITERS,
            confidence=_RANSAC_CONFIDENCE,
            refineIters=_RANSAC_REFINE_ITERS,
        )
        model_value: object = model
        mask_value: object = inlier_mask
        if model_value is None or mask_value is None:
            break
        inlier_mask = cast(NDArray[np.uint8], mask_value)
        inliers = np.flatnonzero(inlier_mask.reshape(-1) != 0)
        if len(inliers) < _MIN_AFFINE_MATCHES:
            break

        geometric_count += 1
        inlier_count = int(len(inliers))
        inlier_ratio = inlier_count / len(remaining)
        max_inlier_count = max(max_inlier_count, inlier_count)
        max_inlier_ratio = max(max_inlier_ratio, inlier_ratio)
        inlier_items = tuple(remaining[int(index)] for index in inliers)
        remaining = [item for index, item in enumerate(remaining) if inlier_mask[index, 0] == 0]

        if (
            inlier_count < settings.min_cluster_inliers
            or inlier_ratio < settings.min_cluster_inlier_ratio
        ):
            continue
        pair = _region_pair(inlier_items)
        if pair is not None and not any(_duplicate_pair(pair, prior) for prior in accepted):
            accepted.append(pair)

    accepted.sort(key=lambda pair: (_box_key(pair.first), _box_key(pair.second)))
    capped = attempts >= settings.max_clusters and len(remaining) >= max(
        _MIN_AFFINE_MATCHES, settings.min_cluster_inliers
    )
    return tuple(accepted), _ClusterMetrics(
        geometric_cluster_count=geometric_count,
        max_cluster_inlier_count=max_inlier_count,
        max_cluster_inlier_ratio=max_inlier_ratio,
        capped=capped,
    )


def _region_pair(
    correspondences: tuple[_Correspondence, ...],
) -> _RegionPair | None:
    first = _bounding_box(tuple(item.first for item in correspondences))
    second = _bounding_box(tuple(item.second for item in correspondences))
    if first is None or second is None:
        return None
    ordered = sorted((first, second), key=_box_key)
    return _RegionPair(first=ordered[0], second=ordered[1])


def _bounding_box(points: tuple[tuple[float, float], ...]) -> _PixelBox | None:
    minimum_x = min(point[0] for point in points)
    maximum_x = max(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_y = max(point[1] for point in points)
    width = maximum_x - minimum_x
    height = maximum_y - minimum_y
    if width <= 0 or height <= 0:
        return None
    return _PixelBox(minimum_x, minimum_y, width, height)


def _duplicate_pair(candidate: _RegionPair, existing: _RegionPair) -> bool:
    return (
        _intersection_over_union(candidate.first, existing.first) >= _DUPLICATE_REGION_IOU
        and _intersection_over_union(candidate.second, existing.second) >= _DUPLICATE_REGION_IOU
    )


def _intersection_over_union(first: _PixelBox, second: _PixelBox) -> float:
    intersection_width = max(
        0.0,
        min(first.x + first.width, second.x + second.width) - max(first.x, second.x),
    )
    intersection_height = max(
        0.0,
        min(first.y + first.height, second.y + second.height) - max(first.y, second.y),
    )
    intersection = intersection_width * intersection_height
    union = first.area + second.area - intersection
    return intersection / union if union > 0 else 0.0


def _box_key(box: _PixelBox) -> tuple[float, float, float, float]:
    return box.x, box.y, box.width, box.height


def _correlation_group(pair: _RegionPair) -> str:
    payload = json.dumps(
        {"first": _box_key(pair.first), "second": _box_key(pair.second)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "image_region_correspondence_" + hashlib.sha256(payload).hexdigest()


def _candidate(
    box: _PixelBox,
    image_width: int,
    image_height: int,
    correlation_group: str,
) -> _RepeatedImageRegionCorrespondenceCandidate:
    x = min(1.0, max(0.0, box.x / image_width))
    y = min(1.0, max(0.0, box.y / image_height))
    width = min(1.0 - x, max(0.0, box.width / image_width))
    height = min(1.0 - y, max(0.0, box.height / image_height))
    if width <= 0 or height <= 0:
        raise ValueError("correspondence region is degenerate")
    return _RepeatedImageRegionCorrespondenceCandidate(
        type="repeated_image_region_correspondence",
        localization=BoundingBoxLocalization(
            type="bounding_box",
            x=x,
            y=y,
            width=width,
            height=height,
            coordinate_space="normalized",
        ),
        correlation_group=correlation_group,
        evidence_refs=(),
    )
