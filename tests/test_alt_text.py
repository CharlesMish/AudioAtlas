from __future__ import annotations

from pathlib import Path

from audioatlas.alt_text import ALT_GRAPH_METADATA, plot_alt_text
from audioatlas.graphs.registry import all_graphs
from audioatlas.html_report import write_report_html
from audioatlas.report import write_report_md


def _summary() -> dict:
    return {
        "metadata": {
            "filename": "revision.wav",
            "samplerate": 48_000,
            "channels": 2,
            "format": "WAV",
            "subtype": "PCM_24",
        },
        "analysis_config": {},
        "analysis_provenance": {
            "analysis_config_sha256": "a" * 64,
            "compatible_analysis_sha256": "b" * 64,
        },
        "levels": {
            "duration_seconds": 10.0,
            "sample_peak_dbfs": -0.8,
            "true_peak_dbtp": -0.5,
            "integrated_lufs": -12.0,
            "rms_dbfs": -15.0,
            "plr_db": 11.5,
            "clipped_samples": 0,
            "near_clipping_samples": 9,
        },
        "rms_envelope": {"rms_dbfs_min": -42.0, "rms_dbfs_max": -6.0},
        "crest_factor_timeline": {
            "crest_factor_db_min": 2.0,
            "crest_factor_db_max": 14.0,
        },
        "average_spectrum": {
            "strongest_bin_hz": 440.0,
            "highest_mean_power_band": "mid",
        },
        "stereo_correlation": {
            "correlation_min": -0.2,
            "correlation_max": 0.98,
            "correlation_median": 0.71,
        },
        "mid_side_energy": {
            "mid_rms_dbfs_min": -40.0,
            "mid_rms_dbfs_max": -7.0,
            "side_rms_dbfs_min": -55.0,
            "side_rms_dbfs_max": -12.0,
            "side_to_mid_ratio_db_median": -9.4,
        },
        "spectral_shape": {
            "centroid_min_hz": 700.0,
            "centroid_max_hz": 5200.0,
            "rolloff_95_median_hz": 11_200.0,
        },
        "band_power_timeline": {
            "bands": {
                "bass": {"median_db": -16.0},
                "mid": {"median_db": -2.0},
            },
            "highest_mean_power_band_by_median": "mid",
        },
        "onset_density": {"onset_density_median": 0.12, "onset_density_max": 0.9},
        "chroma_cqt": {"dominant_pitch_class": "A"},
        "short_term_lufs": {"lufs_min": -18.0, "lufs_median": -12.1, "lufs_max": -8.0},
        "peak_timeline": {
            "frame_peak_dbfs": [-12.0, -3.0, -0.8],
            "frames_with_near_clipping": 2,
        },
    }


def test_alt_text_contains_measured_ranges_instead_of_only_titles() -> None:
    summary = _summary()

    waveform = plot_alt_text("waveform_rms.png", summary)
    spectrogram = plot_alt_text("log_spectrogram.png", summary)
    stereo = plot_alt_text("stereo_correlation.png", summary)
    histogram = plot_alt_text("sample_histogram.png", summary)

    assert "-42.00 to -6.00 dBFS RMS" in waveform
    assert "20 to 24000 Hz" in spectrogram
    assert "-0.20 to 0.98 Pearson r" in stereo
    assert "sample peak -0.80 dBFS" in histogram
    assert "0 clipped samples" in histogram


def test_lightweight_alt_metadata_matches_the_graph_registry() -> None:
    expected = {
        graph.filename: (graph.key, graph.display_name)
        for graph in all_graphs()
    }

    assert expected == ALT_GRAPH_METADATA


def test_every_registered_graph_has_bounded_nonjudgmental_alt_text() -> None:
    summary = _summary()

    for graph in all_graphs():
        text = plot_alt_text(graph.filename, summary)
        assert text.startswith(graph.display_name)
        assert text.endswith(".")
        assert len(text) < 320
        lowered = text.lower()
        for forbidden in ("good mix", "bad mix", "better", "worse", "quality score"):
            assert forbidden not in lowered


def test_html_and_markdown_embed_the_measured_alt_text(tmp_path: Path) -> None:
    summary = _summary()
    plot_files = ["waveform_rms.png", "short_term_lufs.png"]

    html = write_report_html(summary, plot_files, tmp_path).read_text(encoding="utf-8")
    markdown = write_report_md(summary, plot_files, tmp_path).read_text(encoding="utf-8")

    waveform_alt = plot_alt_text("waveform_rms.png", summary)
    short_lufs_alt = plot_alt_text("short_term_lufs.png", summary)
    assert f'alt="{waveform_alt}"' in html
    assert f'alt="{short_lufs_alt}"' in html
    assert f"![{waveform_alt}](waveform_rms.png)" in markdown
    assert f"![{short_lufs_alt}](short_term_lufs.png)" in markdown
    assert 'alt="Waveform + RMS Envelope"' not in html
