"""Arithmetic/protocol evidence only, never assertions of forensic validity."""

import hashlib
import math
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from fakedetector.config.models import AppConfig
from fakedetector.preprocessing._media_tools import TileRegion

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts.research.jpeg_calibration import measure
    from scripts.research.jpeg_corpus import Case, decoded, encode, source_image
    from scripts.research.jpeg_measurements import (
        MODES,
        axis_measurement,
        grid_window,
        histogram,
        ideal_bin_count,
        ideal_requantize,
        log_tail,
        measure_grid,
        native_raster,
        rectangle_count,
        windows,
    )


def test_signed_histogram_golden():
    result = histogram(np.array([-2, -2, 0, 1], dtype="<i4"))
    assert (result.n, result.minimum, result.maximum, result.span) == (4, -2, 1, 4)
    assert (result.occupied, result.zero_fraction, result.empty_fraction) == (3, 0.25, 0.25)
    # H=[2,0,1,1]/4; A1=sqrt(2)/4, A2=1/2.
    assert result.frequency == 0.5
    assert result.amplitude == 0.5
    assert histogram(np.array([2, 2], dtype="<i4")).zero_fraction == 0


def test_constant_empty_fft_tie_and_bounded_integer_range():
    assert histogram(np.array([], dtype="<i4")).state == "no_full_blocks"
    constant = histogram(np.array([0], dtype="<i4"))
    assert constant.state == "constant"
    assert constant.frequency is None and constant.amplitude is None
    # Uniform four bins: all non-DC amplitudes tie at exactly zero; first j wins.
    tied = histogram(np.arange(4, dtype="<i4"))
    assert (tied.frequency, tied.amplitude) == (0.25, 0)
    bounded = histogram(np.array([0, 65535], dtype="<i4"))
    assert bounded.span == 65536 and bounded.amplitude is not None
    for values in ([0, 65536], [-(2**31), 2**31 - 1]):
        result = histogram(np.array(values, dtype="<i4"))
        assert result.state == "histogram_limit"
        assert result.span == values[1] - values[0] + 1
        assert result.occupied is None
    assert len(MODES) == 9 and tuple(sorted(MODES)) == MODES and (0, 0) not in MODES


@pytest.mark.parametrize("q1,q2", [(3, 2), (2, 3), (8, 8), (8, 16), (8, 9)])
def test_ideal_requantization_independent_rational_reference(q1, q2):
    from fractions import Fraction

    for t in range(-100, 101):
        first = math.floor(Fraction(t, q1) + Fraction(1, 2))
        expected = math.floor(Fraction(q1 * first, q2) + Fraction(1, 2))
        assert ideal_requantize(t, q1, q2) == expected
    period = q1 // math.gcd(q1, q2)
    for k in range(-10, 11):
        observed = sum(
            math.floor(Fraction(q1 * a, q2) + Fraction(1, 2)) == k for a in range(-100, 101)
        )
        assert ideal_bin_count(k, q1, q2) == observed
        assert ideal_bin_count(k + period, q1, q2) == observed
    assert ideal_requantize(2**60, q1, q2) > 2**31


@pytest.mark.parametrize(
    "eta,kappa,p", [(16, 4, 0.125), (256, 64, 0.2), (4096, 1000, 0.24), (4096, 2000, 0.01)]
)
def test_log_tail_independent_decimal_direct_binomial(eta, kappa, p):
    with localcontext() as ctx:
        ctx.prec = 60
        probability = Decimal.from_float(p)
        tail = sum(
            Decimal(math.comb(eta, j)) * probability**j * (1 - probability) ** (eta - j)
            for j in range(kappa, eta + 1)
        )
        reference = float(tail.ln())
    assert log_tail(eta, kappa, p) == pytest.approx(reference, abs=2e-10)
    assert log_tail(16, 0, 0) == 0 and log_tail(16, 16, 1) == 0
    with pytest.raises(ValueError):
        log_tail(16, 1, 0)


def test_nfa_ties_and_zero_support():
    assert axis_measurement((0,) * 8, 4096, 16).ell is None
    tied = axis_measurement((8,) * 8, 4096, 16)
    assert tied.boundary_phase is None and tied.block_phase is None
    assert tied.ell is not None
    result = axis_measurement((0, 0, 0, 0, 0, 0, 0, 32), 4096, 16)
    expected = math.log10(16) + log_tail(256, 16, 32 / 4096) / math.log(10)
    assert result.ell == expected
    assert result.boundary_phase == 7 and result.block_phase == 0


@pytest.mark.parametrize("px", range(8))
@pytest.mark.parametrize("py", range(8))
def test_all_native_boundary_phases(px, py):
    y, x = np.indices((67, 67))
    raster = (40 * (((x - px) // 8) % 2) * (((y - py) // 8) % 2)).astype(np.uint8)
    result = measure_grid(raster, check_time=lambda: 60)[0]
    assert result.x.block_phase == px
    assert result.y.block_phase == py
    assert result.x.boundary_phase == (px - 1) % 8
    assert result.y.boundary_phase == (py - 1) % 8
    assert result.x.n == result.y.n == 64
    assert result.flag


def test_window_geometry_and_strict_comparisons():
    assert windows(66, 67) == windows(67, 66) == ()
    assert windows(67, 67) == (TileRegion(x=1, y=1, width=64, height=64),)
    regions = windows(1200, 900)
    assert len(regions) == 16
    assert [(r.x, r.y) for r in regions] == [
        (x, y) for y in (1, 129, 257, 386) for x in (1, 229, 457, 686)
    ]
    assert rectangle_count(67) == sum(67 - 8 * j + 1 for j in range(1, 9))
    constant = measure_grid(np.full((67, 67), 128, np.uint8), check_time=lambda: 60)[0]
    assert constant.support == (0, 0, 67, 67)
    assert not constant.flag and constant.x.n == constant.y.n == 0
    # Constant positive C: equal neighbours must not vote either.
    y, x = np.indices((67, 67))
    result = grid_window((x * y).astype(float), windows(67, 67)[0], 16)
    assert result.x.n == result.y.n == 0


def test_panorama_patch_coverage_and_resource_boundary():
    regions = windows(4096, 256)
    for patch_x, expected in ((100, True), (600, False)):
        intersects = any(
            patch_x < r.x + r.width + 2
            and patch_x + 16 > r.x - 1
            and r.y + r.height + 2 > 100
            and r.y - 1 < 116
            for r in regions
        )
        assert intersects is expected
    assert len(windows(2048, 2048)) == 16
    with pytest.raises(ValueError):
        windows(2049, 2048)


def test_log_tail_at_exact_model_nfa_boundary():
    # P[Binomial(256,1/2)>=256]=2^-256; Nt=2^256 makes the exact ell zero.
    ell = math.log10(2**256) + log_tail(256, 256, 0.5) / math.log(10)
    assert abs(ell) < 1e-12


def test_vectorized_votes_match_independent_scalar_loop():
    luminance = np.random.default_rng(8).integers(0, 256, (67, 67)).astype(float)

    def cross(x, y):
        return abs(
            luminance[y, x] + luminance[y + 1, x + 1] - luminance[y, x + 1] - luminance[y + 1, x]
        )

    xs, ys = [0] * 8, [0] * 8
    for y in range(1, 65):
        for x in range(1, 65):
            c = cross(x, y)
            if c > cross(x - 1, y) and c > cross(x + 1, y):
                xs[x % 8] += 1
            if c > cross(x, y - 1) and c > cross(x, y + 1):
                ys[y % 8] += 1
    observed = grid_window(luminance, windows(67, 67)[0], 16)
    assert observed.x.counts == tuple(xs) and observed.y.counts == tuple(ys)


@pytest.mark.parametrize("orientation", range(1, 9))
def test_inverse_exif_against_pillow(orientation):
    raster = np.arange(7 * 11, dtype=np.uint8).reshape(7, 11)
    transforms = {
        2: Image.Transpose.FLIP_LEFT_RIGHT,
        3: Image.Transpose.ROTATE_180,
        4: Image.Transpose.FLIP_TOP_BOTTOM,
        5: Image.Transpose.TRANSPOSE,
        6: Image.Transpose.ROTATE_270,
        7: Image.Transpose.TRANSVERSE,
        8: Image.Transpose.ROTATE_90,
    }
    image = Image.fromarray(raster)
    oriented = image.transpose(transforms[orientation]) if orientation != 1 else image
    assert np.array_equal(native_raster(np.asarray(oriented), orientation), raster)


def test_real_preprocessing_orientation_progressive_and_cleanup(tmp_path):
    config = AppConfig.model_validate(
        yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    )
    (tmp_path / "corpus").mkdir()
    source = source_image("smooth", 1, (103, 79))
    baseline = None
    for orientation in range(1, 9):
        data = encode(source, 75, 2, orientation % 2 == 0, orientation)
        _, tables = decoded(data)
        case = Case(
            f"exif-{orientation}",
            "same-source",
            "test",
            "smooth",
            "single",
            "exif",
            103,
            79,
            "RGB",
            hashlib.sha256(data).hexdigest(),
            len(data),
            None,
            75,
            2,
            orientation % 2 == 0,
            orientation,
            (0, 0),
            {},
            tables,
        )
        (tmp_path / "corpus" / f"{case.case_id}.jpg").write_bytes(data)
        result = measure(case, tmp_path, config)
        if baseline is None:
            baseline = result
        assert result.dq == baseline.dq
        assert result.grid == baseline.grid
        assert result.dq[0].histogram.n == (103 // 8) * (79 // 8)
        assert result.dq[9].histogram.n == (103 // 16) * (79 // 16)
        assert not list((tmp_path / "workspace").rglob("*.raw"))
        assert not list((tmp_path / "workspace").rglob("*.png"))
    assert baseline is not None
    with pytest.raises(ValueError, match="identity"):
        measure(replace(case, sha256="0" * 64), tmp_path, config)
