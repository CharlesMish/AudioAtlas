from __future__ import annotations

import numpy as np
import pytest

from audioatlas.alt_text import plot_alt_text
from audioatlas.analysis.bundle import _COMPUTE
from audioatlas.config import AnalysisConfig
from audioatlas.explanations import RELATIVE_BAND_DELTA_NOTE, SPECTRAL_CHANNEL_NOTE
from audioatlas.revision_diff import _band_power_deltas
from audioatlas.time_support import timeline_support


@pytest.mark.parametrize(
    "family,field",
    [
        ("rms", "rms_linear"),
        ("peaks", "frame_peak_linear"),
        ("crest", "crest_factor_db"),
        ("stereo", "correlation"),
        ("mid_side", "mid_rms_linear"),
        ("lr_balance", "balance_db"),
        ("spectral_shape", "spectral_centroid_hz"),
        ("onset", "smoothed_onset_density"),
    ],
)
def test_event_footprint_contains_known_event(family, field):
    sr = 8000
    y = np.zeros((sr * 10, 2))
    # Nonzero, unequal channels, exact one-sample event at 5 s.
    y[5 * sr] = [0.4, 0.2]
    cfg = AnalysisConfig(n_fft=512, rms_frame_length=512, hop_length=128)
    result = _COMPUTE[family](y, sr, cfg)
    support = timeline_support(family, result, cfg, sample_rate=sr, samples=len(y))
    values = getattr(result, field)
    active = np.isfinite(values) & (values != 0)
    assert np.any(active)
    assert np.all(support.source_start[active] <= 5 * sr)
    assert np.all(support.source_stop[active] > 5 * sr)
    assert support.time_origin == "analyzed_slice_start"
    # Same decoded slice, regardless of original-file start, has identical support.
    again = timeline_support(family, result, cfg, sample_rate=sr, samples=len(y))
    np.testing.assert_array_equal(support.intervals_seconds(), again.intervals_seconds())


def test_window_end_is_not_an_instant_and_last_block_keeps_actual_start():
    sr = 8000
    y = np.zeros((int(6.06 * sr), 2))
    y[5 * sr : 5 * sr + 80] = 0.1
    cfg = AnalysisConfig()
    r = _COMPUTE["short_term"](y, sr, cfg)
    s = timeline_support("short_term", r, cfg, sample_rate=sr, samples=len(y))
    assert s.anchor == "window_end_clipped_to_duration"
    assert s.frame_samples == 3 * sr
    assert s.source_stop[-1] == len(y)
    # Last label is clipped; subtracting 3 s from it would move the real start.
    assert abs(s.source_start[-1] / sr - (r.times_seconds[-1] - 3)) > 0.01
    strong = np.isfinite(r.lufs) & (r.lufs > np.nanmax(r.lufs) - 3)
    assert np.all(s.source_start[strong] <= 5 * sr + 80)
    assert np.all(s.source_stop[strong] > 5 * sr)
    assert np.all(s.dependency_intervals_seconds()[:, 0] == 0)


@pytest.mark.parametrize("n", [511, 512])
def test_centered_odd_and_even_frames_have_exact_sample_footprints(n):
    cfg = AnalysisConfig(rms_frame_length=n, hop_length=128)
    r = _COMPUTE["rms"](np.ones((700, 1)), 8000, cfg)
    s = timeline_support("rms", r, cfg, sample_rate=8000, samples=700)
    assert s.nominal_start[0] == -(n // 2)
    assert s.nominal_stop[0] - s.nominal_start[0] == n
    assert s.source_start[0] == 0
    assert s.source_stop[-1] == 700


def test_spectral_cancellation_warning_does_not_call_source_silent():
    t = np.arange(16000) / 8000
    x = 0.2 * np.sin(2 * np.pi * 750 * t)
    y = np.column_stack([x, -x])
    assert np.sqrt(np.mean(y**2)) > 0.1
    for family in ["spectral_shape", "band_power"]:
        r = _COMPUTE[family](y, 8000, AnalysisConfig())
        assert not np.any(r.valid_frames)
        assert "mono-downmix energy below the analysis floor" in r.warnings[0]
        assert "silent" not in r.warnings[0]
    assert "arithmetic-average mono downmix" in SPECTRAL_CHANNEL_NOTE
    for name in [
        "log_spectrogram",
        "average_spectrum",
        "spectral_shape",
        "band_energy_timeline",
        "onset_density",
        "chroma_cqt",
    ]:
        assert "arithmetic-average mono downmix" in plot_alt_text(name + ".png", {})


def test_relative_band_sign_reversal_preserves_historical_diff_meaning():
    sr = 8000
    t = np.arange(sr * 4) / sr
    # On-bin at this sample rate/FFT. Mid reference grows faster than target bass.
    bass = np.sin(2 * np.pi * 93.75 * t)
    mid = np.sin(2 * np.pi * 750 * t)
    a = 0.005 * bass + 0.1 * mid
    b = 0.01 * bass + 0.4 * mid
    cfg = AnalysisConfig()
    summaries = [
        dict(band_power_timeline=_COMPUTE["band_power"](y, sr, cfg).to_summary_dict())
        for y in [a, b]
    ]
    row = next(r for r in _band_power_deltas(*summaries) if r["band"] == "bass")
    assert row["delta_b_minus_a_db"] == pytest.approx(-20 * np.log10(2), abs=0.001)
    assert row["measurement"] == "relative_mean_power_per_fft_bin"
    assert "reverse the sign" in RELATIVE_BAND_DELTA_NOTE
    # Historical fallback remains readable, with no change in numeric semantics.
    historical = {"band_energy_timeline": summaries[0]["band_power_timeline"]}
    assert _band_power_deltas(historical, summaries[1]) == _band_power_deltas(*summaries)
