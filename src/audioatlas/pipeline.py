"""Thin orchestration pipeline for v0.1.

This module is intentionally minimal. It does not contain analysis logic.
When agents add a new feature slice, the typical change to this file is:

1. Import the new analysis function and its result dataclass.
2. Call it once with the loaded audio.
3. Add its plot path to ``plot_paths``.
4. Add its summary entry to the ``summary`` dict.

See ``docs/ARCHITECTURE.md`` and ``AGENT_BRIEF.md`` for the full slice recipe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from audioatlas.analysis.bundle import AnalysisBundle
from audioatlas.analysis.findings import generate_findings
from audioatlas.config import AnalysisConfig
from audioatlas.graphs import all_graphs
from audioatlas.graphs.selection import GraphSelection
from audioatlas.html_report import write_report_html
from audioatlas.io import load_audio
from audioatlas.report import write_findings_json, write_report_md, write_summary_json


@dataclass(frozen=True)
class AnalysisRunResult:
    """Paths and in-memory summary produced by an analysis run.

    The ``summary`` dict mirrors what is written to ``summary.json`` so
    downstream agentic workflows can chain runs without re-reading from disk.
    """

    out_dir: Path
    summary_path: Path
    findings_path: Path
    report_path: Path
    html_report_path: Path
    plot_paths: list[Path]
    summary: dict[str, Any]
    findings: dict[str, Any]


def analyze_file(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    config: AnalysisConfig | None = None,
    max_duration_seconds: float | None = None,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
    theme_name: str | None = None,
    selection: GraphSelection | None = None,
) -> AnalysisRunResult:
    """Run the v0.1 analysis pipeline for one file."""

    cfg = config or AnalysisConfig()
    cfg.validate()
    graph_selection = selection or GraphSelection()
    selected_graphs = graph_selection.resolve(all_graphs())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    audio = load_audio(
        input_path,
        max_duration_seconds=max_duration_seconds,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )

    bundle = AnalysisBundle(audio, cfg)
    levels = bundle.get("levels")
    rms = bundle.get("rms")
    crest = bundle.get("crest")
    short_term = bundle.get("short_term")
    peaks = bundle.get("peaks")
    avg = bundle.get("average_spectrum")
    spectral_shape = bundle.get("spectral_shape")
    band_energy = bundle.get("band_energy")
    onset = bundle.get("onset")
    chroma = bundle.get("chroma")
    stereo = bundle.get("stereo")
    mid_side = bundle.get("mid_side")

    plot_paths: list[Path] = []
    for graph in selected_graphs:
        plot_paths.append(graph.render(bundle, out / graph.filename, cfg))

    summary: dict[str, Any] = {
        "schema_version": "0.1.0",
        "metadata": audio.metadata.to_dict(),
        "analysis_config": asdict(cfg),
        "levels": levels.to_dict(),
        "rms_envelope": rms.to_summary_dict(),
        "crest_factor_timeline": crest.to_summary_dict(),
        "peak_timeline": peaks.to_summary_dict(),
        "average_spectrum": avg.to_summary_dict(),
        "spectral_shape": spectral_shape.to_summary_dict(),
        "band_energy_timeline": band_energy.to_summary_dict(),
        "onset_density": onset.to_summary_dict(),
        "chroma_cqt": chroma.to_summary_dict(),
        "short_term_lufs": short_term.to_summary_dict(),
        "stereo_correlation": stereo.to_summary_dict(),
        "mid_side_energy": mid_side.to_summary_dict(),
        "plots": [p.name for p in plot_paths],
        "graphs": {
            "profile": graph_selection.profile,
            "selected": [graph.key for graph in selected_graphs],
            "available": [graph.key for graph in all_graphs()],
            "selected_filenames": [graph.filename for graph in selected_graphs],
        },
    }

    findings = generate_findings(summary).to_dict()
    summary_path = write_summary_json(summary, out)
    findings_path = write_findings_json(findings, out)
    report_path = write_report_md(summary, [p.name for p in plot_paths], out, findings)
    html_report_path = write_report_html(
        summary,
        [p.name for p in plot_paths],
        out,
        findings,
        theme_name=theme_name,
    )

    return AnalysisRunResult(
        out_dir=out,
        summary_path=summary_path,
        findings_path=findings_path,
        report_path=report_path,
        html_report_path=html_report_path,
        plot_paths=plot_paths,
        summary=summary,
        findings=findings,
    )
