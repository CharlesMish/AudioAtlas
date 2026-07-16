from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from audioatlas import __version__
from audioatlas.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_version_uses_package_source_of_truth():
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"audioatlas, version {__version__}"


def test_cli_help_exposes_privacy_and_batch_failure_controls():
    analyze_help = CliRunner().invoke(main, ["analyze", "--help"])
    batch_help = CliRunner().invoke(main, ["batch", "--help"])
    sections_help = CliRunner().invoke(main, ["sections", "--help"])

    assert analyze_help.exit_code == 0
    assert "--include-local-paths" in analyze_help.output
    assert batch_help.exit_code == 0
    assert "--strict" in batch_help.output
    assert "--include-local-paths" in batch_help.output
    assert sections_help.exit_code == 0
    assert "--include-local-paths" in sections_help.output


def test_importing_cli_does_not_eagerly_load_scientific_or_plotting_stack():
    script = """
import sys
import audioatlas.cli  # noqa: F401

heavy_modules = ("librosa", "matplotlib", "pyloudnorm", "scipy", "soundfile")
loaded = [name for name in heavy_modules if name in sys.modules]
if loaded:
    raise SystemExit("unexpected eager imports: " + ", ".join(loaded))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_importing_alt_text_does_not_eagerly_load_scientific_or_plotting_stack():
    script = """
import sys
import audioatlas.alt_text  # noqa: F401

heavy_modules = (
    "librosa", "matplotlib", "numpy", "pyloudnorm", "scipy", "soundfile"
)
loaded = [name for name in heavy_modules if name in sys.modules]
if loaded:
    raise SystemExit("unexpected eager imports: " + ", ".join(loaded))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(
        [sys.executable, "-S", "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_corrupt_single_file_has_clean_cli_error_without_traceback_or_path_leak(tmp_path):
    private_dir = tmp_path / "private-user-directory"
    private_dir.mkdir()
    path = private_dir / "broken.wav"
    path.write_bytes(b"RIFF-not-a-valid-audio-file")
    out = tmp_path / "report"

    result = CliRunner().invoke(
        main,
        [
            "analyze",
            str(path),
            "--out",
            str(out),
            "--graphs-profile",
            "minimal",
        ],
    )

    assert result.exit_code != 0
    assert "Error: Could not read audio file 'broken.wav'" in result.output
    assert "Traceback" not in result.output
    assert "private-user-directory" not in result.output
    assert str(tmp_path) not in result.output
    assert not out.exists()


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--start", "inf"], "--start: must be finite"),
        (["--max-duration", "inf"], "--max-duration: must be finite"),
        (["--rms-frame-length", "0"], "rms_frame_length must be a positive integer"),
        (["--db-floor", "nan"], "db_floor must be a finite number"),
    ],
)
def test_invalid_analysis_numbers_fail_before_preparation(tmp_path, options, message):
    source = ROOT / "tests" / "fixtures" / "sine_1k_-6dbfs_2s.wav"
    out = tmp_path / "report"

    result = CliRunner().invoke(
        main,
        ["analyze", str(source), "--out", str(out), *options],
    )

    assert result.exit_code == 2
    assert message in result.output
    assert "Preparing AudioAtlas" not in result.output
    assert "Traceback" not in result.output
    assert not out.exists()


def test_batch_rejects_non_finite_duration_before_preparation(tmp_path):
    source = tmp_path / "audio"
    source.mkdir()
    out = tmp_path / "catalog"

    result = CliRunner().invoke(
        main,
        ["batch", str(source), "--out", str(out), "--max-duration", "inf"],
    )

    assert result.exit_code == 2
    assert "--max-duration: must be finite" in result.output
    assert "Preparing AudioAtlas" not in result.output
    assert not out.exists()
