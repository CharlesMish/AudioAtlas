"""Regression against the independent-transform numerical contract."""

from __future__ import annotations

from dataclasses import fields

import librosa
import numpy as np
import pytest

from audioatlas.analysis.spectral import SpectralShapeResult, compute_spectral_shape
from audioatlas.config import AnalysisConfig
from audioatlas.utils import EPS, to_mono


def _independent_transform_reference(y, sr, cfg):
    """Pinned pre-optimization algorithm; preserve dtype and mask behavior."""
    mono = to_mono(y).astype(np.float64)
    kwargs = dict(
        y=mono, sr=sr, n_fft=cfg.n_fft, hop_length=cfg.hop_length, window=cfg.window, center=True
    )
    centroid = librosa.feature.spectral_centroid(**kwargs)[0].astype(np.float64)
    rolloff_85 = librosa.feature.spectral_rolloff(**kwargs, roll_percent=0.85)[0].astype(np.float64)
    rolloff_95 = librosa.feature.spectral_rolloff(**kwargs, roll_percent=0.95)[0].astype(np.float64)
    bandwidth = librosa.feature.spectral_bandwidth(**kwargs)[0].astype(np.float64)
    rms = librosa.feature.rms(
        y=mono, frame_length=cfg.n_fft, hop_length=cfg.hop_length, center=True
    )[0].astype(np.float64)
    valid = rms > EPS
    warnings = []
    if not np.all(valid):
        warnings.append("one or more silent frames; spectral shape values are undefined there")
    for arr in (centroid, rolloff_85, rolloff_95, bandwidth):
        arr[~valid] = np.nan
    times = librosa.frames_to_time(
        np.arange(len(centroid)), sr=sr, hop_length=cfg.hop_length
    ).astype(np.float64)
    return SpectralShapeResult(
        times,
        centroid,
        rolloff_85,
        rolloff_95,
        bandwidth,
        valid.astype(bool),
        sr,
        cfg.n_fft,
        cfg.hop_length,
        warnings,
    )


@pytest.mark.parametrize(
    "n_fft,hop,window", [(4096, 1024, "hann"), (255, 61, "boxcar"), (512, 127, "blackman")]
)
@pytest.mark.parametrize(
    "fixture",
    ["mono", "stereo", "silence", "antiphase", "short", "near_floor", "silence_then_tone"],
)
def test_spectral_shape_reuse_is_bit_exact(n_fft, hop, window, fixture):
    rng = np.random.default_rng(927)
    mono = rng.normal(0, 0.1, 8193).astype(np.float32)
    signals = {
        "mono": mono,
        "stereo": np.stack([mono, rng.normal(0, 0.2, len(mono)).astype(np.float32)], axis=1),
        "silence": np.zeros((8193, 2), dtype=np.float32),
        "antiphase": np.stack([mono, -mono], axis=1),
        "short": mono[:1],
        "near_floor": mono * 1e-12,
        "silence_then_tone": np.concatenate([np.zeros(8193, dtype=np.float32), mono]),
    }
    y = signals[fixture]
    cfg = AnalysisConfig(n_fft=n_fft, hop_length=hop, window=window)
    if fixture == "short":
        with pytest.warns(UserWarning, match="too large"):
            expected = _independent_transform_reference(y, 44100, cfg)
        with pytest.warns(UserWarning, match="too large"):
            actual = compute_spectral_shape(y, 44100, cfg)
    else:
        expected = _independent_transform_reference(y, 44100, cfg)
        actual = compute_spectral_shape(y, 44100, cfg)
    for field in fields(expected):
        old = getattr(expected, field.name)
        new = getattr(actual, field.name)
        if isinstance(old, np.ndarray):
            assert new.dtype == old.dtype
            assert new.shape == old.shape
            assert new.tobytes() == old.tobytes(), field.name
        else:
            assert new == old, field.name
    assert actual.to_summary_dict() == expected.to_summary_dict()


def test_spectral_shape_computes_one_transform(monkeypatch):
    calls = []
    original = librosa.stft

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    # Cover both direct public calls and transforms hidden inside features.
    monkeypatch.setattr(librosa, "stft", counted)
    monkeypatch.setattr(librosa.core.spectrum, "stft", counted)
    compute_spectral_shape(np.ones((8193, 2), dtype=np.float32), 44100)
    assert len(calls) == 1
