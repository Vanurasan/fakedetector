"""P1 arithmetic and bounded runtime adaptations; synthetic evidence only."""

import json
from dataclasses import replace

import numpy as np
import pytest
from support.diploma_inputs import audio_request, video_request, worker_request

from fakedetector.analyzers._video_experimental import (
    VideoRepeatedContentCorrespondenceAnalyzer,
    VideoTimingAnomalyAnalyzer,
    VideoVisualDiscontinuityAnalyzer,
    _block_descriptor,
    _distances,
)
from fakedetector.analyzers._worker import _execute_worker, _SpawnedWorkerRunner
from fakedetector.domain import AnalyzerResult, AnalyzerStatus

ANALYZERS = [
    VideoRepeatedContentCorrespondenceAnalyzer(),
    VideoVisualDiscontinuityAnalyzer(),
    VideoTimingAnomalyAnalyzer(),
]


def _frames(count=20):
    return np.broadcast_to(
        np.arange(count, dtype="u1")[:, None, None, None] * 10, (count, 9, 16, 3)
    ).copy()


def test_block_half_up_rounding_and_remainder_pixels():
    frame = np.zeros((9, 32, 3), dtype="u1")
    frame[:, 1::2] = 1
    assert np.all(_block_descriptor(frame) == 1)
    frame = np.full((19, 33, 3), 255, dtype="u1")
    frame[-1, -1] = 0
    actual = _block_descriptor(frame).reshape(9, 16, 3)
    assert np.all(actual[-1, -1] == 227)  # nine pixels, eight at 255, integer half-up
    assert actual[0, 0, 0] == 255


def test_distance_integer_oracles_and_full_range():
    a = np.zeros((4, 432), dtype=np.int64)
    b = np.full_like(a, 255)
    assert _distances(a, b) == (440640, 0, 0, 0)
    a[1::2] = 255
    b = 255 - a
    assert _distances(a, b) == (440640, 660960, 330480, 330480)


def test_vrc_dynamic_copy_and_distinct_control(tmp_path):
    frames = _frames()
    control = ANALYZERS[0].analyze(video_request(tmp_path, [frames]))
    assert control.raw_metrics["zero_descriptor_pairs"] == 0
    assert control.raw_metrics["minimum_color_pair"]["color_numerator"] > 0
    frames[12:16] = frames[2:6]
    positive = ANALYZERS[0].analyze(video_request(tmp_path, [frames]))
    assert positive.raw_metrics["dynamic_zero_descriptor_pairs"] >= 1
    assert positive.raw_metrics["minimum_color_pair"]["color_numerator"] == 0
    assert positive.raw_metrics["minimum_color_pair"]["delta_numerator"] == 0
    assert positive.candidate_findings == []


def test_vrc_static_zeros_are_not_excluded_or_declared_copy(tmp_path):
    result = ANALYZERS[0].analyze(video_request(tmp_path, [np.zeros((12, 9, 16, 3), dtype="u1")]))
    assert result.raw_metrics["zero_descriptor_pairs"] == result.raw_metrics["eligible_pairs"] == 10
    assert result.raw_metrics["dynamic_zero_descriptor_pairs"] == 0
    assert not result.candidate_findings


@pytest.mark.parametrize("count, pairs", [(3, 0), (4, 0), (8, 0), (9, 1), (32, 300)])
def test_vrc_group_pair_bounds(tmp_path, count, pairs):
    result = ANALYZERS[0].analyze(video_request(tmp_path, [_frames(count)]))
    assert result.raw_metrics["eligible_pairs"] == pairs
    assert result.raw_metrics["state"] == ("measured" if pairs else "insufficient_evidence")


def test_vrc_maximum_plan_all_pairs_and_bounded_response(tmp_path):
    request = video_request(tmp_path, [_frames(32)] * 3)
    result = ANALYZERS[0].analyze(request)
    assert result.raw_metrics["valid_groups"] == 87
    assert result.raw_metrics["eligible_pairs"] == 3423
    assert len(_execute_worker(worker_request(ANALYZERS[0], request))) < 65536


def test_visual_cut_and_static_control(tmp_path):
    pixels = np.zeros((10, 9, 16, 3), dtype="u1")
    control = ANALYZERS[1].analyze(video_request(tmp_path, [pixels]))
    assert control.raw_metrics["windows"][0]["transition"]["max"] == 0
    pixels[5:] = 255
    positive = ANALYZERS[1].analyze(
        video_request(tmp_path, [pixels], ticks=[np.arange(10) * 40 - 1000])
    )
    transition = positive.raw_metrics["windows"][0]["transition"]
    assert transition["max"] == 1
    assert transition["max_ordinals"] == [4, 5]
    assert transition["max_pts_ticks"] == [-840, -800]


def test_timing_cfr_vfr_duplicate_and_decrease(tmp_path):
    frames = _frames(12)
    control = ANALYZERS[2].analyze(video_request(tmp_path, [frames]))
    assert control.raw_metrics["windows"][0]["gap_deviation"]["max"] == 0
    ticks = [0, 40, 80, 80, 60, 200, 260, 280, 340, 360, 420, 440]
    result = ANALYZERS[2].analyze(video_request(tmp_path, [frames], ticks=[ticks]))
    row = result.raw_metrics["windows"][0]
    assert row["duplicate_pts_pairs"] == row["decreasing_pts_pairs"] == 1
    assert row["gap_ticks"] == [40, 40, 0, -20, 140, 60, 20, 60, 20, 60, 20]
    assert row["gap_deviation"]["max"] == 1
    assert result.candidate_findings == []
    nonpositive = ANALYZERS[2].analyze(
        video_request(tmp_path, [frames], ticks=[[100] * 12])
    ).raw_metrics["windows"][0]
    assert nonpositive["positive_gap_median_ticks"] is None
    assert nonpositive["gap_deviation"]["count"] == 0
    assert nonpositive["gap_deviation"]["undefined_count"] == 11
    assert nonpositive["gap_deviation"]["max"] is None


def test_unknown_pts_never_bridged_and_bad_groups_preserved(tmp_path):
    masks = np.full(12, 5)
    masks[3] = 4
    request = video_request(tmp_path, [_frames(12)], masks=[masks])
    timing = ANALYZERS[2].analyze(request).raw_metrics["windows"][0]
    assert timing["missing_pts_frames"] == 1
    assert timing["observed_pairs"] == 9
    assert (
        ANALYZERS[1].analyze(request).raw_metrics["windows"][0]["transition"]["undefined_count"]
        == 2
    )
    assert ANALYZERS[0].analyze(request).raw_metrics["windows"][0]["undefined_group_starts"] == [
        0,
        1,
        2,
        3,
    ]


def test_timing_large_signed_ticks_without_int64_overflow(tmp_path):
    ticks = [(1 << 62) + i * 40 for i in range(12)]
    row = (
        ANALYZERS[2]
        .analyze(video_request(tmp_path, [_frames(12)], ticks=[ticks]))
        .raw_metrics["windows"][0]
    )
    assert row["gap_ticks"] == [40] * 11


@pytest.mark.parametrize("analyzer", ANALYZERS, ids=lambda a: a.analyzer_id)
def test_video_contract_determinism_spawn_and_failure(tmp_path, analyzer):
    request = video_request(tmp_path, [_frames(12)])
    assert analyzer.check_applicability(request).applicable
    result = analyzer.analyze(request)
    assert result == analyzer.analyze(request)
    assert result.score is None and not result.candidate_findings
    run = _SpawnedWorkerRunner().run(worker_request(analyzer, request), 15)
    response = json.loads(run.response)
    assert response["kind"] == "result"
    actual = AnalyzerResult.model_validate(response["result"])
    assert actual.status is AnalyzerStatus.COMPLETED
    assert actual.raw_metrics == result.raw_metrics
    assert not analyzer.check_applicability(audio_request(tmp_path, np.zeros(2048))).applicable
    assert (
        json.loads(_execute_worker(worker_request(analyzer, replace(request, metadata={}))))["kind"]
        == "analyzer_error"
    )
    request.artifacts[0].content._local_path.write_bytes(b"bad timing")
    assert (
        json.loads(_execute_worker(worker_request(analyzer, request)))["kind"] == "analyzer_error"
    )


@pytest.mark.parametrize("analyzer", ANALYZERS[:2], ids=lambda a: a.analyzer_id)
def test_video_small_geometry_not_applicable(tmp_path, analyzer):
    request = video_request(tmp_path, [np.zeros((12, 8, 15, 3), dtype="u1")])
    assert not analyzer.check_applicability(request).applicable
    response = json.loads(_execute_worker(worker_request(analyzer, request)))
    assert response["kind"] == "result"
    assert response["result"]["status"] == "not_applicable"
