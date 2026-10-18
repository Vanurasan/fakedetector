"""Frozen stress recipes, parity refusal and localization boundary conventions."""

import copy
import subprocess
from pathlib import Path

import numpy as np
import pytest

with pytest.MonkeyPatch.context() as imports:
    imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts import diploma_vrc2_prototype_applicability as harness


def samples(tmp_path):
    return [
        {
            "dataset": "benign",
            "role": "BENIGN_REFERENCE",
            "source_family": f"video-{i:02}",
            "sample_id": f"video-{i:02}-reference",
            "path": str(tmp_path / f"source-{i}.mp4"),
            "sha256": str(i) * 64,
            "facts": {"technical_parameters": {"width": 48, "height": 32}},
        }
        for i in range(1, 9)
    ]


def test_frozen_matrix_complete_unique_and_no_method_search(tmp_path):
    matrix = harness.matrix(tmp_path, samples(tmp_path))
    assert matrix["method"] == "D2__I25__K9__R10"
    cells = matrix["cells"]
    assert len(cells) == len({(r["cell"], r["source_family"]) for r in cells}) == 128
    assert {
        axis: sum(c["axis"] == axis for c in cells)
        for axis in ("cadence", "repeat-length", "near-copy")
    } == {"cadence": 40, "repeat-length": 40, "near-copy": 48}
    assert matrix == harness.matrix(tmp_path, samples(tmp_path))
    for cell in cells:
        assert cell["known_source"][0] == 0.25 and cell["known_destination"][0] == 10.25
        for output in cell["outputs"].values():
            for command in output["commands"]:
                assert "-n" in command and "-y" not in command
                assert "{w}" not in str(command) and "{h}" not in str(command)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (None, 1, (None, "insufficient")),
        (0, None, (None, "insufficient")),
        (0, 0, (0, "zero")),
        (0.25, 0.5, (0.25, "positive")),
        (0.5, 0.25, (-0.25, "negative")),
    ],
)
def test_paired_sign_preserves_null_and_strict_sign(a, b, expected):
    assert harness.paired_sign(a, b) == expected


def test_parity_refuses_metric_state_and_run_changes():
    expected = dict.fromkeys(harness.FIELDS.values(), 1.0)
    expected.update(state="MEASURED", best_run={"constituents": [{"distance": 1.0}]})
    actual = {new: expected[old] for new, old in harness.FIELDS.items()}
    actual["best_run"] = copy.deepcopy(expected["best_run"])
    assert harness.compare(actual, expected)["max_difference"] == 0
    for field, value in (
        ("d_best", 1.001),
        ("state", "INSUFFICIENT_RUN_SUPPORT"),
        ("relative_distinctiveness", None),
        ("best_run", None),
    ):
        with pytest.raises(ValueError, match="STOP"):
            harness.compare({**actual, field: value}, expected)
    actual["best_run"]["constituents"][0]["distance"] = 0.9
    with pytest.raises(ValueError, match="constituents"):
        harness.compare(actual, expected)


def test_runtime_isolation_gate_rejects_runtime_exposure(monkeypatch):
    assert harness.runtime_isolation()["pass"]
    monkeypatch.setattr(harness, "_resolve_runtime_analyzer_definition", lambda _: object())
    with pytest.raises(ValueError, match="runtime isolation"):
        harness.runtime_isolation()


@pytest.mark.parametrize("start,overlap,contained", [(6, 9, 9), (1, 7, 4), (24, 0, 0)])
def test_localization_closed_pts_half_open_episode(start, overlap, contained):
    pairs = [
        {
            side: {"pts_ticks": list(range(offset + i, offset + i + 4)), "time_base": [1, 24]}
            for side, offset in (("a", 0), ("b", 240))
        }
        for i in range(start, start + 9)
    ]
    metrics = {"best_run": {"constituents": pairs}}
    cell = {"known_source": [0.25, 1], "known_destination": [10.25, 11]}
    result = harness.localization(metrics, cell)
    assert result["overlap_count"] == overlap
    assert result["fully_contained_count"] == contained
    assert result["temporal_lag_error"] == pytest.approx(0)
    assert result["FULLY_CONTAINED"] == (contained == 9)
    assert result["MAJORITY_OVERLAP"] == (overlap >= 5)
    assert harness.localization({"best_run": None}, cell)["source_span"] is None


def test_frozen_ffmpeg_recipes_preserve_duration_pts_and_determinism(tmp_path):
    source = tmp_path / "source-1.mp4"
    pixels = np.random.default_rng(74).integers(0, 256, (288, 32, 48, 3), dtype="u1")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "48x32",
            "-r",
            "24",
            "-i",
            "pipe:0",
            "-c:v",
            "mpeg4",
            "-q:v",
            "2",
            "-g",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-video_track_timescale",
            "24000",
            str(source),
        ],
        input=pixels.tobytes(),
        capture_output=True,
        check=True,
        timeout=30,
    )
    matrix = harness.matrix(tmp_path, samples(tmp_path))
    for cell in matrix["cells"][:16]:
        for role, output in cell["outputs"].items():
            path = Path(output["path"])
            path.parent.mkdir(exist_ok=True)
            for command in output["commands"]:
                subprocess.run(command, check=True, capture_output=True, timeout=30)
            assert harness.prior.probe_pts(path) == [
                i * (24000 // cell["fps"]) for i in range(cell["fps"] * 12)
            ]
            if cell["cell"] == "N0_EXACT" and role == "repeat":
                completed = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(path),
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "pipe:1",
                    ],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
                frames = np.frombuffer(completed.stdout, dtype="u1").reshape(288, 32, 48, 3)
                assert np.array_equal(frames[6:24], frames[246:264])
