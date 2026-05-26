"""Golden end-to-end test against a committed audio fixture.

This is the regression anchor: a known sine wave, known expected metrics.
If an agent refactor causes any of these numbers to drift outside the
recorded tolerances, this test fails - regardless of unit-test coverage.

To regenerate the fixture, run ``python tests/fixtures/_build_golden.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from audioatlas.config import AnalysisConfig
from audioatlas.pipeline import analyze_file

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN_WAV = FIXTURES / "sine_1k_-6dbfs_2s.wav"
GOLDEN_EXPECTED = FIXTURES / "sine_1k_-6dbfs_2s.expected.json"


@pytest.fixture(scope="module")
def expected() -> dict:
    return json.loads(GOLDEN_EXPECTED.read_text(encoding="utf-8"))


def test_golden_fixture_files_exist():
    assert GOLDEN_WAV.exists(), (
        "Golden WAV is missing. Run: python tests/fixtures/_build_golden.py"
    )
    assert GOLDEN_EXPECTED.exists(), (
        "Golden expected JSON is missing. Run: python tests/fixtures/_build_golden.py"
    )


def test_pipeline_matches_golden_values(tmp_path: Path, expected: dict):
    cfg = AnalysisConfig(
        n_fft=2048,
        hop_length=512,
        rms_frame_length=2048,
        welch_nperseg=4096,
        true_peak_oversample=1,
    )
    result = analyze_file(GOLDEN_WAV, tmp_path / "out", config=cfg)

    levels = result.summary["levels"]
    spectrum = result.summary["average_spectrum"]

    assert levels["sample_rate"] == expected["sample_rate"]
    assert levels["channels"] == expected["channels"]
    assert levels["duration_seconds"] == pytest.approx(
        expected["duration_seconds"], abs=1e-3
    )
    assert levels["clipped_samples"] == expected["clipped_samples"]
    assert levels["near_clipping_samples"] == expected["near_clipping_samples"]

    assert levels["sample_peak_dbfs"] == pytest.approx(
        expected["sample_peak_dbfs_approx"],
        abs=expected["sample_peak_dbfs_tolerance"],
    )
    assert levels["rms_dbfs"] == pytest.approx(
        expected["rms_dbfs_approx"], abs=expected["rms_dbfs_tolerance"]
    )
    assert levels["crest_factor_db"] == pytest.approx(
        expected["crest_factor_db_approx"],
        abs=expected["crest_factor_db_tolerance"],
    )
    assert spectrum["strongest_bin_hz"] == pytest.approx(
        expected["strongest_bin_hz_approx"],
        abs=expected["strongest_bin_hz_tolerance"],
    )

    # Files actually got written.
    assert result.summary_path.exists()
    assert result.report_path.exists()
    for p in result.plot_paths:
        assert p.exists() and p.stat().st_size > 0


def test_pipeline_summary_carries_schema_version(tmp_path: Path):
    cfg = AnalysisConfig(
        n_fft=2048, hop_length=512, rms_frame_length=2048,
        welch_nperseg=4096, true_peak_oversample=1,
    )
    result = analyze_file(GOLDEN_WAV, tmp_path / "out", config=cfg)
    assert "schema_version" in result.summary
    assert result.summary["schema_version"] == "0.1.0"
