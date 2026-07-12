"""Single-file analysis and report orchestration.

Analysis functions own measurements, graph specifications own rendering, and
this module coordinates one coherent staged publication. It deliberately does
not contain DSP interpretation logic.
"""

from __future__ import annotations

import gc
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
from audioatlas.output import (
    ALL_GENERATED_FILENAMES,
    OUTPUT_MARKER_FILENAME,
    SINGLE_REPORT_FILENAMES,
    publish_staged_output,
    staged_output_directory,
    write_output_manifest,
)
from audioatlas.provenance import build_analysis_provenance, track_identity_block
from audioatlas.release import SUMMARY_SCHEMA_VERSION
from audioatlas.report import write_findings_json, write_report_md, write_summary_json


@dataclass(frozen=True)
class AnalysisRunResult:
    """Paths and in-memory summary produced by an analysis run.

    The ``summary`` dict mirrors what is written to ``summary.json`` so
    downstream workflows can chain runs without re-reading from disk.
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
    presentation_mode: str | None = None,
    selection: GraphSelection | None = None,
    include_local_paths: bool = False,
    track_id: str | None = None,
) -> AnalysisRunResult:
    """Analyze one file, publish its report, and release renderer cycles.

    Matplotlib closes each figure, but some renderer/artist objects participate
    in reference cycles. The inner-frame boundary makes the analysis bundle,
    audio array, and render state unreachable before collection, bounding
    memory growth across album-sized in-process batch runs.
    """

    try:
        return _analyze_file_impl(
            input_path,
            out_dir,
            config=config,
            max_duration_seconds=max_duration_seconds,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            theme_name=theme_name,
            presentation_mode=presentation_mode,
            selection=selection,
            include_local_paths=include_local_paths,
            track_id=track_id,
        )
    finally:
        gc.collect()


def _analyze_file_impl(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    config: AnalysisConfig | None = None,
    max_duration_seconds: float | None = None,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
    theme_name: str | None = None,
    presentation_mode: str | None = None,
    selection: GraphSelection | None = None,
    include_local_paths: bool = False,
    track_id: str | None = None,
) -> AnalysisRunResult:
    """Implement one analysis run inside a collectable lifecycle frame.

    Machine-local paths are excluded from report metadata unless
    ``include_local_paths`` is explicitly enabled.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    graph_selection = selection or GraphSelection()
    graph_specs = all_graphs()
    selected_graphs = graph_selection.resolve(graph_specs)
    out = Path(out_dir)

    # Complete loading and analysis before touching a previous report. A bad
    # input therefore cannot erase a known-good output folder.
    audio = load_audio(
        input_path,
        max_duration_seconds=max_duration_seconds,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        include_local_paths=include_local_paths,
    )

    bundle = AnalysisBundle(audio, cfg)
    levels = bundle.get("levels")
    rms = bundle.get("rms")
    crest = bundle.get("crest")
    short_term = bundle.get("short_term")
    peaks = bundle.get("peaks")
    avg = bundle.get("average_spectrum")
    spectral_shape = bundle.get("spectral_shape")
    band_power = bundle.get("band_power")
    onset = bundle.get("onset")
    chroma = bundle.get("chroma")
    stereo = bundle.get("stereo")
    mid_side = bundle.get("mid_side")

    selected_filenames = [graph.filename for graph in selected_graphs]
    band_power_summary = band_power.to_summary_dict()
    summary: dict[str, Any] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "metadata": audio.metadata.to_dict(),
        "source_identity": track_identity_block(track_id),
        "analysis_config": asdict(cfg),
        "analysis_provenance": build_analysis_provenance(cfg),
        "levels": levels.to_dict(),
        "rms_envelope": rms.to_summary_dict(),
        "crest_factor_timeline": crest.to_summary_dict(),
        "peak_timeline": peaks.to_summary_dict(),
        "average_spectrum": avg.to_summary_dict(),
        "spectral_shape": spectral_shape.to_summary_dict(),
        "band_power_timeline": band_power_summary,
        # Deprecated compatibility alias retained for the 0.2 alpha line.
        "band_energy_timeline": band_power_summary,
        "onset_density": onset.to_summary_dict(),
        "chroma_cqt": chroma.to_summary_dict(),
        "short_term_lufs": short_term.to_summary_dict(),
        "stereo_correlation": stereo.to_summary_dict(),
        "mid_side_energy": mid_side.to_summary_dict(),
        "plots": selected_filenames,
        "graphs": {
            "profile": graph_selection.profile,
            "selected": [graph.key for graph in selected_graphs],
            "available": [graph.key for graph in graph_specs],
            "selected_filenames": selected_filenames,
        },
    }
    findings = generate_findings(summary).to_dict()

    # A destination may legitimately be reused for any generated artifact kind.
    # Treat every predictable root artifact as AudioAtlas-owned so switching
    # among reports, catalogs, and revision diffs cannot leave a mixed folder.
    owned_names = set(ALL_GENERATED_FILENAMES)
    with staged_output_directory(out) as staging:
        for graph in selected_graphs:
            graph.render(bundle, staging / graph.filename, cfg)

        write_summary_json(summary, staging)
        write_findings_json(findings, staging)
        write_report_md(summary, selected_filenames, staging, findings)
        write_report_html(
            summary,
            selected_filenames,
            staging,
            findings,
            theme_name=theme_name,
            presentation_mode=presentation_mode,
        )
        write_output_manifest(
            staging,
            kind="single-track-report",
            generated_files=[
                *selected_filenames,
                *SINGLE_REPORT_FILENAMES,
                OUTPUT_MARKER_FILENAME,
            ],
        )
        publish_staged_output(staging, out, owned_filenames=owned_names)

    return AnalysisRunResult(
        out_dir=out,
        summary_path=out / "summary.json",
        findings_path=out / "findings.json",
        report_path=out / "report.md",
        html_report_path=out / "report.html",
        plot_paths=[out / filename for filename in selected_filenames],
        summary=summary,
        findings=findings,
    )
