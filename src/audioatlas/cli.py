"""Command line interface for AudioAtlas.

Keep this module thin. Argument parsing only. All work is done in
``audioatlas.pipeline.analyze_file``.
"""

from __future__ import annotations

import re
from pathlib import Path

import click
import yaml

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

    index_lines = [
        "# AudioAtlas section reports",
        "",
        f"Input: `{input_path.name}`",
        "",
        "These are manually supplied sections, not automatically detected song sections.",
        "",
        "| Section | Source range | Report | HTML |",
        "|---|---:|---|---|",
    ]
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

        end_label = "EOF" if end_seconds is None else f"{end_seconds:g}s"
        index_lines.append(
            f"| {name} | {start_seconds:g}s-{end_label} | "
            f"[{result.report_path.name}]({section_dir.name}/{result.report_path.name}) | "
            f"[{result.html_report_path.name}]({section_dir.name}/{result.html_report_path.name}) |"
        )
        click.echo(f"Section report written to: {result.out_dir}")

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
