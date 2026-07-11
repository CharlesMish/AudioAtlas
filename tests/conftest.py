from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def sr() -> int:
    return 48_000


def sine_wave(freq: float, amp: float, sr: int, duration: float, channels: int = 1) -> np.ndarray:
    t = np.arange(int(sr * duration), dtype=np.float64) / sr
    mono = amp * np.sin(2 * np.pi * freq * t)
    if channels == 1:
        return mono.astype(np.float32)[:, None]
    return np.repeat(mono[:, None], channels, axis=1).astype(np.float32)


@pytest.fixture
def sine_minus_6_dbfs(sr: int) -> np.ndarray:
    amp = 10 ** (-6 / 20)
    return sine_wave(1000, amp, sr, 1.0, channels=1)


@pytest.fixture
def clipped_sine(sr: int) -> np.ndarray:
    y = sine_wave(1000, 1.2, sr, 1.0, channels=1)
    return np.clip(y, -1.0, 1.0).astype(np.float32)


@pytest.fixture
def stereo_phase_inverted(sr: int) -> np.ndarray:
    left = sine_wave(1000, 0.5, sr, 1.0, channels=1)[:, 0]
    return np.stack([left, -left], axis=1).astype(np.float32)


@pytest.fixture
def stereo_correlated(sr: int) -> np.ndarray:
    left = sine_wave(1000, 0.5, sr, 1.0, channels=1)[:, 0]
    return np.stack([left, left], axis=1).astype(np.float32)
