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

from audioatlas.analysis.levels import compute_rms_envelope, compute_scalar_levels
from audioatlas.analysis.spectral import compute_average_spectrum, compute_log_spectrogram
from audioatlas.analysis.stereo import compute_mid_side_energy, compute_stereo_correlation
from audioatlas.config import AnalysisConfig
from audioatlas.io import load_audio
from audioatlas.report import write_report_md, write_summary_json
from audioatlas.visualize.histogram import plot_sample_histogram
from audioatlas.visualize.spectrogram import plot_log_spectrogram
from audioatlas.visualize.spectrum import plot_average_spectrum
from audioatlas.visualize.stereo import plot_mid_side_energy, plot_stereo_correlation
from audioatlas.visualize.waveform import plot_rms_timeline, plot_waveform_rms


@dataclass(frozen=True)
class AnalysisRunResult:
    """Paths and in-memory summary produced by an analysis run.

    The ``summary`` dict mirrors what is written to ``summary.json`` so
    downstream agentic workflows can chain runs without re-reading from disk.
    """

    out_dir: Path
    summary_path: Path
    report_path: Path
    plot_paths: list[Path]
    summary: dict[str, Any]


def analyze_file(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    config: AnalysisConfig | None = None,
    max_duration_seconds: float | None = None,
) -> AnalysisRunResult:
    """Run the v0.1 analysis pipeline for one file."""

    cfg = config or AnalysisConfig()
    cfg.validate()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    audio = load_audio(input_path, max_duration_seconds=max_duration_seconds)

    levels = compute_scalar_levels(audio.y, audio.sr, cfg)
    rms = compute_rms_envelope(audio.y, audio.sr, cfg)
    spec = compute_log_spectrogram(audio.y, audio.sr, cfg)
    avg = compute_average_spectrum(audio.y, audio.sr, cfg)
    stereo = compute_stereo_correlation(audio.y, audio.sr, cfg)
    mid_side = compute_mid_side_energy(audio.y, audio.sr, cfg)

    plot_paths: list[Path] = []
    plot_paths.append(plot_waveform_rms(audio.y, audio.sr, rms, out / "01_waveform_rms.png", cfg))
    plot_paths.append(plot_rms_timeline(rms, out / "02_rms_timeline.png", cfg))
    plot_paths.append(plot_log_spectrogram(spec, out / "03_log_spectrogram.png"))
    plot_paths.append(plot_average_spectrum(avg, out / "04_average_spectrum.png", cfg))
    plot_paths.append(plot_sample_histogram(audio.y, out / "05_sample_histogram.png", cfg))
    plot_paths.append(plot_stereo_correlation(stereo, out / "06_stereo_correlation.png"))
    plot_paths.append(plot_mid_side_energy(mid_side, out / "07_mid_side_energy.png", cfg))

    summary: dict[str, Any] = {
        "schema_version": "0.1.0",
        "metadata": audio.metadata.to_dict(),
        "analysis_config": asdict(cfg),
        "levels": levels.to_dict(),
        "rms_envelope": rms.to_summary_dict(),
        "average_spectrum": avg.to_summary_dict(),
        "stereo_correlation": stereo.to_summary_dict(),
        "mid_side_energy": mid_side.to_summary_dict(),
        "plots": [p.name for p in plot_paths],
    }

    summary_path = write_summary_json(summary, out)
    report_path = write_report_md(summary, [p.name for p in plot_paths], out)

    return AnalysisRunResult(
        out_dir=out,
        summary_path=summary_path,
        report_path=report_path,
        plot_paths=plot_paths,
        summary=summary,
    )
