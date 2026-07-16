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
from audioatlas.output import OUTPUT_MARKER_FILENAME
from audioatlas.release import CATALOG_SCHEMA_VERSION


def _write_sine(
    path: Path,
    *,
    freq: float,
    amp: float = 0.2,
    sr: int = 48_000,
    seconds: float = 1.0,
) -> None:
    t = np.arange(int(sr * seconds), dtype=np.float64) / sr
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
    assert catalog["schema_version"] == CATALOG_SCHEMA_VERSION
    assert catalog["input_folder"] == input_dir.name
    assert catalog["output_folder"] == out_dir.name
    assert catalog["path_kind"] == "basename"
    assert catalog["local_paths_included"] is False
    assert str(tmp_path) not in (out_dir / "catalog_summary.json").read_text(
        encoding="utf-8"
    )
    assert catalog["skipped_files"] == [
        {
            "filename": "notes.txt",
            "reason": "unsupported file extension",
            "status": "skipped",
        }
    ]
    assert catalog["tracks"][0]["report_path"] == "alpha/report.html"
    manifest = json.loads(
        (out_dir / OUTPUT_MARKER_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["kind"] == "batch-catalog"
    assert manifest["generated_directories"] == ["alpha", "beta"]

    html = (out_dir / "catalog.html").read_text(encoding="utf-8")
    track_html = (out_dir / "alpha" / "report.html").read_text(encoding="utf-8")
    md = (out_dir / "catalog.md").read_text(encoding="utf-8")
    assert 'href="alpha/report.html"' in html
    assert "[report.html](alpha/report.html)" in md
    assert "Folder-level technical fingerprints, not verdicts." in html
    assert "It does not rank tracks or judge quality." in html
    assert "--bg: #f7f0e4;" in html
    assert "--bg: #f7f0e4;" in track_html


def test_batch_cli_graph_selection_applies_to_each_track_and_catalog_populates(
    tmp_path: Path,
):
    input_dir = tmp_path / "audio"
    input_dir.mkdir()
    _write_sine(input_dir / "alpha.wav", freq=330)
    _write_sine(input_dir / "beta.wav", freq=660)
    out_dir = tmp_path / "catalog"

    result = CliRunner().invoke(
        main,
        [
            "batch",
            str(input_dir),
            "--out",
            str(out_dir),
            "--graphs-profile",
            "minimal",
            "--n-fft",
            "1024",
            "--hop-length",
            "256",
            "--rms-frame-length",
            "1024",
            "--true-peak-oversample",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    for name in ["alpha", "beta"]:
        summary = json.loads((out_dir / name / "summary.json").read_text(encoding="utf-8"))
        assert len(summary["plots"]) == 4
        assert "short_term_lufs" in summary
        assert "stereo_correlation" in summary

    catalog = json.loads((out_dir / "catalog_summary.json").read_text(encoding="utf-8"))
    assert catalog["track_count"] == 2
    assert all(track["integrated_lufs"] is not None for track in catalog["tracks"])
    assert all("median_stereo_correlation" in track for track in catalog["tracks"])


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
            "average_spectrum": {"highest_mean_power_band": "mid"},
            "spectral_shape": {
                "centroid_median_hz": 2345.0,
                "rolloff_95_median_hz": 9876.0,
            },
        },
        findings={"findings_shown": []},
    )

    assert record["centroid_median_hz"] == 2345.0
    assert record["rolloff_95_median_hz"] == 9876.0
    assert record["highest_mean_power_band"] == "mid"
    assert record["strongest_band"] == "mid"


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
    assert '<body data-presentation="studio">' in html
    assert 'class="skip-link" href="#main-content"' in html
    assert '<nav class="top-nav" aria-label="Catalog sections">' in html
    assert 'role="region" aria-label="Analyzed tracks" tabindex="0"' in html
    assert "decoded-audio delivery context" in md


def test_catalog_markdown_escapes_user_controlled_labels(tmp_path: Path):
    catalog = build_catalog_summary(
        input_folder=tmp_path / "audio | *draft*",
        output_folder=tmp_path / "reports _two_",
        tracks=[
            {
                "filename": "mix | *draft* _two_.wav",
                "report_path": "mix-draft-two/report.html",
            }
        ],
        skipped_files=[{"filename": "notes | old.txt", "reason": "not *audio*"}],
    )

    path = write_catalog_md(catalog, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert r"# AudioAtlas Catalog: audio \| \*draft\*" in text
    assert r"mix \| \*draft\* \_two\_.wav" in text
    assert r"notes \| old.txt: not \*audio\*" in text


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
            "highest_mean_power_band": "bass",
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
            "highest_mean_power_band": "mid",
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

    assert '<th scope="col">Traits</th>' in html
    assert '<th scope="col">Shown findings</th>' in html
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


def test_catalog_local_paths_are_only_included_by_explicit_opt_in(tmp_path: Path):
    catalog = build_catalog_summary(
        input_folder=tmp_path / "private-input",
        output_folder=tmp_path / "private-output",
        tracks=[],
        skipped_files=[],
        include_local_paths=True,
    )

    assert catalog["input_folder"] == str((tmp_path / "private-input").resolve())
    assert catalog["output_folder"] == str((tmp_path / "private-output").resolve())
    assert catalog["path_kind"] == "absolute"
    assert catalog["local_paths_included"] is True


def test_batch_continues_after_corrupt_supported_file_and_records_failure(tmp_path: Path):
    input_dir = tmp_path / "private-user-name" / "audio"
    input_dir.mkdir(parents=True)
    (input_dir / "bad.wav").write_bytes(b"not audio")
    _write_sine(input_dir / "good.wav", freq=440, seconds=0.25)
    out_dir = tmp_path / "catalog"

    result = CliRunner().invoke(
        main,
        [
            "batch",
            str(input_dir),
            "--out",
            str(out_dir),
            "--graphs-profile",
            "minimal",
            "--n-fft",
            "512",
            "--hop-length",
            "128",
            "--rms-frame-length",
            "512",
            "--true-peak-oversample",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Skipped files:   1" in result.output
    catalog_text = (out_dir / "catalog_summary.json").read_text(encoding="utf-8")
    catalog = json.loads(catalog_text)
    assert catalog["track_count"] == 1
    assert [track["filename"] for track in catalog["tracks"]] == ["good.wav"]
    assert (out_dir / "good" / "report.html").exists()
    assert len(catalog["skipped_files"]) == 1
    skipped = catalog["skipped_files"][0]
    assert skipped["filename"] == "bad.wav"
    assert skipped["status"] == "analysis_failed"
    assert "Could not read audio file 'bad.wav'" in skipped["reason"]
    assert str(tmp_path) not in skipped["reason"]
    assert str(input_dir) not in catalog_text
    assert not (out_dir / "bad").exists()


def test_batch_strict_failure_leaves_previous_catalog_untouched(tmp_path: Path):
    input_dir = tmp_path / "audio"
    input_dir.mkdir()
    (input_dir / "bad.wav").write_bytes(b"not audio")
    out_dir = tmp_path / "catalog"
    out_dir.mkdir()
    previous = '{"known_good": true}\n'
    (out_dir / "catalog_summary.json").write_text(previous, encoding="utf-8")
    (out_dir / "human-notes.txt").write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["batch", str(input_dir), "--out", str(out_dir), "--strict"],
    )

    assert result.exit_code != 0
    assert "Could not read audio file 'bad.wav'" in result.output
    assert "Traceback" not in result.output
    assert (out_dir / "catalog_summary.json").read_text(encoding="utf-8") == previous
    assert (out_dir / "human-notes.txt").read_text(encoding="utf-8") == "keep"


def test_batch_with_no_successes_writes_diagnostic_catalog_then_returns_nonzero(
    tmp_path: Path,
):
    input_dir = tmp_path / "audio"
    input_dir.mkdir()
    (input_dir / "bad.wav").write_bytes(b"not audio")
    out_dir = tmp_path / "catalog"

    result = CliRunner().invoke(
        main,
        ["batch", str(input_dir), "--out", str(out_dir)],
    )

    assert result.exit_code != 0
    assert "No audio files were analyzed" in result.output
    catalog = json.loads((out_dir / "catalog_summary.json").read_text(encoding="utf-8"))
    assert catalog["track_count"] == 0
    assert catalog["skipped_files"][0]["status"] == "analysis_failed"
    assert (out_dir / "catalog.html").exists()
    assert (out_dir / "catalog.md").exists()
