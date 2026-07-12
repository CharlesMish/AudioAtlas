from __future__ import annotations

import numpy as np
import soundfile as sf

from audioatlas.analysis.bundle import _COMPUTE
from audioatlas.config import AnalysisConfig
from audioatlas.graphs import all_graphs, graph_by_key
from audioatlas.graphs.registry import validate_registry
from audioatlas.graphs.selection import GraphSelection
from audioatlas.output import PLOT_FILENAMES
from audioatlas.pipeline import analyze_file

EXPECTED_KEYS = [
    "waveform_rms",
    "rms_timeline",
    "crest_factor_timeline",
    "log_spectrogram",
    "average_spectrum",
    "sample_histogram",
    "stereo_correlation",
    "mid_side_energy",
    "spectral_shape",
    "band_energy_timeline",
    "onset_density",
    "chroma_cqt",
    "short_term_lufs",
    "peak_timeline",
    "peak_vs_rms",
    "rms_histogram",
    "stereo_correlation_histogram",
]

EXPECTED_FILENAMES = [
    "waveform_rms.png",
    "rms_timeline.png",
    "crest_factor_timeline.png",
    "log_spectrogram.png",
    "average_spectrum.png",
    "sample_histogram.png",
    "stereo_correlation.png",
    "mid_side_energy.png",
    "spectral_shape.png",
    "band_energy_timeline.png",
    "onset_density.png",
    "chroma_cqt.png",
    "short_term_lufs.png",
    "peak_timeline.png",
    "peak_vs_rms.png",
    "rms_histogram.png",
    "stereo_correlation_histogram.png",
]

EXPECTED_STANDARD_FILENAMES = [
    "waveform_rms.png",
    "rms_timeline.png",
    "crest_factor_timeline.png",
    "log_spectrogram.png",
    "average_spectrum.png",
    "sample_histogram.png",
    "stereo_correlation.png",
    "mid_side_energy.png",
    "spectral_shape.png",
    "band_energy_timeline.png",
    "onset_density.png",
    "chroma_cqt.png",
    "short_term_lufs.png",
    "peak_timeline.png",
]

EXPECTED_WIDE_FILENAMES = {
    "log_spectrogram.png",
    "average_spectrum.png",
    "band_energy_timeline.png",
    "onset_density.png",
    "chroma_cqt.png",
    "short_term_lufs.png",
}


def test_registry_integrity_and_current_contract():
    validate_registry()

    graphs = all_graphs()
    keys = [graph.key for graph in graphs]
    filenames = [graph.filename for graph in graphs]

    assert len(graphs) == 17
    assert keys == EXPECTED_KEYS
    assert filenames == EXPECTED_FILENAMES
    assert frozenset(filenames) == PLOT_FILENAMES
    assert len(set(keys)) == len(keys)
    assert len(set(filenames)) == len(filenames)
    assert [graph.order for graph in graphs] == list(range(1, 18))
    assert {graph.filename for graph in graphs if graph.wide} == EXPECTED_WIDE_FILENAMES

    for graph in graphs:
        assert all(name in _COMPUTE for name in graph.requires)
        assert callable(graph.render)
        assert graph.enabled_by_default == ("standard" in graph.profiles)


def test_graph_by_key_returns_registered_graph():
    assert graph_by_key("waveform_rms").filename == "waveform_rms.png"
    assert graph_by_key("short_term_lufs").filename == "short_term_lufs.png"
    assert graph_by_key("peak_timeline").filename == "peak_timeline.png"
    assert graph_by_key("peak_vs_rms").profiles == frozenset({"full"})
    assert graph_by_key("rms_histogram").profiles == frozenset({"full"})
    assert graph_by_key("stereo_correlation_histogram").profiles == frozenset({"full"})


def test_pipeline_renders_registry_default_filenames(tmp_path, sr):
    path = tmp_path / "song.wav"
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, y, sr)

    result = analyze_file(
        path,
        tmp_path / "report",
        config=AnalysisConfig(
            n_fft=1024,
            hop_length=256,
            rms_frame_length=1024,
            welch_nperseg=1024,
            true_peak_oversample=1,
        ),
    )

    assert [plot.name for plot in result.plot_paths] == EXPECTED_STANDARD_FILENAMES
    assert result.summary["plots"] == EXPECTED_STANDARD_FILENAMES
    assert result.summary["graphs"]["selected"] == [
        graph.key for graph in GraphSelection().resolve(all_graphs())
    ]
