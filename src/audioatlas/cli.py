"""Command line interface for AudioAtlas.

Keep this module thin. Argument parsing only. All work is done in
``audioatlas.pipeline.analyze_file``.
"""

from __future__ import annotations

from pathlib import Path

import click

from audioatlas import __version__
from audioatlas.batch import analyze_folder
from audioatlas.config import AnalysisConfig
from audioatlas.pipeline import analyze_file
from audioatlas.theme import theme_listing_text, validate_theme_name


@click.group()
@click.version_option(__version__, prog_name="audioatlas")
def main() -> None:
    """AudioAtlas: factual single-track audio maps."""


@main.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out", "out_dir",
    type=click.Path(file_okay=False, path_type=Path), required=True,
    help="Output directory for the report.",
)
@click.option(
    "--max-duration", type=float, default=None,
    help="Optional seconds to analyze for quick dev runs.",
)
@click.option("--n-fft", type=int, default=4096, show_default=True)
@click.option("--hop-length", type=int, default=1024, show_default=True)
@click.option(
    "--rms-frame-length", type=int, default=None,
    help="Frame length for the RMS envelope. Defaults to --n-fft.",
)
@click.option(
    "--db-floor", type=float, default=-100.0, show_default=True,
    help="Floor (in dB) used to clamp dBFS-style metrics and plots.",
)
@click.option(
    "--true-peak-oversample", type=int, default=4, show_default=True,
    help="Polyphase oversample factor for the true-peak approximation. "
         "Set to 1 to disable oversampling and use sample peak.",
)
@click.option("--theme", default=None, help="Built-in report theme ID. Run `audioatlas themes`.")
def analyze(
    input_path: Path,
    out_dir: Path,
    max_duration: float | None,
    n_fft: int,
    hop_length: int,
    rms_frame_length: int | None,
    db_floor: float,
    true_peak_oversample: int,
    theme: str | None,
) -> None:
    """Analyze one audio file and write a report folder."""

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    selected_theme = _validate_theme_for_cli(theme)
    result = analyze_file(
        input_path,
        out_dir,
        config=cfg,
        max_duration_seconds=max_duration,
        theme_name=selected_theme,
    )
    click.echo(f"AudioAtlas report written to: {result.out_dir}")
    click.echo(f"Summary: {result.summary_path}")
    click.echo(f"Report:  {result.report_path}")
    click.echo(f"HTML:    {result.html_report_path}")


@main.command()
@click.argument("input_folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--out", "out_dir",
    type=click.Path(file_okay=False, path_type=Path), required=True,
    help="Output directory for the catalog report.",
)
@click.option(
    "--max-duration", type=float, default=None,
    help="Optional seconds to analyze for quick dev runs.",
)
@click.option("--n-fft", type=int, default=4096, show_default=True)
@click.option("--hop-length", type=int, default=1024, show_default=True)
@click.option(
    "--rms-frame-length",
    type=int,
    default=None,
    help="Frame length for the RMS envelope. Defaults to --n-fft.",
)
@click.option(
    "--db-floor",
    type=float,
    default=-100.0,
    show_default=True,
    help="Floor (in dB) used to clamp dBFS-style metrics and plots.",
)
@click.option(
    "--true-peak-oversample",
    type=int,
    default=4,
    show_default=True,
    help="Polyphase oversample factor for the true-peak approximation. "
    "Set to 1 to disable oversampling and use sample peak.",
)
@click.option("--theme", default=None, help="Built-in report theme ID. Run `audioatlas themes`.")
def batch(
    input_folder: Path,
    out_dir: Path,
    max_duration: float | None,
    n_fft: int,
    hop_length: int,
    rms_frame_length: int | None,
    db_floor: float,
    true_peak_oversample: int,
    theme: str | None,
) -> None:
    """Analyze a folder of audio files and write a neutral catalog."""

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    selected_theme = _validate_theme_for_cli(theme)
    result = analyze_folder(
        input_folder,
        out_dir,
        config=cfg,
        max_duration_seconds=max_duration,
        theme_name=selected_theme,
    )
    click.echo(f"AudioAtlas catalog written to: {result.out_dir}")
    click.echo(f"Catalog summary: {result.catalog_summary_path}")
    click.echo(f"Catalog report:  {result.catalog_md_path}")
    click.echo(f"Catalog HTML:    {result.catalog_html_path}")


@main.command()
def themes() -> None:
    """List built-in static report themes."""

    click.echo(theme_listing_text())


def _validate_theme_for_cli(theme: str | None) -> str:
    try:
        return validate_theme_name(theme)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--theme") from exc


def _make_config(
    n_fft: int,
    hop_length: int,
    rms_frame_length: int | None,
    db_floor: float,
    true_peak_oversample: int,
) -> AnalysisConfig:
    return AnalysisConfig(
        n_fft=n_fft,
        hop_length=hop_length,
        rms_frame_length=rms_frame_length if rms_frame_length is not None else n_fft,
        db_floor=db_floor,
        true_peak_oversample=true_peak_oversample,
    )


if __name__ == "__main__":
    main()
