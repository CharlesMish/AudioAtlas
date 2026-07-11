from __future__ import annotations

from click.testing import CliRunner

from audioatlas import __version__
from audioatlas.cli import main


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
