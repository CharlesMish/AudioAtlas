"""Regression checks for computation coverage, independent of report formatting."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from click.testing import CliRunner

from audioatlas import batch, cli, pipeline
from audioatlas.analysis.bundle import _COMPUTE
from audioatlas.graphs.selection import GraphSelection
from audioatlas.output import write_output_manifest

# Keep these expectations independent of the execution-policy implementation.
CORE_SUMMARIES = {
    "levels",
    "rms_envelope",
    "peak_timeline",
    "stereo_correlation",
    "mid_side_energy",
    "spectral_shape",
}
OMITTED = {
    "lr_balance": "lr_balance",
    "crest": "crest_factor_timeline",
    "short_term": "short_term_lufs",
    "average_spectrum": "average_spectrum",
    "band_power": "band_energy_timeline",
    "onset": "onset_density",
    "chroma": "chroma_cqt",
}
MINIMAL_GRAPHS = ["waveform_rms", "rms_timeline", "log_spectrogram", "sample_histogram"]
HISTOGRAM_ONLY = GraphSelection(
    profile="minimal", disable=("waveform_rms", "rms_timeline", "log_spectrogram")
)


def _write_audio(path: Path, kind: str = "asymmetric") -> Path:
    sr = 48_000
    duration = 0.025 if kind == "short" else 1.5
    t = np.arange(round(sr * duration), dtype=np.float64) / sr
    left = 0.32 * np.sin(2 * np.pi * 233 * t)
    if kind == "asymmetric":
        right = 0.11 * np.sin(2 * np.pi * 467 * t + 0.7)
        y = np.column_stack((left, right))
        y[: sr // 5] = 0  # Silence creates undefined correlation frames.
        y[sr // 2 : sr // 2 + 256, 0] = 1.0  # One-sided clipped transient.
        y[sr : sr + 96, 1] = -1.0
    elif kind == "silent":
        y = np.zeros((len(t), 2))
    else:
        y = left[:, None]
    sf.write(path, y, sr, subtype="FLOAT")
    return path


def _fake_run(out_dir: Path) -> SimpleNamespace:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.html").write_text("fixture", encoding="utf-8")
    write_output_manifest(out_dir, kind="single-track-report", generated_files=["report.html"])
    return SimpleNamespace(
        out_dir=out_dir,
        summary_path=out_dir / "summary.json",
        report_path=out_dir / "report.md",
        html_report_path=out_dir / "report.html",
        summary={},
        findings={},
    )


def test_compact_default_really_skips_seven_analyses(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("An analysis omitted by compact mode was executed")

    for name in OMITTED:
        monkeypatch.setitem(_COMPUTE, name, forbidden)
    result = pipeline.analyze_file(
        _write_audio(tmp_path / "asymmetric.wav"), tmp_path / "compact", analysis_mode="compact"
    )

    assert result.summary["schema_version"] == "0.4.0"
    assert result.summary["graphs"]["profile"] == "compact"
    assert result.summary["graphs"]["selected"] == MINIMAL_GRAPHS
    assert {path.name for path in result.plot_paths} == {f"{name}.png" for name in MINIMAL_GRAPHS}
    assert all(path.is_file() for path in result.plot_paths)
    assert result.summary.keys() >= CORE_SUMMARIES
    assert not set(OMITTED.values()) & result.summary.keys()
    coverage = result.summary["analysis_execution"]
    assert coverage["mode"] == "compact"
    assert set(coverage["computed"]) == {
        "levels", "rms", "peaks", "stereo", "mid_side", "spectral_shape", "spectrogram"
    }
    assert set(coverage["skipped"]) == set(OMITTED)
    assert set(coverage["summary_blocks"]) == CORE_SUMMARIES
    assert coverage["findings_coverage"] == "complete"
    assert "findings_scope" not in coverage
    assert result.findings["analysis_execution"] == coverage
    saved = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert saved["analysis_execution"] == coverage
    assert "band_power_timeline" not in saved
    assert saved["analysis_provenance"]["summary_schema_version"] == saved["schema_version"]


def test_selected_extensions_restore_dependencies_once(tmp_path, monkeypatch):
    calls = Counter()
    for name, compute in tuple(_COMPUTE.items()):
        def counted(*args, _name=name, _compute=compute, **kwargs):
            calls[_name] += 1
            return _compute(*args, **kwargs)

        monkeypatch.setitem(_COMPUTE, name, counted)

    result = pipeline.analyze_file(
        _write_audio(tmp_path / "extensions.wav"),
        tmp_path / "extended",
        analysis_mode="compact",
        selection=GraphSelection(
            profile="minimal",
            enable=("chroma_cqt", "short_term_lufs", "peak_vs_rms", "chroma_cqt"),
        ),
    )

    assert {"chroma_cqt", "short_term_lufs", "peak_vs_rms"} <= set(
        result.summary["graphs"]["selected"]
    )
    assert {"chroma_cqt", "short_term_lufs"} <= result.summary.keys()
    assert calls["chroma"] == calls["short_term"] == calls["peaks"] == calls["rms"] == 1
    assert all(count == 1 for count in calls.values())
    assert set(calls) == set(result.summary["analysis_execution"]["computed"])
    assert set(result.summary["analysis_execution"]["skipped"]) == {
        "crest", "average_spectrum", "band_power", "onset", "lr_balance"
    }


@pytest.mark.parametrize("kind", ["asymmetric", "mono", "short", "silent"])
def test_compact_retains_exact_measurements_and_findings(tmp_path, kind):
    path = _write_audio(tmp_path / f"{kind}.wav", kind)
    # One cheap graph isolates computation parity from redundant rendering work.
    full = pipeline.analyze_file(path, tmp_path / "full", selection=HISTOGRAM_ONLY)
    compact = pipeline.analyze_file(
        path, tmp_path / "compact", selection=HISTOGRAM_ONLY, analysis_mode="compact"
    )

    assert full.summary["schema_version"] == "0.4.0"
    assert set(OMITTED.values()) <= full.summary.keys()
    for key in CORE_SUMMARIES | {"metadata", "analysis_config"}:
        assert compact.summary[key] == full.summary[key], key
    full_findings = {key: value for key, value in full.findings.items() if key != "analysis_execution"}
    compact_findings = {
        key: value for key, value in compact.findings.items() if key != "analysis_execution"
    }
    assert compact_findings == full_findings
    if kind == "asymmetric":
        assert full.summary["levels"]["clipped_samples"] > 0
        assert full.findings["count"] > 0
    assert set(compact.summary["analysis_execution"]["skipped"]) == set(OMITTED) | {"spectrogram"}
    assert full.summary["analysis_execution"]["mode"] == "full"
    for signature in ("measurement_code_sha256", "finding_rule_code_sha256",
                      "analysis_config_sha256", "compatible_analysis_sha256", "exact_environment_sha256"):
        assert compact.summary["analysis_provenance"][signature] == full.summary["analysis_provenance"][signature]


def test_cli_compact_propagates_to_analyze_batch_and_each_section(tmp_path, monkeypatch):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    path = _write_audio(inputs / "one.wav", "mono")
    _write_audio(inputs / "two.wav", "mono")
    calls = []

    def capture(input_path, out_dir, **kwargs):
        calls.append((input_path, out_dir, kwargs))
        return _fake_run(out_dir)

    monkeypatch.setattr(pipeline, "analyze_file", capture)
    monkeypatch.setattr(batch, "analyze_file", capture)
    commands = [
        ["analyze", str(path)],
        ["batch", str(inputs)],
        ["sections", str(path), "--section", "opening:0:0.5", "--section", "rest:0.5:1.5"],
    ]
    for args in commands:
        result = CliRunner().invoke(
            cli.main, [*args, "--out", str(tmp_path / args[0]), "--analysis-mode", "compact"]
        )
        assert result.exit_code == 0, result.output
    assert len(calls) == 5
    assert all(kwargs["analysis_mode"] == "compact" for _, _, kwargs in calls)
    assert all(kwargs["selection"].profile == "compact" for _, _, kwargs in calls)
    assert [kwargs["start_seconds"] for _, _, kwargs in calls[-2:]] == [0.0, 0.5]
    assert [kwargs["end_seconds"] for _, _, kwargs in calls[-2:]] == [0.5, 1.5]


def test_cli_explicit_and_yaml_graph_choices_override_compact_default(tmp_path, monkeypatch):
    path = _write_audio(tmp_path / "one.wav", "mono")
    config = tmp_path / "graphs.yaml"
    config.write_text(
        "graphs:\n  profile: full\n  enable: [chroma_cqt]\n  disable: [sample_histogram]\n",
        encoding="utf-8",
    )
    selections = []

    def capture(input_path, out_dir, **kwargs):
        assert kwargs["analysis_mode"] == "compact"
        selections.append(kwargs["selection"])
        return _fake_run(out_dir)

    monkeypatch.setattr(pipeline, "analyze_file", capture)
    for overrides in ([], ["--graphs-profile", "standard"]):
        result = CliRunner().invoke(
            cli.main,
            [
                "analyze", str(path), "--out", str(tmp_path / "report"),
                "--analysis-mode", "compact", "--graphs-config", str(config),
                "--enable", "peak_vs_rms", *overrides,
            ],
        )
        assert result.exit_code == 0, result.output
    assert [selection.profile for selection in selections] == ["full", "standard"]
    assert all(selection.enable == ("chroma_cqt", "peak_vs_rms") for selection in selections)
    assert all(selection.disable == ("sample_histogram",) for selection in selections)


def test_invalid_analysis_mode_fails_before_loading_or_creating_output(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid analysis mode reached input loading")

    monkeypatch.setattr(pipeline, "load_audio", forbidden)
    monkeypatch.setattr(pipeline, "compute_source_binding", forbidden)
    for analyze, source in (
        (pipeline.analyze_file, tmp_path / "missing.wav"),
        (batch.analyze_folder, tmp_path / "missing-folder"),
    ):
        out = tmp_path / analyze.__name__
        with pytest.raises(ValueError, match="Unknown analysis mode"):
            analyze(source, out, analysis_mode="compcat")
        assert not out.exists()


@pytest.mark.parametrize("graph,family,block", [
    ("crest_factor_timeline", "crest", "crest_factor_timeline"),
    ("short_term_lufs", "short_term", "short_term_lufs"),
    ("average_spectrum", "average_spectrum", "average_spectrum"),
    ("band_energy_timeline", "band_power", "band_power_timeline"),
    ("onset_density", "onset", "onset_density"),
    ("chroma_cqt", "chroma", "chroma_cqt"),
    ("lr_balance", "lr_balance", "lr_balance"),
])
def test_each_optional_graph_restores_exact_family_once(tmp_path, monkeypatch, graph, family, block):
    calls = Counter()
    for name, compute in tuple(_COMPUTE.items()):
        def counted(*args, _name=name, _compute=compute, **kwargs):
            calls[_name] += 1
            return _compute(*args, **kwargs)
        monkeypatch.setitem(_COMPUTE, name, counted)
    result = pipeline.analyze_file(
        _write_audio(tmp_path / "restore.wav"), tmp_path / "report",
        analysis_mode="compact", selection=GraphSelection(profile="compact", enable=(graph,)),
    )
    assert block in result.summary
    assert calls[family] == 1
    assert set(calls) == set(result.summary["analysis_execution"]["computed"])
    assert all(count == 1 for count in calls.values())
    assert set(OMITTED) - {family} <= set(result.summary["analysis_execution"]["skipped"])
    if family == "band_power":
        assert result.summary["band_energy_timeline"] == result.summary[block]


def test_compact_standard_restores_graph_dependencies_and_preserves_owned_output(tmp_path):
    path = _write_audio(tmp_path / "source.wav")
    output = tmp_path / "report"
    full = pipeline.analyze_file(path, output)
    (output / "listener-notes.txt").write_text("keep my notes", encoding="utf-8")
    extended = pipeline.analyze_file(path, tmp_path / "extended", analysis_mode="compact",
                                     selection=GraphSelection(profile="standard"))
    assert extended.summary["analysis_execution"]["skipped"] == ["lr_balance"]
    for key in set(full.summary) - {"schema_version", "analysis_provenance", "analysis_execution", "lr_balance"}:
        assert extended.summary[key] == full.summary[key], key
    compact = pipeline.analyze_file(path, output, analysis_mode="compact")
    assert {p.name for p in output.glob("*.png")} == {p.name for p in compact.plot_paths}
    assert (output / "listener-notes.txt").read_text() == "keep my notes"
    full_again = pipeline.analyze_file(path, output)
    assert full_again.summary == full.summary
    assert full_again.findings == full.findings
    assert "Analysis scope" not in full_again.html_report_path.read_text()


def test_cli_invalid_mode_rejected_before_output(tmp_path):
    path = tmp_path / "exists.wav"
    path.touch()
    for command, source in (("analyze", path), ("batch", tmp_path), ("sections", path)):
        out = tmp_path / f"bad-{command}"
        result = CliRunner().invoke(
            cli.main,
            [command, str(source), "--out", str(out), "--analysis-mode", "compcat"],
        )
        assert result.exit_code != 0
        assert "compcat" in result.output
        assert not out.exists()


@pytest.mark.parametrize("mode,profile,expected", [
    (None, None, "standard"), ("full", "compact", "compact"),
    (None, "minimal", "minimal"), ("compact", None, "compact"),
    ("compact", "full", "full"), ("full", "standard", "standard"),
])
def test_cli_mode_profile_orthogonality(tmp_path, monkeypatch, mode, profile, expected):
    path = _write_audio(tmp_path / "mono.wav", "mono")
    calls = []

    def capture(source, output, **kwargs):
        calls.append(kwargs)
        return _fake_run(output)

    monkeypatch.setattr(pipeline, "analyze_file", capture)
    args = ["analyze", str(path), "--out", str(tmp_path / "report")]
    if mode:
        args += ["--analysis-mode", mode]
    if profile:
        args += ["--graphs-profile", profile]
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 0, result.output
    assert calls[0]["analysis_mode"] == (mode or "full")
    assert calls[0]["selection"].profile == expected
