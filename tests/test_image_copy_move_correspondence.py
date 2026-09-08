"""Deterministic Stage 6 image-region correspondence analyzer tests."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import cast

import cv2
import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from fakedetector.analyzers._catalog import (
    _real_analyzer_registrations,
    _resolve_worker_definition,
)
from fakedetector.analyzers._image_copy_move import (
    ImageCopyMoveCorrespondenceAnalyzer,
    ImageCopyMoveCorrespondenceSettings,
    _Correspondence,
    _duplicate_pair,
    _FeatureSet,
    _geometric_region_pairs,
    _PixelBox,
    _RegionPair,
    _self_correspondences,
)
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._transport import (
    _MAX_STAGE5_ANALYZER_RESULT_BYTES,
    _serialize_stage5_analyzer_result,
    _WorkerArtifact,
    _WorkerRequest,
)
from fakedetector.analyzers._worker import _SpawnedWorkerRunner, _WorkerRunKind
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, ImageTechnicalParameters, MediaType
from fakedetector.lifecycle._stage6 import Stage6FindingFormationError, Stage6FindingService

_IMAGE_SIZE = 512
_FIRST_REGION = (48, 64, 112, 112)
_SECOND_REGION = (320, 300, 112, 112)


def _save_array(path: Path, pixels: np.ndarray) -> None:
    with Image.fromarray(pixels) as image:
        image.save(path, format="PNG")


def _positive_pixels(*, rgba: bool = False) -> np.ndarray:
    rng = np.random.default_rng(217)
    channels = 4 if rgba else 3
    canvas = np.full((_IMAGE_SIZE, _IMAGE_SIZE, channels), 24, dtype=np.uint8)
    patch = rng.integers(0, 256, size=(112, 112, 3), dtype=np.uint8)
    first_x, first_y, width, height = _FIRST_REGION
    second_x, second_y, _, _ = _SECOND_REGION
    canvas[first_y : first_y + height, first_x : first_x + width, :3] = patch
    canvas[second_y : second_y + height, second_x : second_x + width, :3] = patch
    if rgba:
        canvas[:, :, 3] = 255
    return canvas


def _repeating_ui_pixels() -> np.ndarray:
    canvas = np.full((_IMAGE_SIZE, _IMAGE_SIZE, 3), 238, dtype=np.uint8)
    card = np.full((280, 176, 3), 250, dtype=np.uint8)
    cv2.rectangle(card, (0, 0), (175, 279), (52, 63, 78), 4)
    cv2.circle(card, (88, 68), 34, (45, 112, 196), -1)
    cv2.circle(card, (88, 68), 17, (245, 248, 252), 3)
    cv2.line(card, (34, 132), (142, 132), (68, 76, 91), 5)
    cv2.line(card, (34, 158), (128, 158), (102, 112, 128), 4)
    cv2.line(card, (34, 184), (136, 184), (102, 112, 128), 4)
    for index, x in enumerate((56, 280)):
        canvas[112:392, x : x + 176] = card
        cv2.putText(
            canvas,
            f"CARD {index + 1}",
            (x + 32, 426),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (52, 63, 78),
            2,
            cv2.LINE_AA,
        )
    return canvas


def _high_tie_repeating_pixels() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    tile = rng.integers(0, 256, size=(32, 32), dtype=np.uint8)
    grayscale = np.tile(tile, (32, 32))
    return np.repeat(grayscale[:, :, np.newaxis], 3, axis=2), grayscale


def _request(
    source: Path,
    normalized: Path,
    *,
    settings: ImageCopyMoveCorrespondenceSettings | None = None,
    source_dimensions: tuple[int, int] | None = None,
    artifact_format: str = "png",
) -> AnalyzerRequest:
    with Image.open(normalized) as image:
        width, height = image.size
        mode = image.mode
    source_width, source_height = source_dimensions or (width, height)
    return AnalyzerRequest(
        analysis_id="a" * 32,
        media_type=MediaType.IMAGE,
        file_facts=_AnalyzerFileFacts(
            extension="png",
            declared_mime_type="image/png",
            detected_mime_type="image/png",
            media_type=MediaType.IMAGE,
            size_bytes=source.stat().st_size,
            sha256="0" * 64,
            signature_match=True,
            safe_read=True,
            technical_parameters=ImageTechnicalParameters(
                width=source_width,
                height=source_height,
                format="PNG",
                color_mode=mode,
                frame_count=1,
                has_metadata=False,
            ),
        ),
        source=_ReadOnlyAnalyzerInput(source),
        settings=settings or ImageCopyMoveCorrespondenceSettings(),
        timeout_seconds=10.0,
        artifacts=(
            AnalyzerArtifactInput(
                artifact_id="image_normalized",
                artifact_type="normalized_image",
                content=_ReadOnlyAnalyzerInput(normalized),
                format=artifact_format,
            ),
        ),
        metadata={
            "normalized": {
                "format": "png",
                "mode": mode,
                "width": width,
                "height": height,
                "scope": "first_frame",
            }
        },
    )


def _analyze(path: Path, **kwargs: object) -> AnalyzerResult:
    request = _request(path, path, **kwargs)
    analyzer = ImageCopyMoveCorrespondenceAnalyzer()
    assert analyzer.check_applicability(request).applicable
    return analyzer.analyze(request)


def _copy_move_candidate(
    correlation_suffix: str,
    *,
    x: float,
    y: float,
) -> dict[str, object]:
    return {
        "type": "repeated_image_region_correspondence",
        "localization": {
            "type": "bounding_box",
            "x": x,
            "y": y,
            "width": 0.2,
            "height": 0.2,
            "coordinate_space": "normalized",
        },
        "correlation_group": "image_region_correspondence_" + correlation_suffix * 64,
        "evidence_refs": [],
    }


def _copy_move_result(candidates: list[dict[str, object]]) -> AnalyzerResult:
    return AnalyzerResult.model_validate(
        {
            "analyzer_id": "image_copy_move_correspondence",
            "analyzer_version": "1.0.0",
            "media_type": "image",
            "group": "content",
            "status": "completed",
            "applicable": True,
            "started_at": None,
            "finished_at": None,
            "duration_ms": 0,
            "score": None,
            "score_name": None,
            "summary": "Repeated interface regions measured.",
            "raw_metrics": {},
            "candidate_findings": candidates,
            "warnings": [],
            "errors": [],
        }
    )


def test_dependency_pins_and_orb_runtime_are_exact() -> None:
    assert importlib.metadata.version("opencv-python-headless") == "4.14.0.94"
    assert importlib.metadata.version("numpy") == "2.5.2"
    assert cv2.__version__ == "4.14.0"
    assert np.__version__ == "2.5.2"
    assert cv2.ORB_create(nfeatures=8) is not None


def test_copy_move_settings_are_frozen_bounded_and_reject_unknown_fields() -> None:
    settings = ImageCopyMoveCorrespondenceSettings()
    assert settings.model_dump() == {
        "min_dimension_px": 128,
        "max_pixels": 12_000_000,
        "max_keypoints": 5_000,
        "descriptor_ratio": 0.75,
        "min_spatial_separation_px": 32.0,
        "ransac_reprojection_threshold_px": 3.0,
        "min_cluster_inliers": 12,
        "min_cluster_inlier_ratio": 0.5,
        "max_clusters": 4,
    }
    with pytest.raises(ValidationError):
        settings.max_keypoints = 64
    with pytest.raises(ValidationError):
        ImageCopyMoveCorrespondenceSettings.model_validate({"unknown": True})
    for invalid in (
        {"max_pixels": 12_000_001},
        {"max_keypoints": 5_001},
        {"descriptor_ratio": 1.0},
        {"min_cluster_inlier_ratio": 0.0},
        {"max_clusters": 5},
    ):
        with pytest.raises(ValidationError):
            ImageCopyMoveCorrespondenceSettings.model_validate(invalid)


def test_copy_move_registration_is_trusted_and_requires_normalized_image() -> None:
    registrations = _real_analyzer_registrations()
    registration = next(
        item for item in registrations if item.analyzer_id == "image_copy_move_correspondence"
    )
    assert registration.analyzer_version == "1.0.0"
    assert registration.group == "content"
    assert registration.supported_media_types == frozenset({MediaType.IMAGE})
    assert registration.worker_key == "stage6.image_copy_move_correspondence.v1"
    assert _resolve_worker_definition(registration.worker_key) is not None


@pytest.mark.parametrize(
    ("dimensions", "reason"),
    [((127, 512), "image_dimensions"), ((4_000, 4_000), "image_pixels")],
)
def test_copy_move_not_applicable_dimension_bounds_without_large_allocation(
    tmp_path: Path,
    dimensions: tuple[int, int],
    reason: str,
) -> None:
    path = tmp_path / "tiny.png"
    _save_array(path, np.zeros((128, 128, 3), dtype=np.uint8))
    decision = ImageCopyMoveCorrespondenceAnalyzer().check_applicability(
        _request(path, path, source_dimensions=dimensions)
    )
    assert not decision.applicable
    assert decision.reason_code == reason


def test_copy_move_not_applicable_for_missing_or_invalid_normalized_representation(
    tmp_path: Path,
) -> None:
    rgb = tmp_path / "rgb.png"
    grayscale = tmp_path / "grayscale.png"
    _save_array(rgb, np.zeros((128, 128, 3), dtype=np.uint8))
    _save_array(grayscale, np.zeros((128, 128), dtype=np.uint8))
    analyzer = ImageCopyMoveCorrespondenceAnalyzer()

    missing = _request(rgb, rgb)
    missing = AnalyzerRequest(
        analysis_id=missing.analysis_id,
        media_type=missing.media_type,
        file_facts=missing.file_facts,
        source=missing.source,
        settings=missing.settings,
        timeout_seconds=missing.timeout_seconds,
    )
    assert analyzer.check_applicability(missing).reason_code == "normalized_image_missing"
    assert (
        analyzer.check_applicability(_request(rgb, rgb, artifact_format="jpeg")).reason_code
        == "normalized_image_missing"
    )
    assert (
        analyzer.check_applicability(_request(rgb, grayscale)).reason_code
        == "normalized_image_contract"
    )


def test_uniform_and_unique_images_complete_without_candidates(tmp_path: Path) -> None:
    uniform = tmp_path / "uniform.png"
    unique = tmp_path / "unique.png"
    _save_array(uniform, np.full((256, 256, 3), 90, dtype=np.uint8))
    rng = np.random.default_rng(991)
    _save_array(unique, rng.integers(0, 256, size=(320, 320, 3), dtype=np.uint8))

    uniform_result = _analyze(uniform)
    unique_result = _analyze(unique)

    assert uniform_result.status is AnalyzerStatus.COMPLETED
    assert uniform_result.raw_metrics["keypoint_count"] == 0
    assert uniform_result.candidate_findings == []
    assert unique_result.status is AnalyzerStatus.COMPLETED
    assert unique_result.raw_metrics["accepted_cluster_count"] == 0
    assert unique_result.candidate_findings == []


def test_self_matching_excludes_identity_and_nearby_descriptor_pairs() -> None:
    descriptors = np.asarray(
        [
            [0] * 32,
            [1] + [0] * 31,
            [255] * 32,
        ],
        dtype=np.uint8,
    )
    nearby = _FeatureSet(
        points=np.asarray([(0, 0), (10, 0), (100, 100)], dtype=np.float32),
        descriptors=descriptors,
    )
    separated = _FeatureSet(
        points=np.asarray([(0, 0), (64, 0), (100, 100)], dtype=np.float32),
        descriptors=descriptors,
    )

    assert (
        _self_correspondences(
            nearby,
            descriptor_ratio=0.75,
            min_spatial_separation=32,
        )
        == ()
    )
    matches = _self_correspondences(
        separated,
        descriptor_ratio=0.75,
        min_spatial_separation=32,
    )
    assert len(matches) == 1
    assert matches[0].first != matches[0].second


def test_close_duplicate_region_pairs_are_suppressed_by_both_regions() -> None:
    original = _RegionPair(
        first=_PixelBox(10, 20, 40, 30),
        second=_PixelBox(110, 120, 40, 30),
    )
    close_duplicate = _RegionPair(
        first=_PixelBox(12, 22, 40, 30),
        second=_PixelBox(112, 122, 40, 30),
    )
    different_second_region = _RegionPair(
        first=_PixelBox(12, 22, 40, 30),
        second=_PixelBox(300, 300, 40, 30),
    )

    assert _duplicate_pair(close_duplicate, original)
    assert not _duplicate_pair(different_second_region, original)


def test_duplicate_region_pair_suppression_is_invariant_to_pair_orientation() -> None:
    existing = _RegionPair(
        first=_PixelBox(10, 20, 40, 30),
        second=_PixelBox(11, 120, 40, 30),
    )
    cross_order_duplicate = _RegionPair(
        first=_PixelBox(9, 122, 40, 30),
        second=_PixelBox(12, 22, 40, 30),
    )

    assert _duplicate_pair(cross_order_duplicate, existing)
    assert _duplicate_pair(existing, cross_order_duplicate)


def test_geometric_clustering_suppresses_one_cross_order_unordered_pair() -> None:
    offsets = tuple((x, y) for y in (0.0, 15.0, 30.0) for x in (0.0, 13.0, 27.0, 40.0))
    existing = tuple(
        _Correspondence(
            first=(10.0 + x, 20.0 + y),
            second=(11.0 + x, 120.0 + y),
            distance=1.0,
        )
        for x, y in offsets
    )
    cross_order_duplicate = tuple(
        _Correspondence(
            first=(9.0 + x, 122.0 + y),
            second=(12.0 + x, 22.0 + y),
            distance=1.0,
        )
        for x, y in offsets
    )
    settings = ImageCopyMoveCorrespondenceSettings()

    first_run = _geometric_region_pairs(existing + cross_order_duplicate, settings)
    second_run = _geometric_region_pairs(existing + cross_order_duplicate, settings)

    assert first_run == second_run
    assert first_run[1].geometric_cluster_count == 2
    assert len(first_run[0]) == 1


def test_geometric_clustering_preserves_legitimate_separate_region_pairs() -> None:
    offsets = tuple((x, y) for y in (0.0, 15.0, 30.0) for x in (0.0, 13.0, 27.0, 40.0))
    first_pair = tuple(
        _Correspondence(
            first=(10.0 + x, 20.0 + y),
            second=(11.0 + x, 120.0 + y),
            distance=1.0,
        )
        for x, y in offsets
    )
    separate_pair = tuple(
        _Correspondence(
            first=(200.0 + x, 20.0 + y),
            second=(300.0 + x, 120.0 + y),
            distance=1.0,
        )
        for x, y in offsets
    )

    pairs, metrics = _geometric_region_pairs(
        first_pair + separate_pair,
        ImageCopyMoveCorrespondenceSettings(),
    )

    assert metrics.geometric_cluster_count == 2
    assert len(pairs) == 2


def test_fully_transparent_rgb_values_do_not_create_features(tmp_path: Path) -> None:
    path = tmp_path / "transparent.png"
    rng = np.random.default_rng(723)
    pixels = rng.integers(0, 256, size=(256, 256, 4), dtype=np.uint8)
    pixels[:, :, 3] = 0
    _save_array(path, pixels)

    result = _analyze(path)

    assert result.raw_metrics["keypoint_count"] == 0
    assert result.raw_metrics["descriptor_count"] == 0
    assert result.candidate_findings == []


def test_synthetic_copy_produces_exactly_paired_bounding_boxes(tmp_path: Path) -> None:
    path = tmp_path / "copied.png"
    _save_array(path, _positive_pixels())

    result = _analyze(path)

    assert cast(int, result.raw_metrics["accepted_cluster_count"]) >= 1
    assert len(result.candidate_findings) == 2 * cast(
        int, result.raw_metrics["accepted_cluster_count"]
    )
    first_pair = result.candidate_findings[:2]
    assert first_pair[0]["correlation_group"] == first_pair[1]["correlation_group"]
    assert all(item["type"] == "repeated_image_region_correspondence" for item in first_pair)
    expected = (_FIRST_REGION, _SECOND_REGION)
    for candidate, (x, y, width, height) in zip(first_pair, expected, strict=True):
        localization = cast(dict[str, object], candidate["localization"])
        assert localization["type"] == "bounding_box"
        assert localization["coordinate_space"] == "normalized"
        assert float(localization["x"]) == pytest.approx(x / _IMAGE_SIZE, abs=0.08)
        assert float(localization["y"]) == pytest.approx(y / _IMAGE_SIZE, abs=0.08)
        assert 0 < float(localization["width"]) <= width / _IMAGE_SIZE + 0.02
        assert 0 < float(localization["height"]) <= height / _IMAGE_SIZE + 0.02
    assert cast(int, result.raw_metrics["geometric_cluster_count"]) <= 4
    assert len(result.candidate_findings) <= 8


def test_copy_move_output_is_bounded_and_contains_no_feature_payload(tmp_path: Path) -> None:
    path = tmp_path / "bounded.png"
    rng = np.random.default_rng(19)
    _save_array(path, rng.integers(0, 256, size=(512, 512, 3), dtype=np.uint8))
    settings = ImageCopyMoveCorrespondenceSettings(max_keypoints=64, max_clusters=1)

    result = _analyze(path, settings=settings)
    serialized = _serialize_stage5_analyzer_result(result)

    assert result.raw_metrics["keypoint_count"] == 64
    assert result.raw_metrics["descriptor_count"] == 64
    assert result.raw_metrics["analysis_capped"] is True
    assert cast(int, result.raw_metrics["geometric_cluster_count"]) <= 1
    assert len(result.candidate_findings) <= 2
    assert len(serialized) <= _MAX_STAGE5_ANALYZER_RESULT_BYTES
    payload = result.model_dump(mode="json", warnings="error")
    forbidden = {"descriptors", "keypoints", "matches", "pixels"}
    assert forbidden.isdisjoint(cast(dict[str, object], payload["raw_metrics"]))


def test_orb_tied_response_overflow_is_capped_before_matching_and_repeatable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "high-tie-repeating.png"
    pixels, grayscale = _high_tie_repeating_pixels()
    _save_array(path, pixels)
    settings = ImageCopyMoveCorrespondenceSettings()
    raw_keypoints, raw_descriptors = cv2.ORB_create(
        nfeatures=settings.max_keypoints
    ).detectAndCompute(grayscale, None)
    assert len(raw_keypoints) > settings.max_keypoints
    assert raw_descriptors is not None
    assert len(raw_descriptors) > settings.max_keypoints

    descriptor_counts: list[tuple[int, int]] = []
    original_matcher = cv2.BFMatcher

    class RecordingMatcher:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._delegate = original_matcher(*args, **kwargs)

        def __getattr__(self, name: str) -> object:
            if name == "knnMatch":
                return self._knn_match
            return getattr(self._delegate, name)

        def _knn_match(
            self,
            query_descriptors: np.ndarray,
            train_descriptors: np.ndarray,
            *,
            k: int,
        ) -> object:
            descriptor_counts.append((len(query_descriptors), len(train_descriptors)))
            return self._delegate.knnMatch(query_descriptors, train_descriptors, k=k)

    monkeypatch.setattr(cv2, "BFMatcher", RecordingMatcher)

    results = [_analyze(path, settings=settings) for _ in range(2)]

    assert results[1] == results[0]
    assert all(result.status is AnalyzerStatus.COMPLETED for result in results)
    assert all(
        cast(int, result.raw_metrics["keypoint_count"]) <= settings.max_keypoints
        for result in results
    )
    assert all(
        cast(int, result.raw_metrics["descriptor_count"]) <= settings.max_keypoints
        for result in results
    )
    assert all(result.raw_metrics["analysis_capped"] is True for result in results)
    assert descriptor_counts == [(settings.max_keypoints, settings.max_keypoints)] * 2
    assert all(len(result.candidate_findings) <= 8 for result in results)
    assert all(
        len(_serialize_stage5_analyzer_result(result)) <= _MAX_STAGE5_ANALYZER_RESULT_BYTES
        for result in results
    )


def test_positive_output_and_finding_identity_are_repeatable(tmp_path: Path) -> None:
    path = tmp_path / "repeatable.png"
    _save_array(path, _positive_pixels(rgba=True))
    analyzer = ImageCopyMoveCorrespondenceAnalyzer()
    request = _request(path, path)
    service = Stage6FindingService()

    results = [analyzer.analyze(request) for _ in range(3)]
    findings = [service.form_findings((result,)) for result in results]

    assert [result.raw_metrics for result in results[1:]] == [results[0].raw_metrics] * 2
    assert [result.candidate_findings for result in results[1:]] == [
        results[0].candidate_findings
    ] * 2
    assert findings[1:] == [findings[0], findings[0]]
    assert findings[0]
    assert all(
        sum(other.correlation_group == finding.correlation_group for other in findings[0]) == 2
        for finding in findings[0]
    )
    assert all(finding.severity.value == "weak" for finding in findings[0])
    assert all(finding.source_score is None for finding in findings[0])
    assert all(finding.score_impact is None for finding in findings[0])
    assert all(not finding.critical_override_eligible for finding in findings[0])


def test_converter_accepts_one_valid_copy_move_pair() -> None:
    result = _copy_move_result(
        [
            _copy_move_candidate("a", x=0.1, y=0.1),
            _copy_move_candidate("a", x=0.6, y=0.6),
        ]
    )

    findings = Stage6FindingService().form_findings((result,))

    assert len(findings) == 2
    assert {finding.correlation_group for finding in findings} == {
        "image_region_correspondence_" + "a" * 64
    }


@pytest.mark.parametrize(
    "candidates",
    [
        [_copy_move_candidate("a", x=0.1, y=0.1)],
        [
            _copy_move_candidate("a", x=0.1, y=0.1),
            _copy_move_candidate("a", x=0.4, y=0.4),
            _copy_move_candidate("a", x=0.7, y=0.7),
        ],
        [
            _copy_move_candidate("a", x=0.1, y=0.1),
            _copy_move_candidate("a", x=0.1, y=0.1),
        ],
    ],
    ids=["one_candidate", "three_candidates", "identical_bounding_boxes"],
)
def test_converter_rejects_malformed_copy_move_pair_structure(
    candidates: list[dict[str, object]],
) -> None:
    with pytest.raises(Stage6FindingFormationError) as captured:
        Stage6FindingService().form_findings((_copy_move_result(candidates),))

    assert captured.value.reason_code == "candidate_validation"


def test_converter_accepts_two_independent_copy_move_pairs() -> None:
    result = _copy_move_result(
        [
            _copy_move_candidate("b", x=0.65, y=0.1),
            _copy_move_candidate("a", x=0.1, y=0.1),
            _copy_move_candidate("b", x=0.65, y=0.65),
            _copy_move_candidate("a", x=0.1, y=0.65),
        ]
    )

    findings = Stage6FindingService().form_findings((result,))

    assert len(findings) == 4
    assert {
        group: sum(finding.correlation_group == group for finding in findings)
        for group in {finding.correlation_group for finding in findings}
    } == {
        "image_region_correspondence_" + "a" * 64: 2,
        "image_region_correspondence_" + "b" * 64: 2,
    }


def test_copy_move_pair_validation_preserves_existing_finding_ids() -> None:
    result = _copy_move_result(
        [
            _copy_move_candidate("a", x=0.1, y=0.1),
            _copy_move_candidate("a", x=0.6, y=0.6),
        ]
    )

    findings = Stage6FindingService().form_findings((result,))

    assert [finding.finding_id for finding in findings] == [
        "finding_694f1a6c1e5e9046f143e45c8c9ab51fcaa8bf30386f98d549c5925a8197d443",
        "finding_7068caedc50ba2c437e439caf08fdf6ba32614d924f9c2ffe69fc30dcc623d10",
    ]


def test_converter_rejects_more_than_eight_copy_move_candidates(tmp_path: Path) -> None:
    path = tmp_path / "candidate-bound.png"
    _save_array(path, _positive_pixels())
    result = _analyze(path)
    assert len(result.candidate_findings) >= 2
    oversized = result.model_copy(
        update={"candidate_findings": result.candidate_findings[:2] * 5},
        deep=True,
    )

    with pytest.raises(Stage6FindingFormationError) as captured:
        Stage6FindingService().form_findings((oversized,))

    assert captured.value.reason_code == "candidate_validation"


@pytest.mark.parametrize(
    "localization_update",
    [
        {"width": 0.0},
        {"x": 0.9, "width": 0.2},
        {"height": 0.0},
        {"y": 0.9, "height": 0.2},
    ],
)
def test_converter_rejects_degenerate_or_out_of_bounds_copy_move_regions(
    tmp_path: Path,
    localization_update: dict[str, float],
) -> None:
    path = tmp_path / "invalid-bbox.png"
    _save_array(path, _positive_pixels())
    result = _analyze(path)
    candidate = cast(dict[str, object], result.candidate_findings[0])
    localization = cast(dict[str, object], candidate["localization"])
    invalid_candidate = {
        **candidate,
        "localization": {**localization, **localization_update},
    }
    invalid_result = result.model_copy(
        update={"candidate_findings": [invalid_candidate]},
        deep=True,
    )

    with pytest.raises(Stage6FindingFormationError) as captured:
        Stage6FindingService().form_findings((invalid_result,))

    assert captured.value.reason_code == "candidate_validation"


def test_repeating_interface_elements_remain_weak_observations(tmp_path: Path) -> None:
    path = tmp_path / "legitimate-interface-elements.png"
    _save_array(path, _repeating_ui_pixels())

    results = [_analyze(path), _analyze(path)]
    findings = [Stage6FindingService().form_findings((result,)) for result in results]

    assert all(result.status is AnalyzerStatus.COMPLETED for result in results)
    assert results[1] == results[0]
    assert findings[1] == findings[0]
    assert findings[0]
    assert all(finding.severity.value == "weak" for finding in findings[0])
    reported_text = " ".join(
        [results[0].summary, *(finding.description for finding in findings[0])]
    ).casefold()
    assert all(word not in reported_text for word in ("forgery", "manipulation", "deepfake"))


def test_copy_move_runs_through_real_spawned_worker(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    normalized = tmp_path / "normalized.png"
    _save_array(source, np.full((_IMAGE_SIZE, _IMAGE_SIZE, 3), 24, dtype=np.uint8))
    _save_array(normalized, _positive_pixels())
    analyzer_request = _request(source, normalized)
    request = _WorkerRequest(
        worker_key="stage6.image_copy_move_correspondence.v1",
        analysis_id=analyzer_request.analysis_id,
        media_type="image",
        file_facts_json=analyzer_request.file_facts.model_dump_json(),
        source_path=str(source),
        artifacts=(
            _WorkerArtifact(
                artifact_id="image_normalized",
                artifact_type="normalized_image",
                local_path=str(normalized),
                format="png",
            ),
        ),
        metadata_json="{}",
        warnings=(),
        settings_json=ImageCopyMoveCorrespondenceSettings().model_dump_json(),
        timeout_seconds=10.0,
    )

    run = _SpawnedWorkerRunner().run(request, 10.0)

    assert run.kind is _WorkerRunKind.RESPONSE
    assert run.response is not None
    envelope = json.loads(run.response)
    assert envelope["kind"] == "result"
    assert envelope["result"]["analyzer_id"] == "image_copy_move_correspondence"
    assert envelope["result"]["raw_metrics"]["accepted_cluster_count"] >= 1
    assert len(envelope["result"]["candidate_findings"]) >= 2
