from __future__ import annotations

import numpy as np
import pytest

from audioatlas.utils import (
    EPS,
    ensure_2d_audio,
    linear_to_dbfs,
    mmss,
    power_to_db,
    safe_stem,
    to_mono,
)


class TestEnsure2dAudio:
    def test_1d_input_becomes_column(self):
        y = np.zeros(100, dtype=np.float32)
        out = ensure_2d_audio(y)
        assert out.shape == (100, 1)
        assert out.dtype == np.float32

    def test_2d_input_unchanged(self):
        y = np.zeros((100, 2), dtype=np.float32)
        out = ensure_2d_audio(y)
        assert out.shape == (100, 2)

    def test_3d_input_rejected(self):
        with pytest.raises(ValueError):
            ensure_2d_audio(np.zeros((10, 2, 3), dtype=np.float32))


class TestToMono:
    def test_mono_passthrough(self):
        y = np.ones((100, 1), dtype=np.float32) * 0.5
        out = to_mono(y)
        assert out.shape == (100,)
        assert np.allclose(out, 0.5)

    def test_stereo_arithmetic_mean(self):
        y = np.zeros((100, 2), dtype=np.float32)
        y[:, 0] = 0.4
        y[:, 1] = 0.6
        out = to_mono(y)
        assert np.allclose(out, 0.5)


class TestLinearToDbfs:
    def test_full_scale_is_zero_db(self):
        assert linear_to_dbfs(1.0) == pytest.approx(0.0, abs=1e-9)

    def test_minus_six_db_amp(self):
        assert linear_to_dbfs(0.5) == pytest.approx(-6.0, abs=0.05)

    def test_zero_amp_returns_eps_db_without_floor(self):
        # No floor: returns -240 dB-ish from EPS clamp
        val = linear_to_dbfs(0.0)
        assert val < -200.0

    def test_zero_amp_respects_floor(self):
        assert linear_to_dbfs(0.0, floor_db=-100.0) == pytest.approx(-100.0, abs=1e-9)

    def test_floor_does_not_clip_louder_values(self):
        # Floor should only clamp at the bottom.
        assert linear_to_dbfs(0.5, floor_db=-100.0) == pytest.approx(-6.0, abs=0.05)

    def test_array_input_returns_array(self):
        out = linear_to_dbfs(np.array([1.0, 0.5, 0.0]), floor_db=-100.0)
        assert isinstance(out, np.ndarray)
        assert out[0] == pytest.approx(0.0, abs=1e-9)
        assert out[1] == pytest.approx(-6.0, abs=0.05)
        assert out[2] == pytest.approx(-100.0, abs=1e-9)


class TestPowerToDb:
    def test_unit_power_is_zero_db(self):
        assert power_to_db(1.0) == pytest.approx(0.0, abs=1e-9)

    def test_zero_power_respects_floor(self):
        assert power_to_db(0.0, floor_db=-100.0) == pytest.approx(-100.0, abs=1e-9)


class TestMmss:
    def test_basic(self):
        assert mmss(0.0) == "0:00"
        assert mmss(59.0) == "0:59"
        assert mmss(60.0) == "1:00"
        assert mmss(125.7) == "2:06"

    def test_nan_or_inf_safe(self):
        assert mmss(float("nan")) == "?:??"
        assert mmss(float("inf")) == "?:??"


class TestSafeStem:
    def test_replaces_spaces(self):
        assert safe_stem("/tmp/some song name.wav") == "some_song_name"

    def test_no_extension(self):
        assert safe_stem("foo") == "foo"


def test_eps_is_positive_and_small():
    # Trivial regression guard - EPS underpins the dB conversions.
    assert 0 < EPS < 1e-6
