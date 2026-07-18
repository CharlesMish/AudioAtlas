from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

import audioatlas.io as io_module
from audioatlas.errors import AudioLoadError, SourceChangedError
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
    assert loaded.metadata.path == "test.wav"
    assert loaded.metadata.path_kind == "basename"
    assert loaded.metadata.local_paths_included is False
    assert np.isclose(float(loaded.y[0, 0]), 0.25, atol=1e-4)


def test_load_audio_can_read_manual_time_section(tmp_path, sr):
    path = tmp_path / "section.wav"
    y = np.zeros((sr * 3, 1), dtype=np.float32)
    y[sr : 2 * sr, 0] = 0.5
    sf.write(path, y, sr)

    loaded = load_audio(path, start_seconds=1.0, end_seconds=2.0)

    assert loaded.y.shape == (sr, 1)
    assert loaded.metadata.duration_seconds == 1.0
    assert loaded.metadata.source_start_seconds == 1.0
    assert loaded.metadata.source_end_seconds == 2.0
    assert loaded.metadata.source_duration_seconds == 3.0
    assert np.isclose(float(np.mean(loaded.y[:, 0])), 0.5, atol=1e-4)


def test_missing_audio_uses_same_clean_domain_error(tmp_path):
    path = tmp_path / "secret-folder" / "missing.wav"

    with pytest.raises(AudioLoadError, match="file does not exist") as caught:
        load_audio(path)

    assert path.name in str(caught.value)
    assert str(path.parent) not in str(caught.value)


def test_load_audio_can_include_resolved_local_path_by_explicit_opt_in(tmp_path, sr):
    path = tmp_path / "local.wav"
    sf.write(path, np.zeros((sr // 10, 1), dtype=np.float32), sr)

    loaded = load_audio(path, include_local_paths=True)

    assert loaded.metadata.path == str(path.resolve())
    assert loaded.metadata.path_kind == "absolute"
    assert loaded.metadata.local_paths_included is True


def test_load_audio_corrupt_error_is_domain_specific_and_redacts_parent_path(tmp_path):
    private_folder = tmp_path / "private-user-name"
    private_folder.mkdir()
    path = private_folder / "corrupt.wav"
    path.write_bytes(b"not audio")

    with pytest.raises(AudioLoadError) as caught:
        load_audio(path)

    message = str(caught.value)
    assert "Could not read audio file 'corrupt.wav'" in message
    assert str(tmp_path) not in message
    assert "Traceback" not in message


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start_seconds": float("inf")}, "start_seconds must be finite"),
        ({"end_seconds": float("nan")}, "end_seconds must be finite"),
        ({"max_duration_seconds": float("inf")}, "max_duration_seconds must be finite"),
    ],
)
def test_load_audio_rejects_non_finite_ranges(tmp_path, sr, kwargs, message):
    path = tmp_path / "finite.wav"
    sf.write(path, np.zeros((sr // 10, 1), dtype=np.float32), sr)

    with pytest.raises(ValueError, match=message):
        load_audio(path, **kwargs)


def test_load_audio_rejects_source_changed_during_decode(
    tmp_path, sr, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "exporting.wav"
    sf.write(path, np.zeros((sr // 10, 1), dtype=np.float32), sr)
    identities = iter([(1, 2, 3, 4), (1, 2, 5, 6)])
    monkeypatch.setattr(io_module, "_source_identity", lambda supplied: next(identities))

    with pytest.raises(SourceChangedError, match="changed while it was being read"):
        load_audio(path)
