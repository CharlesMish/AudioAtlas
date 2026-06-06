from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf
from click.testing import CliRunner

from audioatlas.catalog_report import (
    build_catalog_summary,
    calculate_catalog_statistics,
    decoded_audio_context,
    detect_common_patterns,
    track_record_from_run,
    write_catalog_html,
    write_catalog_md,
)
from audioatlas.cli import main


def _write_sine(path: Path, *, freq: float, amp: float = 0.2, sr: int = 48_000) -> None:
    t = np.arange(int(sr * 1.0), dtype=np.float64) / sr
    y = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(path, y, sr)


def test_batch_cli_creates_per_track_reports_and_catalog_outputs(tmp_path: Path):
    input_dir = tmp_path / "audio"
    input_dir.mkdir()
    _write_sine(input_dir / "alpha.wav", freq=330)
    _write_sine(input_dir / "beta.wav", freq=660)
    (input_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    out_dir = tmp_path / "catalog"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "batch",
            str(input_dir),
            "--out",
            str(out_dir),
            "--n-fft",
            "1024",
            "--hop-length",
            "256",
            "--rms-frame-length",
            "1024",
            "--true-peak-oversample",
            "1",
            "--theme",
            "warm_tape",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "catalog_summary.json").exists()
    assert (out_dir / "catalog.md").exists()
    assert (out_dir / "catalog.html").exists()
    for name in ["alpha", "beta"]:
        assert (out_dir / name / "report.html").exists()
        assert (out_dir / name / "report.md").exists()
        assert (out_dir / name / "summary.json").exists()
        assert (out_dir / name / "findings.json").exists()

    catalog = json.loads((out_dir / "catalog_summary.json").read_text(encoding="utf-8"))
    assert catalog["track_count"] == 2
    assert [track["filename"] for track in catalog["tracks"]] == ["alpha.wav", "beta.wav"]
    assert catalog["skipped_files"] == [
        {"filename": "notes.txt", "reason": "unsupported file extension"}
    ]
    assert catalog["tracks"][0]["report_path"] == "alpha/report.html"

    html = (out_dir / "catalog.html").read_text(encoding="utf-8")
    track_html = (out_dir / "alpha" / "report.html").read_text(encoding="utf-8")
    md = (out_dir / "catalog.md").read_text(encoding="utf-8")
    assert 'href="alpha/report.html"' in html
    assert "[report.html](alpha/report.html)" in md
    assert "Folder-level technical fingerprints, not verdicts." in html
    assert "It does not rank tracks or judge quality." in html
    assert "--bg: #f7f0e4;" in html
    assert "--bg: #f7f0e4;" in track_html


def test_catalog_statistics_calculate_folder_min_median_max():
    tracks = [
        {"integrated_lufs": -14.0, "plr_db": 10.0},
        {"integrated_lufs": -10.0, "plr_db": 8.0},
        {"integrated_lufs": -8.0, "plr_db": None},
    ]

    stats = calculate_catalog_statistics(tracks)

    assert stats["integrated_lufs"]["count"] == 3
    assert stats["integrated_lufs"]["min"] == -14.0
    assert stats["integrated_lufs"]["median"] == -10.0
    assert stats["integrated_lufs"]["max"] == -8.0
    assert stats["plr_db"]["count"] == 2
    assert stats["plr_db"]["median"] == 9.0
    assert stats["plr_db"]["missing_count"] == 1


def test_catalog_track_record_extracts_spectral_shape_values():
    record = track_record_from_run(
        filename="shape.wav",
        report_path="shape/report.html",
        summary={
            "metadata": {"samplerate": 48_000, "channels": 2},
            "levels": {"duration_seconds": 1.0},
            "spectral_shape": {
                "centroid_median_hz": 2345.0,
                "rolloff_95_median_hz": 9876.0,
            },
        },
        findings={"findings_shown": []},
    )

    assert record["centroid_median_hz"] == 2345.0
    assert record["rolloff_95_median_hz"] == 9876.0


def test_common_patterns_detect_traits_above_threshold_and_ignore_rare_traits():
    tracks = [
        {"filename": f"track-{index}.mp3", "format": "MP3", "true_peak_dbtp": 0.2}
        for index in range(7)
    ]
    tracks.extend(
        {"filename": f"quiet-{index}.wav", "format": "WAV", "true_peak_dbtp": -1.0}
        for index in range(3)
    )
    for index, track in enumerate(tracks):
        track["clipped_samples"] = 1 if index == 0 else 0
        track["near_clipping_samples"] = 0

    patterns = detect_common_patterns(tracks)
    ids = {pattern["id"] for pattern in patterns}

    assert "true_peak_above_0" in ids
    assert "decoded_level_footprint" in ids
    assert "clipped_samples_present" not in ids


def test_lossy_decoded_catalog_caveat_renders_for_mp3_heavy_folder(tmp_path: Path):
    tracks = [
        {
            "filename": f"track-{index}.mp3",
            "format": "MP3",
            "subtype": "MPEG_LAYER_III",
            "report_path": f"track-{index}/report.html",
        }
        for index in range(7)
    ]
    tracks.extend(
        {
            "filename": f"track-{index}.wav",
            "format": "WAV",
            "report_path": f"track-{index}/report.html",
        }
        for index in range(3)
    )
    catalog = build_catalog_summary(
        input_folder=tmp_path / "input_audio",
        output_folder=tmp_path / "reports",
        tracks=tracks,
        skipped_files=[],
    )
    assert decoded_audio_context(catalog["tracks"])["applies"] is True

    html_path = write_catalog_html(catalog, tmp_path)
    md_path = write_catalog_md(catalog, tmp_path)
    html = html_path.read_text(encoding="utf-8")
    md = md_path.read_text(encoding="utf-8")

    assert "About these files" in html
    assert "decoded-audio delivery context" in html
    assert "do not establish whether the original master clipped" in html
    assert "decoded-audio delivery context" in md


def test_catalog_html_uses_trait_tags_and_distribution_median_ticks(tmp_path: Path):
    tracks = [
        {
            "filename": "alpha.mp3",
            "format": "MP3",
            "report_path": "alpha/report.html",
            "duration_seconds": 1.0,
            "integrated_lufs": -8.0,
            "true_peak_dbtp": 0.3,
            "plr_db": 8.0,
            "median_stereo_correlation": 0.2,
            "median_side_to_mid_ratio_db": -5.0,
            "rolloff_95_median_hz": 7000.0,
            "strongest_band": "bass",
            "clipped_samples": 2,
            "near_clipping_samples": 10,
            "findings_shown_count": 3,
        },
        {
            "filename": "beta.mp3",
            "format": "MP3",
            "report_path": "beta/report.html",
            "duration_seconds": 1.0,
            "integrated_lufs": -12.0,
            "true_peak_dbtp": -1.0,
            "plr_db": 12.0,
            "median_stereo_correlation": 0.8,
            "median_side_to_mid_ratio_db": -12.0,
            "rolloff_95_median_hz": 11000.0,
            "strongest_band": "mid",
            "clipped_samples": 0,
            "near_clipping_samples": 0,
            "findings_shown_count": 0,
        },
    ]
    catalog = build_catalog_summary(
        input_folder=tmp_path / "input_audio",
        output_folder=tmp_path / "reports",
        tracks=tracks,
        skipped_files=[],
    )
    html = write_catalog_html(catalog, tmp_path).read_text(encoding="utf-8")

    assert "<th>Traits</th>" in html
    assert "<th>Shown findings</th>" in html
    assert "decoded levels" in html
    assert "3 shown" in html
    assert "median-tick" in html
    assert "track-dot" in html
    assert "<th>Findings</th>" not in html


def test_catalog_html_renders_non_default_theme(tmp_path: Path):
    catalog = build_catalog_summary(
        input_folder=tmp_path / "input_audio",
        output_folder=tmp_path / "reports",
        tracks=[{"filename": "alpha.wav", "report_path": "alpha/report.html"}],
        skipped_files=[],
    )
    html = write_catalog_html(catalog, tmp_path, theme_name="studio_blue").read_text(
        encoding="utf-8"
    )

    assert "--bg: #f0f4f8;" in html
    assert "--trait-bg:" in html
    assert "<link" not in html
    assert "src=\"http" not in html
    assert "href=\"http" not in html


def test_dark_catalog_theme_uses_theme_variables_for_common_pattern_cards(tmp_path: Path):
    tracks = [
        {
            "filename": f"track-{index}.mp3",
            "format": "MP3",
            "report_path": f"track-{index}/report.html",
            "true_peak_dbtp": 0.2,
            "near_clipping_samples": 1,
            "clipped_samples": 0,
        }
        for index in range(7)
    ]
    tracks.extend(
        {
            "filename": f"quiet-{index}.wav",
            "format": "WAV",
            "report_path": f"quiet-{index}/report.html",
            "true_peak_dbtp": -1.0,
            "near_clipping_samples": 0,
            "clipped_samples": 0,
        }
        for index in range(3)
    )
    catalog = build_catalog_summary(
        input_folder=tmp_path / "input_audio",
        output_folder=tmp_path / "reports",
        tracks=tracks,
        skipped_files=[],
    )
    html = write_catalog_html(catalog, tmp_path, theme_name="midnight_studio").read_text(
        encoding="utf-8"
    )

    assert "Common patterns in this folder" in html
    for leaked_color in [
        "color: #1e293b",
        "color: #334155",
        "color: #475569",
        "color: #64748b",
        "color: #94a3b8",
    ]:
        assert leaked_color not in html
    assert re.search(
        r"\.distribution-card h3, \.fingerprint-card h3, \.pattern-card h3 \{[^}]*color: var\(--text\)",
        html,
    )
    assert ".pattern-card p { margin: 6px 0; color: var(--text-muted);" in html
    assert ".track-table th { color: var(--text);" in html
    assert ".glossary-list dt { color: var(--text);" in html


def test_catalog_html_language_avoids_scoring_terms(tmp_path: Path):
    catalog = {
        "input_folder": "demo",
        "track_count": 1,
        "tracks": [
            {
                "filename": "alpha.wav",
                "report_path": "alpha/report.html",
                "duration_seconds": 1.0,
                "integrated_lufs": -12.0,
                "true_peak_dbtp": -1.0,
                "plr_db": 11.0,
                "median_stereo_correlation": 1.0,
                "median_side_to_mid_ratio_db": None,
                "strongest_band": "mid",
                "findings_shown_count": 0,
            }
        ],
        "statistics": calculate_catalog_statistics(
            [{"integrated_lufs": -12.0, "true_peak_dbtp": -1.0, "plr_db": 11.0}]
        ),
    }
    path = write_catalog_html(catalog, tmp_path)
    text = path.read_text(encoding="utf-8").lower()

    for phrase in ["best", "worst", "score", "grade", "pass/fail", "better", "worse", "leaderboard"]:
        assert phrase not in text
    assert "folder median" in text
    assert "technical fingerprints" in text
