from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf
from click.testing import CliRunner

from audioatlas.catalog_report import calculate_catalog_statistics, write_catalog_html
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
    md = (out_dir / "catalog.md").read_text(encoding="utf-8")
    assert 'href="alpha/report.html"' in html
    assert "[report.html](alpha/report.html)" in md
    assert "Folder-level technical fingerprints, not rankings." in html
    assert "It does not rank tracks or judge quality." in html


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

    for phrase in ["best", "worst", "score", "grade", "pass/fail", "better", "worse"]:
        assert phrase not in text
    assert "folder median" in text
    assert "technical fingerprints" in text
