from __future__ import annotations

import numpy as np
import soundfile as sf

from audioatlas.io import load_audio


def test_load_audio_preserves_shape_and_metadata(tmp_path, sr):
    path = tmp_path / "test.wav"
    y = np.zeros((sr, 2), dtype=np.float32)
    y[:, 0] = 0.25
    y[:, 1] = -0.25
    sf.write(path, y, sr)

    loaded = load_audio(path)

    assert loaded.y.shape == (sr, 2)
    assert loaded.sr == sr
    assert loaded.metadata.channels == 2
    assert loaded.metadata.frames == sr
    assert loaded.metadata.duration_seconds == 1.0
    assert np.isclose(float(loaded.y[0, 0]), 0.25, atol=1e-4)
