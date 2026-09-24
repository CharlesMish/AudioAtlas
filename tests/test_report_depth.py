"""Report-depth contracts at the CLI boundary and unchanged numerical pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import click
import numpy as np
import pytest
import soundfile as sf
from click.testing import CliRunner

from audioatlas import batch, cli, pipeline
from audioatlas.graphs import GraphSelection, all_graphs


@pytest.fixture
def inputs(tmp_path):
    folder = tmp_path / "inputs"
    folder.mkdir()
    path = folder / "one.wav"
    sr = 24000
    t = np.arange(sr * 2, dtype=float) / sr
    sf.write(path, np.column_stack((0.3 * np.sin(2 * np.pi * 330 * t),
                                  0.2 * np.sin(2 * np.pi * 660 * t))), sr)
    return folder, path


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def fake(input_path, out_dir, **kwargs):
        # The entire plan must be visible before the first pipeline call.
        click.echo("PIPELINE START")
        calls.append(kwargs)
        out_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(out_dir=out_dir, summary={}, findings={},
                               summary_path=out_dir / "summary.json",
                               report_path=out_dir / "report.md",
                               html_report_path=out_dir / "report.html")

    monkeypatch.setattr(pipeline, "analyze_file", fake)
    monkeypatch.setattr(batch, "analyze_file", fake)
    return calls


def invoke(command, inputs, out, flags):
    folder, path = inputs
    args = [command, str(folder if command == "batch" else path), "--out", str(out)]
    if command == "sections":
        args += ["--section", "first:0:1", "--section", "second:1:2"]
    return CliRunner().invoke(cli.main, [*args, *flags])


@pytest.mark.parametrize("command", ["analyze", "batch", "sections"])
@pytest.mark.parametrize("depth,mode,profile,count", [
    ("overview", "compact", "compact", 4),
    ("standard", "full", "standard", 14),
    ("detailed", "full", "full", 18),
    (None, "full", "standard", 14),
])
def test_presets_and_default_propagate(command, depth, mode, profile, count,
                                      inputs, tmp_path, captured):
    result = invoke(command, inputs, tmp_path / "out",
                    ["--report-depth", depth] if depth else [])
    assert result.exit_code == 0, result.output
    assert len(captured) == (2 if command == "sections" else 1)
    for kwargs in captured:
        assert kwargs["analysis_mode"] == mode
        assert kwargs["selection"] == GraphSelection(profile=profile)
    assert f"Report depth: {(depth or 'standard').title()}" in result.output
    assert f"Analysis breadth: {mode.title()}" in result.output
    assert f"Plots: {count} per report" in result.output
    assert result.output.index("Additional restored analyses: none") < result.output.index("PIPELINE START")


@pytest.mark.parametrize("flags,mode,profile,depth", [
    (["--analysis-mode", "compact"], "compact", "compact", "Overview"),
    (["--analysis-mode", "full"], "full", "standard", "Standard"),
    (["--graphs-profile", "minimal"], "full", "minimal", "Custom"),
    (["--graphs-profile", "compact"], "full", "compact", "Custom"),
    (["--graphs-profile", "standard"], "full", "standard", "Standard"),
    (["--graphs-profile", "full"], "full", "full", "Detailed"),
])
def test_legacy_axes_unchanged(flags, mode, profile, depth, inputs, tmp_path, captured):
    result = invoke("analyze", inputs, tmp_path / "out", flags)
    assert result.exit_code == 0, result.output
    assert captured[0]["analysis_mode"] == mode
    assert captured[0]["selection"].profile == profile
    assert f"Report depth: {depth}" in result.output


@pytest.mark.parametrize("command", ["analyze", "batch", "sections"])
@pytest.mark.parametrize("flags", [
    ["--report-depth", "unknown"],
    ["--report-depth", "overview", "--analysis-mode", "full"],
    ["--report-depth", "standard", "--analysis-mode", "compact"],
    ["--report-depth", "overview", "--graphs-profile", "standard"],
    ["--report-depth", "overview", "--enable", "chroma_cqt"],
    ["--report-depth", "detailed", "--disable", "chroma_cqt"],
    ["--report-depth", "overview", "--enable", "unknown"],
    ["--analysis-mode", "unknown"],
    ["--graphs-profile", "unknown"],
])
def test_invalid_or_conflicting_controls_fail_before_output(command, flags, inputs,
                                                           tmp_path, captured):
    out = tmp_path / "out"
    result = invoke(command, inputs, out, flags)
    assert result.exit_code != 0
    assert not out.exists()
    assert not captured
    if "conflicts" in result.output:
        assert "Remove --report-depth" in result.output


def test_matching_axes_alias_and_noop_changes_are_canonicalized(inputs, tmp_path, captured):
    config = tmp_path / "graphs.yaml"
    config.write_text("graphs:\n  profile: minimal\n  enable: [waveform_rms]\n")
    result = invoke("analyze", inputs, tmp_path / "out", [
        "--report-depth", "overview", "--analysis-mode", "compact", "--graphs-profile", "minimal",
        "--graphs-config", str(config), "--disable", "chroma_cqt",
    ])
    assert result.exit_code == 0, result.output
    assert captured[0]["selection"] == GraphSelection(profile="compact")


@pytest.mark.parametrize("depth", [None, "overview"])
def test_yaml_profile_masking_is_legacy_only(depth, inputs, tmp_path, captured):
    config = tmp_path / "graphs.yaml"
    config.write_text("graphs:\n  profile: standard\n")
    flags = ["--analysis-mode", "compact", "--graphs-profile", "compact", "--graphs-config", str(config)]
    if depth:
        flags += ["--report-depth", depth]
    result = invoke("analyze", inputs, tmp_path / "out", flags)
    if depth:
        assert result.exit_code != 0
        assert "graphs.profile in YAML=standard" in result.output
        assert not captured
        assert not (tmp_path / "out").exists()
    else:
        assert result.exit_code == 0, result.output
        assert captured[0]["selection"].profile == "compact"


@pytest.mark.parametrize("use_yaml", [False, True])
def test_legacy_restored_families_visible_before_analysis(use_yaml, inputs, tmp_path, captured):
    flags = ["--analysis-mode", "compact"]
    if use_yaml:
        config = tmp_path / "graphs.yaml"
        config.write_text("graphs:\n  enable: [chroma_cqt, short_term_lufs]\n")
        flags += ["--graphs-config", str(config)]
    else:
        flags += ["--enable", "chroma_cqt,short_term_lufs"]
    result = invoke("analyze", inputs, tmp_path / "out", flags)
    assert result.exit_code == 0, result.output
    assert "Report depth: Custom" in result.output
    assert "Plots: 6 per report" in result.output
    assert result.output.index("Additional restored analyses: short_term, chroma") < result.output.index("PIPELINE START")
    assert len(captured[0]["selection"].resolve(all_graphs())) == 6


def test_legacy_compact_standard_restores_all_optional_families(inputs, tmp_path, captured):
    result = invoke("analyze", inputs, tmp_path / "out",
                    ["--analysis-mode", "compact", "--graphs-profile", "standard"])
    assert result.exit_code == 0, result.output
    assert "Additional restored analyses: crest, short_term, average_spectrum, band_power, onset, chroma" in result.output


@pytest.mark.parametrize("depth,mode,profile", [
    ("overview", "compact", "compact"),
    ("standard", "full", "standard"),
    ("detailed", "full", "full"),
])
def test_presets_retain_exact_real_outputs(depth, mode, profile, inputs, tmp_path):
    """Run the actual pipeline through both CLI paths; compare every saved value."""
    outputs = []
    for name, flags in [
        ("preset", ["--report-depth", depth]),
        ("legacy", ["--analysis-mode", mode, "--graphs-profile", profile]),
    ]:
        out = tmp_path / name
        result = invoke("analyze", inputs, out, flags)
        assert result.exit_code == 0, result.output
        outputs.append(out)
    for filename in ("summary.json", "findings.json"):
        assert json.loads((outputs[0] / filename).read_text()) == json.loads((outputs[1] / filename).read_text())
    for plot in outputs[0].glob("*.png"):
        assert plot.read_bytes() == (outputs[1] / plot.name).read_bytes(), plot.name


def test_documented_depth_contract():
    guide = (Path(__file__).parents[1] / "docs/USER_GUIDE.md").read_text()
    assert "Key current measurements, all current finding checks, 4 plots" in guide
    assert "All measurements, 14 plots; default" in guide
    assert "All measurements, 18 plots" in guide
    assert "report-depth persistence needs a" in guide
