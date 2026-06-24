"""Command line interface for AudioAtlas.

Keep this module thin. Argument parsing only. All work is done in
``audioatlas.pipeline.analyze_file``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import click
import yaml

from audioatlas import __version__
from audioatlas.batch import analyze_folder
from audioatlas.config import AnalysisConfig
from audioatlas.pipeline import AnalysisRunResult, analyze_file
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
@click.option(
    "--start", "start_seconds", type=float, default=None,
    help="Optional source start time in seconds for a manual section report.",
)
@click.option(
    "--end", "end_seconds", type=float, default=None,
    help="Optional source end time in seconds for a manual section report.",
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
    start_seconds: float | None,
    end_seconds: float | None,
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
    try:
        result = analyze_file(
            input_path,
            out_dir,
            config=cfg,
            max_duration_seconds=max_duration,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            theme_name=selected_theme,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
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
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="Output directory that will receive one report folder per section.",
)
@click.option(
    "--section",
    "section_specs",
    multiple=True,
    help=(
        "Manual section as name:start:end in seconds, for example verse:30:62. "
        "Repeat for multiple sections. Leave end blank for EOF."
    ),
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML file with a top-level sections list (name, start, optional end).",
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
def sections(
    input_path: Path,
    out_dir: Path,
    section_specs: tuple[str, ...],
    config_path: Path | None,
    n_fft: int,
    hop_length: int,
    rms_frame_length: int | None,
    db_floor: float,
    true_peak_oversample: int,
    theme: str | None,
) -> None:
    """Analyze manually supplied sections from one audio file.

    AudioAtlas does not detect song sections here. It runs the same report
    pipeline on explicit source ranges supplied by the user.
    """

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    selected_theme = _validate_theme_for_cli(theme)
    parsed_sections = _collect_section_definitions(section_specs, config_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    section_results: list[tuple[str, float, float | None, AnalysisRunResult]] = []
    for name, start_seconds, end_seconds in parsed_sections:
        section_dir = out_dir / _section_slug(name, start_seconds, end_seconds)
        try:
            result = analyze_file(
                input_path,
                section_dir,
                config=cfg,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                theme_name=selected_theme,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

        section_results.append((name, start_seconds, end_seconds, result))
        click.echo(f"Section report written to: {result.out_dir}")

    # Build enhanced index with comparison table using existing summary data
    index_lines: list[str] = [
        "# AudioAtlas section reports",
        "",
        f"Input: `{input_path.name}`",
        "",
        "These are manually supplied sections, not automatically detected song sections.",
        "",
    ]
    index_lines.extend(_build_section_comparison_table(section_results))

    index_path = out_dir / "section_index.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    click.echo(f"Section index: {index_path}")


@main.command()
def themes() -> None:
    """List built-in static report themes."""

    click.echo(theme_listing_text())


def _validate_theme_for_cli(theme: str | None) -> str:
    try:
        return validate_theme_name(theme)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--theme") from exc


def _collect_section_definitions(
    section_specs: tuple[str, ...],
    config_path: Path | None,
) -> list[tuple[str, float, float | None]]:
    if not section_specs and config_path is None:
        raise click.UsageError("Provide at least one --section or --config.")

    parsed: list[tuple[str, float, float | None]] = []
    for spec in section_specs:
        parsed.append(_parse_section_spec(spec))
    if config_path is not None:
        parsed.extend(_parse_sections_from_yaml(config_path))
    return parsed


def _normalize_section(
    name: str,
    start: float,
    end: float | None,
) -> tuple[str, float, float | None]:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise click.BadParameter("Section name cannot be blank")
    if start < 0:
        raise click.BadParameter("Section start time must be non-negative")
    if end is not None and end <= start:
        raise click.BadParameter("Section end time must be greater than start time")
    return cleaned_name, start, end


def _parse_section_spec(spec: str) -> tuple[str, float, float | None]:
    parts = spec.split(":")
    if len(parts) != 3:
        raise click.BadParameter(
            f"Invalid section spec {spec!r}. Expected name:start:end, for example verse:30:62."
        )
    name, start_text, end_text = (part.strip() for part in parts)
    try:
        start = float(start_text)
    except ValueError as exc:
        raise click.BadParameter(f"Invalid section start time in {spec!r}") from exc
    if end_text == "":
        end = None
    else:
        try:
            end = float(end_text)
        except ValueError as exc:
            raise click.BadParameter(f"Invalid section end time in {spec!r}") from exc
    return _normalize_section(name, start, end)


def _parse_sections_from_yaml(path: Path) -> list[tuple[str, float, float | None]]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise click.BadParameter(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise click.BadParameter(
            f"Section config {path} must be a YAML mapping with a sections list."
        )

    sections = loaded.get("sections")
    if not isinstance(sections, list) or not sections:
        raise click.BadParameter(f"Section config {path} must contain a non-empty sections list.")

    parsed: list[tuple[str, float, float | None]] = []
    for index, entry in enumerate(sections, start=1):
        if not isinstance(entry, dict):
            raise click.BadParameter(f"Section entry {index} in {path} must be a mapping.")
        name = entry.get("name")
        start = entry.get("start")
        end = entry.get("end") if "end" in entry else None
        if not isinstance(name, str):
            raise click.BadParameter(f"Section entry {index} in {path} must have a string name.")
        if not isinstance(start, (int, float)) or isinstance(start, bool):
            raise click.BadParameter(f"Section entry {index} in {path} must have a numeric start.")
        if end is not None and (not isinstance(end, (int, float)) or isinstance(end, bool)):
            raise click.BadParameter(
                f"Section entry {index} in {path} must have a numeric end or omit it."
            )
        parsed.append(_normalize_section(name, float(start), float(end) if end is not None else None))
    return parsed


def _section_slug(name: str, start_seconds: float, end_seconds: float | None) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip()).strip("_") or "section"
    start = f"{start_seconds:07.3f}".replace(".", "p")
    end = "EOF" if end_seconds is None else f"{end_seconds:07.3f}".replace(".", "p")
    return f"{start}_{end}_{safe_name}"


def _fmt(v: Any, ndigits: int = 2) -> str:
    if v is None or isinstance(v, bool):
        return "n/a"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if ndigits == 0:
        return str(int(round(fv)))
    return f"{fv:.{ndigits}f}"


def _build_section_comparison_table(
    sections: list[tuple[str, float, float | None, AnalysisRunResult]],
) -> list[str]:
    if not sections:
        return []
    lines: list[str] = []
    lines.append("## Section comparison (manual sections only)")
    lines.append("")
    lines.append(
        "| Section | Source range | Duration (s) | Integrated LUFS | PLR (dB) | "
        "Sample peak (dBFS) | True peak (dBTP) | RMS (dBFS) | Median stereo corr. | "
        "Median side/mid (dB) | Median 95% rolloff (Hz) | Median onset | Report | HTML |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    )
    for name, start_seconds, end_seconds, result in sections:
        summ = result.summary or {}
        levels = summ.get("levels") or {}
        stereo = summ.get("stereo_correlation") or {}
        mid_side = summ.get("mid_side_energy") or {}
        spectral = summ.get("spectral_shape") or {}
        onset = summ.get("onset_density") or {}

        dur = levels.get("duration_seconds")
        lufs = levels.get("integrated_lufs")
        plr = levels.get("plr_db")
        spk = levels.get("sample_peak_dbfs")
        tpk = levels.get("true_peak_dbtp")
        rms = levels.get("rms_dbfs")
        corr = stereo.get("correlation_median")
        sm = mid_side.get("side_to_mid_ratio_db_median")
        roll = spectral.get("rolloff_95_median_hz")
        ons = onset.get("onset_density_median")

        end_label = "EOF" if end_seconds is None else f"{end_seconds:g}s"
        src = f"{start_seconds:g}s-{end_label}"

        slug = _section_slug(name, start_seconds, end_seconds)
        report_link = f"[{result.report_path.name}]({slug}/{result.report_path.name})"
        html_link = f"[{result.html_report_path.name}]({slug}/{result.html_report_path.name})"

        row = (
            f"| {name} | {src} | {_fmt(dur, 1)} | {_fmt(lufs, 1)} | {_fmt(plr, 1)} | "
            f"{_fmt(spk, 1)} | {_fmt(tpk, 1)} | {_fmt(rms, 1)} | {_fmt(corr, 2)} | "
            f"{_fmt(sm, 1)} | {_fmt(roll, 0)} | {_fmt(ons, 3)} | {report_link} | {html_link} |"
        )
        lines.append(row)
    return lines


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
