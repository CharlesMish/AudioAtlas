from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from audioatlas.analysis.levels import compute_scalar_levels
from audioatlas.analysis.stereo import compute_mid_side_energy, compute_stereo_correlation
from audioatlas.config import AnalysisConfig

_FAST_SETTINGS = settings(max_examples=10, derandomize=True, deadline=None)


@_FAST_SETTINGS
@given(gain_db=st.floats(min_value=-24.0, max_value=-0.25, allow_nan=False, allow_infinity=False))
def test_plr_is_invariant_under_constant_gain(gain_db: float) -> None:
    """Constant gain moves peak and LUFS together, leaving PLR unchanged."""

    sr = 16_000
    t = np.arange(sr, dtype=np.float64) / sr
    mono = 0.18 * np.sin(2 * np.pi * 311.0 * t) + 0.07 * np.sin(2 * np.pi * 997.0 * t)
    audio = np.stack([mono, 0.8 * mono], axis=1).astype(np.float32)
    scaled = (audio * (10.0 ** (gain_db / 20.0))).astype(np.float32)
    cfg = AnalysisConfig(true_peak_oversample=1)

    base = compute_scalar_levels(audio, sr, cfg)
    changed = compute_scalar_levels(scaled, sr, cfg)

    assert base.integrated_lufs is not None
    assert changed.integrated_lufs is not None
    assert base.plr_db is not None
    assert changed.plr_db is not None
    assert changed.sample_peak_dbfs - base.sample_peak_dbfs == pytest.approx(gain_db, abs=5e-4)
    assert changed.integrated_lufs - base.integrated_lufs == pytest.approx(gain_db, abs=5e-4)
    assert changed.plr_db == pytest.approx(base.plr_db, abs=7e-4)


@_FAST_SETTINGS
@given(
    phase=st.floats(min_value=-math.pi, max_value=math.pi, allow_nan=False, allow_infinity=False),
    right_gain=st.floats(min_value=0.1, max_value=0.95, allow_nan=False, allow_infinity=False),
)
def test_stereo_measurements_are_symmetric_under_channel_swap(
    phase: float, right_gain: float
) -> None:
    sr = 8_000
    t = np.arange(sr // 2, dtype=np.float64) / sr
    left = 0.3 * np.sin(2 * np.pi * 271.0 * t)
    right = right_gain * 0.3 * np.sin(2 * np.pi * 271.0 * t + phase)
    audio = np.stack([left, right], axis=1).astype(np.float32)
    swapped = audio[:, ::-1]
    cfg = AnalysisConfig(n_fft=256, hop_length=64, rms_frame_length=256)

    correlation = compute_stereo_correlation(audio, sr, cfg)
    correlation_swapped = compute_stereo_correlation(swapped, sr, cfg)
    mid_side = compute_mid_side_energy(audio, sr, cfg)
    mid_side_swapped = compute_mid_side_energy(swapped, sr, cfg)

    np.testing.assert_allclose(
        correlation.correlation,
        correlation_swapped.correlation,
        atol=1e-12,
        equal_nan=True,
    )
    assert correlation.overall_correlation == pytest.approx(
        correlation_swapped.overall_correlation, abs=1e-12
    )
    np.testing.assert_allclose(mid_side.mid_rms_linear, mid_side_swapped.mid_rms_linear, atol=1e-12)
    np.testing.assert_allclose(mid_side.side_rms_linear, mid_side_swapped.side_rms_linear, atol=1e-12)
    np.testing.assert_allclose(
        mid_side.side_to_mid_ratio_db,
        mid_side_swapped.side_to_mid_ratio_db,
        atol=1e-12,
        equal_nan=True,
    )


@_FAST_SETTINGS
@given(
    sample_count=st.integers(min_value=1, max_value=3_000),
    channels=st.integers(min_value=1, max_value=4),
)
def test_silence_and_subsecond_inputs_degrade_without_nonfinite_scalars(
    sample_count: int, channels: int
) -> None:
    sr = 8_000
    cfg = AnalysisConfig(true_peak_oversample=4, db_floor=-96.0)
    audio = np.zeros((sample_count, channels), dtype=np.float32)

    result = compute_scalar_levels(audio, sr, cfg)

    assert result.sample_peak_dbfs == pytest.approx(cfg.db_floor)
    assert result.rms_dbfs == pytest.approx(cfg.db_floor)
    assert result.clipped_samples == 0
    assert result.near_clipping_samples == 0
    assert len(result.dc_offset_per_channel) == channels
    assert all(math.isfinite(value) for value in result.dc_offset_per_channel)
    assert result.integrated_lufs is None
    assert result.plr_db is None
    if result.true_peak_dbtp is not None:
        assert math.isfinite(result.true_peak_dbtp)


@_FAST_SETTINGS
@given(offset=st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False))
def test_dc_offset_field_tracks_added_constant_offset(offset: float) -> None:
    sr = 8_000
    t = np.arange(sr // 2, dtype=np.float64) / sr
    zero_mean = 0.2 * np.sin(2 * np.pi * 200.0 * t)
    audio = (zero_mean + offset).astype(np.float32)[:, None]

    result = compute_scalar_levels(audio, sr, AnalysisConfig(true_peak_oversample=1))

    assert result.dc_offset_per_channel[0] == pytest.approx(offset, abs=2e-7)
    assert result.sample_peak_linear <= 0.401
