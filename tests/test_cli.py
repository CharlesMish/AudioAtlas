from __future__ import annotations

import json

import numpy as np
import soundfile as sf
from click.testing import CliRunner

from audioatlas.cli import _parse_section_spec, _parse_sections_from_yaml, _section_slug, main


def _write_sections_fixture(path, *, seconds: int = 6, sr: int = 48_000) -> int:
    y = np.zeros((sr * seconds, 2), dtype=np.float32)
    y[: 3 * sr, :] = 0.1
    y[3 * sr :, :] = 0.3
    sf.write(path, y, sr)
    return sr


def test_cli_analyze_accepts_start_and_end_section(tmp_path):
    path = tmp_path / "section.wav"
    sr = 48_000
    y = np.zeros((sr * 3, 2), dtype=np.float32)
    y[sr : 3 * sr, :] = 0.25
    sf.write(path, y, sr)
    out_dir = tmp_path / "report"

    result = CliRunner().invoke(
        main,
        ["analyze", str(path), "--out", str(out_dir), "--start", "1", "--end", "3"],
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "report.html").exists()
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metadata"]["source_start_seconds"] == 1.0
    assert summary["metadata"]["source_end_seconds"] == 3.0
    assert summary["levels"]["duration_seconds"] == 2.0


def test_cli_sections_writes_one_report_per_manual_section(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    out_dir = tmp_path / "sections_out"

    result = CliRunner().invoke(
        main,
        [
            "sections",
            str(path),
            "--out",
            str(out_dir),
            "--section",
            "intro:0:3",
            "--section",
            "louder:3:6",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "section_index.md").exists()
    reports = sorted(out_dir.glob("*/report.html"))
    assert len(reports) == 2
    index = (out_dir / "section_index.md").read_text(encoding="utf-8")
    assert "manual" in index
    assert "intro" in index
    assert "louder" in index


def test_cli_sections_accepts_yaml_config(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    config_path = tmp_path / "sections.yaml"
    config_path.write_text(
        """\
sections:
  - name: intro
    start: 0
    end: 3
  - name: louder
    start: 3
    end: 6
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "yaml_sections"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "section_index.md").exists()
    reports = sorted(out_dir.glob("*/report.html"))
    assert len(reports) == 2
    index = (out_dir / "section_index.md").read_text(encoding="utf-8")
    assert "intro" in index
    assert "louder" in index

    intro_summary = json.loads(
        (out_dir / "000p000_003p000_intro" / "summary.json").read_text(encoding="utf-8")
    )
    assert intro_summary["metadata"]["source_start_seconds"] == 0.0
    assert intro_summary["metadata"]["source_end_seconds"] == 3.0


def test_cli_sections_yaml_omitted_end_matches_eof_section_spec(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path, seconds=4)
    config_path = tmp_path / "ending.yaml"
    config_path.write_text(
        """\
sections:
  - name: ending
    start: 2
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "yaml_eof"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code == 0, result.output
    expected_slug = _section_slug("ending", 2.0, None)
    assert (out_dir / expected_slug / "report.html").exists()
    index = (out_dir / "section_index.md").read_text(encoding="utf-8")
    assert "2s-EOF" in index

    cli_slug = _section_slug(*_parse_section_spec("ending:2:"))
    yaml_slug = _section_slug(*_parse_sections_from_yaml(config_path)[0])
    assert cli_slug == yaml_slug == expected_slug


def test_cli_sections_mixed_section_and_config(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    config_path = tmp_path / "sections.yaml"
    config_path.write_text(
        """\
sections:
  - name: louder
    start: 3
    end: 6
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "mixed_sections"

    result = CliRunner().invoke(
        main,
        [
            "sections",
            str(path),
            "--out",
            str(out_dir),
            "--section",
            "intro:0:3",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0, result.output
    reports = sorted(out_dir.glob("*/report.html"))
    assert len(reports) == 2
    index = (out_dir / "section_index.md").read_text(encoding="utf-8")
    assert index.index("intro") < index.index("louder")


def test_cli_sections_requires_section_or_config(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    out_dir = tmp_path / "empty"

    result = CliRunner().invoke(main, ["sections", str(path), "--out", str(out_dir)])

    assert result.exit_code != 0
    assert "at least one --section or --config" in result.output


def test_cli_sections_rejects_invalid_yaml(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("sections: [name: intro\n", encoding="utf-8")
    out_dir = tmp_path / "bad_yaml"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code != 0
    assert "Invalid YAML" in result.output


def test_cli_sections_rejects_yaml_missing_name(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    config_path = tmp_path / "missing_name.yaml"
    config_path.write_text(
        """\
sections:
  - start: 0
    end: 3
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "missing_name"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code != 0
    assert "string name" in result.output


def test_cli_sections_rejects_yaml_invalid_range(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    config_path = tmp_path / "invalid_range.yaml"
    config_path.write_text(
        """\
sections:
  - name: bad
    start: 5
    end: 5
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "invalid_range"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code != 0
    assert "greater than start" in result.output