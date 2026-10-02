from types import SimpleNamespace

import numpy as np
import pytest

from audioatlas.analysis.bundle import AnalysisBundle
from audioatlas.config import AnalysisConfig
from audioatlas.evidence import aligned_cells, evidence_lanes


def bundle(y):
    return AnalysisBundle(
        SimpleNamespace(y=y, sr=8000),
        AnalysisConfig(n_fft=512, rms_frame_length=512, hop_length=128),
    )


def test_adapter_does_not_restore_skipped_families_and_detaches_arrays(monkeypatch):
    b = bundle(np.ones((16000, 2)))
    r = b.get("rms")
    cache = b.computed_results
    with pytest.raises(TypeError):
        cache["peaks"] = r
    monkeypatch.setattr(b, "get", lambda _: pytest.fail("adapter attempted computation"))
    lanes = evidence_lanes(b)
    assert [lane.key for lane in lanes] == ["rms"]
    np.testing.assert_array_equal(lanes[0].values, r.rms_dbfs)
    assert not np.shares_memory(lanes[0].values, r.rms_dbfs)
    with pytest.raises(ValueError):
        lanes[0].values[0] = 123
    assert set(b.computed_results) == {"rms"}


def test_undefined_gap_is_not_zero_or_interpolated():
    y = np.full((24000, 2), 0.2)
    y[8000:16000, 0] = 0
    b = bundle(y)
    r = b.get("lr_balance")
    (lane,) = evidence_lanes(b)
    assert np.any(lane.undefined_reasons == "left_below_floor")
    assert not len(lane.overlapping_indices(1.1, 1.9))
    cells = list(aligned_cells((lane,), duration_seconds=3, step_seconds=0.1))
    assert all(
        "lr_balance" not in c.indices_by_lane
        for c in cells
        if c.start_seconds >= 1.1 and c.end_seconds <= 1.9
    )
    np.testing.assert_array_equal(lane.values, r.balance_db)
    for cell in cells:
        for indices in cell.indices_by_lane.values():
            assert np.all(lane.valid[indices])
            intervals = lane.support.intervals_seconds()[indices]
            assert np.all(intervals[:, 1] > cell.start_seconds)
            assert np.all(intervals[:, 0] < cell.end_seconds)


def test_lufs_is_one_original_frame_referenced_across_cells():
    b = bundle(np.ones((32000, 2)) * 0.1)
    b.get("short_term")
    (lane,) = evidence_lanes(b)
    cells = list(aligned_cells((lane,), duration_seconds=4, step_seconds=1))
    assert all(0 in c.indices_by_lane["short_term_lufs"] for c in cells[:3])
    assert 0 not in cells[3].indices_by_lane["short_term_lufs"]
    assert lane.support.intervals_seconds()[0].tolist() == [0, 3]


def test_mono_not_applicable_and_multidimensional_families_not_flattened():
    b = bundle(np.zeros((8000, 1)))
    b.get("lr_balance")
    b.get("spectrogram")
    (lane,) = evidence_lanes(b)
    assert len(lane.values) == 0
    assert "not_applicable_mono" in lane.notes
    assert not list(aligned_cells((lane,), duration_seconds=0))
    with pytest.raises(ValueError):
        list(aligned_cells((lane,), duration_seconds=1, step_seconds=0))


def test_global_reference_does_not_claim_local_dependency():
    b = bundle(np.ones((8000, 2)) * 0.1)
    b.get("band_power")
    lanes = evidence_lanes(b)
    assert lanes
    with pytest.raises(ValueError, match="global reference"):
        lanes[0].support.dependency_intervals_seconds()


def test_selected_range_preserves_slice_relative_support(tmp_path):
    import soundfile as sf

    from audioatlas.io import load_audio

    sr = 8000
    y = np.zeros((sr * 5, 2), dtype=np.float32)
    y[3 * sr] = [0.4, 0.2]
    path = tmp_path / "event.wav"
    sf.write(path, y, sr, subtype="FLOAT")
    audio = load_audio(path, start_seconds=2, end_seconds=4)
    b = AnalysisBundle(audio, AnalysisConfig(n_fft=512, rms_frame_length=512, hop_length=128))
    b.get("peaks")
    (lane,) = evidence_lanes(b)
    active = lane.values > -99
    intervals = lane.support.intervals_seconds()[active]
    assert np.all(intervals[:, 0] <= 1)
    assert np.all(intervals[:, 1] > 1)
    assert audio.metadata.source_start_seconds == 2
    assert np.all(lane.times_seconds[active] < 1.01)
