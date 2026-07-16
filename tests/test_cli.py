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
    assert summary["metadata"]["path"] == "section.wav"
    assert summary["metadata"]["path_kind"] == "basename"
    assert str(tmp_path) not in json.dumps(summary)
    assert summary["levels"]["duration_seconds"] == 2.0


def test_cli_analyze_graphs_profile_minimal_renders_subset(tmp_path):
    path = tmp_path / "song.wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    y[:, 0] = 0.2
    sf.write(path, y, sr)
    out_dir = tmp_path / "minimal_report"

    result = CliRunner().invoke(
        main,
        [
            "analyze",
            str(path),
            "--out",
            str(out_dir),
            "--graphs-profile",
            "minimal",
            "--include-local-paths",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["plots"] == [
        "waveform_rms.png",
        "rms_timeline.png",
        "log_spectrogram.png",
        "sample_histogram.png",
    ]
    assert summary["graphs"]["profile"] == "minimal"
    assert summary["metadata"]["path"] == str(path.resolve())
    assert summary["metadata"]["path_kind"] == "absolute"
    assert summary["metadata"]["local_paths_included"] is True
    assert len(list(out_dir.glob("*.png"))) == 4
    assert "chroma_cqt" in summary
    assert "stereo_correlation" in summary


def test_cli_analyze_default_standard_renders_fourteen_plots(tmp_path):
    path = tmp_path / "song.wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    y[:, 0] = 0.2
    sf.write(path, y, sr)
    out_dir = tmp_path / "standard_report"

    result = CliRunner().invoke(main, ["analyze", str(path), "--out", str(out_dir)])

    assert result.exit_code == 0, result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["graphs"]["profile"] == "standard"
    assert len(summary["plots"]) == 14
    assert summary["plots"][-1] == "peak_timeline.png"
    assert len(list(out_dir.glob("*.png"))) == 14


def test_cli_analyze_graphs_profile_full_renders_extension_pack(tmp_path):
    path = tmp_path / "song.wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    y[:, 0] = 0.2
    sf.write(path, y, sr)
    out_dir = tmp_path / "full_report"

    result = CliRunner().invoke(
        main,
        ["analyze", str(path), "--out", str(out_dir), "--graphs-profile", "full"],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["plots"]) == 17
    assert summary["plots"][-4:] == [
        "peak_timeline.png",
        "peak_vs_rms.png",
        "rms_histogram.png",
        "stereo_correlation_histogram.png",
    ]
    assert len(list(out_dir.glob("*.png"))) == 17


def test_cli_analyze_minimal_can_enable_full_only_graph(tmp_path):
    path = tmp_path / "song.wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    y[:, 0] = 0.2
    sf.write(path, y, sr)
    out_dir = tmp_path / "minimal_peak_report"

    result = CliRunner().invoke(
        main,
        [
            "analyze",
            str(path),
            "--out",
            str(out_dir),
            "--graphs-profile",
            "minimal",
            "--enable",
            "peak_vs_rms",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["plots"]) == 5
    assert summary["plots"][-1] == "peak_vs_rms.png"
    assert "frame_peak_dbfs" in summary["peak_timeline"]
    assert "rms_envelope" in summary


def test_cli_analyze_graph_enable_and_disable(tmp_path):
    path = tmp_path / "song.wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    y[:, 0] = 0.2
    sf.write(path, y, sr)
    out_dir = tmp_path / "selected_report"

    result = CliRunner().invoke(
        main,
        [
            "analyze",
            str(path),
            "--out",
            str(out_dir),
            "--graphs-profile",
            "minimal",
            "--enable",
            "chroma_cqt,short_term_lufs",
            "--disable",
            "rms_timeline",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["graphs"]["selected"] == [
        "waveform_rms",
        "log_spectrogram",
        "sample_histogram",
        "chroma_cqt",
        "short_term_lufs",
    ]
    assert summary["plots"] == [
        "waveform_rms.png",
        "log_spectrogram.png",
        "sample_histogram.png",
        "chroma_cqt.png",
        "short_term_lufs.png",
    ]


def test_cli_analyze_graphs_config_file(tmp_path):
    path = tmp_path / "song.wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    y[:, 0] = 0.2
    sf.write(path, y, sr)
    config_path = tmp_path / "graphs.yaml"
    config_path.write_text(
        """\
graphs:
  profile: minimal
  enable: [chroma_cqt]
  disable: [rms_timeline]
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "config_report"

    result = CliRunner().invoke(
        main,
        ["analyze", str(path), "--out", str(out_dir), "--graphs-config", str(config_path)],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["graphs"]["selected"] == [
        "waveform_rms",
        "log_spectrogram",
        "sample_histogram",
        "chroma_cqt",
    ]


def test_cli_analyze_bad_graph_key_fails_before_analysis(tmp_path):
    path = tmp_path / "song.wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    sf.write(path, y, sr)
    out_dir = tmp_path / "bad_key_report"

    result = CliRunner().invoke(
        main,
        ["analyze", str(path), "--out", str(out_dir), "--enable", "missing_graph"],
    )

    assert result.exit_code != 0
    assert "missing_graph" in result.output
    assert not out_dir.exists()


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
    # New comparison table assertions (uses existing summary fields)
    assert "Section comparison (manual sections only)" in index
    assert "Integrated LUFS" in index
    assert "PLR (dB)" in index
    assert "Median stereo corr." in index
    assert "Median 95% rolloff (Hz)" in index
    assert "report.md" in index
    assert "report.html" in index
    # different source ranges
    assert "0s-3s" in index or "0.000s-3s" in index
    assert "3s-6s" in index or "3.000s-6s" in index


def test_cli_sections_graph_selection_applies_to_each_section(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    out_dir = tmp_path / "selected_sections"

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
            "--graphs-profile",
            "minimal",
        ],
    )

    assert result.exit_code == 0, result.output
    for summary_path in sorted(out_dir.glob("*/summary.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert len(summary["plots"]) == 4
        assert "short_term_lufs" in summary
        assert "stereo_correlation" in summary
    index = (out_dir / "section_index.md").read_text(encoding="utf-8")
    assert "Integrated LUFS" in index
    assert "Median stereo corr." in index


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


def test_cli_sections_yaml_accepts_short_section_range(tmp_path):
    path = tmp_path / "short.wav"
    sr = 48_000
    y = np.zeros((sr * 2, 1), dtype=np.float32)
    y[: sr // 2, 0] = 0.2
    sf.write(path, y, sr)
    config_path = tmp_path / "short.yaml"
    config_path.write_text(
        """\
sections:
  - name: middle
    start: 1
    end: 1.5
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "short_section"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code == 0, result.output
    section_dir = out_dir / _section_slug("middle", 1.0, 1.5)
    assert (section_dir / "report.html").exists()
    assert (section_dir / "summary.json").exists()
    summary = json.loads((section_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metadata"]["source_start_seconds"] == 1.0
    assert summary["metadata"]["source_end_seconds"] == 1.5


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


def test_cli_sections_rejects_colliding_output_slugs_before_writing(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    out_dir = tmp_path / "colliding_sections"

    result = CliRunner().invoke(
        main,
        [
            "sections",
            str(path),
            "--out",
            str(out_dir),
            "--section",
            "A/B:0:3",
            "--section",
            "A B:0:3",
        ],
    )

    assert result.exit_code == 2
    assert "same output folder" in result.output
    assert "Preparing AudioAtlas" not in result.output
    assert not out_dir.exists()


def test_cli_sections_rejects_non_finite_range_before_writing(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    out_dir = tmp_path / "non_finite_section"

    result = CliRunner().invoke(
        main,
        [
            "sections",
            str(path),
            "--out",
            str(out_dir),
            "--section",
            "intro:inf:",
        ],
    )

    assert result.exit_code == 2
    assert "Section start time must be finite" in result.output
    assert "Preparing AudioAtlas" not in result.output
    assert not out_dir.exists()


def test_cli_sections_escapes_section_names_in_markdown_index(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    out_dir = tmp_path / "escaped_sections"

    result = CliRunner().invoke(
        main,
        [
            "sections",
            str(path),
            "--out",
            str(out_dir),
            "--section",
            "verse | *lift*:0:3",
            "--graphs-profile",
            "compact",
        ],
    )

    assert result.exit_code == 0, result.output
    index = (out_dir / "section_index.md").read_text(encoding="utf-8")
    assert r"verse \| \*lift\*" in index


def test_cli_sections_rejects_unknown_yaml_keys(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    config_path = tmp_path / "sections.yaml"
    config_path.write_text(
        "sections:\n  - name: intro\n    start: 0\n    end: 3\n    colour: blue\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "unknown_section_key"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code == 2
    assert "Unknown key(s)" in result.output
    assert "colour" in result.output
    assert not out_dir.exists()


def test_cli_sections_rejects_non_utf8_yaml(tmp_path):
    path = tmp_path / "sections.wav"
    _write_sections_fixture(path)
    config_path = tmp_path / "sections.yaml"
    config_path.write_bytes(b"sections:\n  - name: \xff\n")
    out_dir = tmp_path / "non_utf8_section_config"

    result = CliRunner().invoke(
        main,
        ["sections", str(path), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code == 2
    assert "Could not read section config" in result.output
    assert not out_dir.exists()


def test_cli_analyze_without_out_uses_friendly_default(tmp_path, monkeypatch):
    path = tmp_path / "My Mix (v5).wav"
    sr = 48_000
    y = np.zeros((sr, 1), dtype=np.float32)
    y[:, 0] = 0.05
    sf.write(path, y, sr)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        main,
        ["analyze", str(path), "--graphs-profile", "compact"],
    )

    assert result.exit_code == 0, result.output
    out_dir = tmp_path / "audioatlas-report-my-mix-v5"
    assert out_dir.is_dir()
    assert (out_dir / "report.html").is_file()
    assert "No --out supplied" in result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["graphs"]["profile"] == "compact"
    assert len(summary["plots"]) == 4
