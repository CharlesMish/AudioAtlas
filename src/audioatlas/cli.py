"""Command line interface for AudioAtlas.

Keep this module thin. Argument parsing only. All work is done in
``audioatlas.pipeline.analyze_file``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import yaml

from audioatlas import __version__
from audioatlas.errors import AudioAtlasError
from audioatlas.graph_profiles import VALID_PROFILES

if TYPE_CHECKING:
    from audioatlas.config import AnalysisConfig
    from audioatlas.graphs.selection import GraphSelection
    from audioatlas.pipeline import AnalysisRunResult


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
@click.option(
    "--graphs-profile",
    type=click.Choice(VALID_PROFILES),
    default=None,
    help="Graph render profile. Defaults to standard unless --graphs-config sets it.",
)
@click.option(
    "--enable",
    "graph_enable",
    multiple=True,
    help="Comma-separated graph keys to add to the selected profile. May be repeated.",
)
@click.option(
    "--disable",
    "graph_disable",
    multiple=True,
    help="Comma-separated graph keys to remove from the selected profile. May be repeated.",
)
@click.option(
    "--graphs-config",
    "graphs_config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML file with an optional top-level graphs block.",
)
@click.option(
    "--include-local-paths",
    is_flag=True,
    help="Include resolved machine-local paths in JSON metadata (off by default for sharing).",
)
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
    graphs_profile: str | None,
    graph_enable: tuple[str, ...],
    graph_disable: tuple[str, ...],
    graphs_config: Path | None,
    include_local_paths: bool,
) -> None:
    """Analyze one audio file and write a report folder."""

    click.echo(f"Preparing AudioAtlas analysis for: {input_path.name}")
    from audioatlas.pipeline import analyze_file

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    selected_theme = _validate_theme_for_cli(theme)
    selection = _make_selection(graphs_profile, graph_enable, graph_disable, graphs_config)
    try:
        result = analyze_file(
            input_path,
            out_dir,
            config=cfg,
            max_duration_seconds=max_duration,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            theme_name=selected_theme,
            selection=selection,
            include_local_paths=include_local_paths,
        )
    except (AudioAtlasError, ValueError) as exc:
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
@click.option(
    "--graphs-profile",
    type=click.Choice(VALID_PROFILES),
    default=None,
    help="Graph render profile. Defaults to standard unless --graphs-config sets it.",
)
@click.option(
    "--enable",
    "graph_enable",
    multiple=True,
    help="Comma-separated graph keys to add to the selected profile. May be repeated.",
)
@click.option(
    "--disable",
    "graph_disable",
    multiple=True,
    help="Comma-separated graph keys to remove from the selected profile. May be repeated.",
)
@click.option(
    "--graphs-config",
    "graphs_config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML file with an optional top-level graphs block.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Stop on the first unreadable audio file instead of recording it and continuing.",
)
@click.option(
    "--include-local-paths",
    is_flag=True,
    help="Include resolved machine-local paths in JSON metadata (off by default for sharing).",
)
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
    graphs_profile: str | None,
    graph_enable: tuple[str, ...],
    graph_disable: tuple[str, ...],
    graphs_config: Path | None,
    strict: bool,
    include_local_paths: bool,
) -> None:
    """Analyze a folder of audio files and write a neutral catalog."""

    click.echo(f"Preparing AudioAtlas batch from: {input_folder.name}")
    from audioatlas.batch import analyze_folder

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    selected_theme = _validate_theme_for_cli(theme)
    selection = _make_selection(graphs_profile, graph_enable, graph_disable, graphs_config)
    try:
        result = analyze_folder(
            input_folder,
            out_dir,
            config=cfg,
            max_duration_seconds=max_duration,
            theme_name=selected_theme,
            selection=selection,
            strict=strict,
            include_local_paths=include_local_paths,
        )
    except (AudioAtlasError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"AudioAtlas catalog written to: {result.out_dir}")
    click.echo(f"Catalog summary: {result.catalog_summary_path}")
    click.echo(f"Catalog report:  {result.catalog_md_path}")
    click.echo(f"Catalog HTML:    {result.catalog_html_path}")
    skipped = result.catalog.get("skipped_files")
    skipped_count = len(skipped) if isinstance(skipped, list) else 0
    if skipped_count:
        click.echo(f"Skipped files:   {skipped_count} (details are in the catalog)", err=True)
    if result.catalog.get("track_count") == 0:
        raise click.ClickException(
            f"No audio files were analyzed. See {result.catalog_summary_path} for details."
        )


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
@click.option(
    "--graphs-profile",
    type=click.Choice(VALID_PROFILES),
    default=None,
    help="Graph render profile. Defaults to standard unless --graphs-config sets it.",
)
@click.option(
    "--enable",
    "graph_enable",
    multiple=True,
    help="Comma-separated graph keys to add to the selected profile. May be repeated.",
)
@click.option(
    "--disable",
    "graph_disable",
    multiple=True,
    help="Comma-separated graph keys to remove from the selected profile. May be repeated.",
)
@click.option(
    "--graphs-config",
    "graphs_config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML file with an optional top-level graphs block.",
)
@click.option(
    "--include-local-paths",
    is_flag=True,
    help="Include resolved machine-local paths in JSON metadata (off by default for sharing).",
)
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
    graphs_profile: str | None,
    graph_enable: tuple[str, ...],
    graph_disable: tuple[str, ...],
    graphs_config: Path | None,
    include_local_paths: bool,
) -> None:
    """Analyze manually supplied sections from one audio file.

    AudioAtlas does not detect song sections here. It runs the same report
    pipeline on explicit source ranges supplied by the user.
    """

    parsed_sections = _collect_section_definitions(section_specs, config_path)
    click.echo(f"Preparing {len(parsed_sections)} manual section report(s) for: {input_path.name}")
    from audioatlas.pipeline import analyze_file

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    selected_theme = _validate_theme_for_cli(theme)
    selection = _make_selection(graphs_profile, graph_enable, graph_disable, graphs_config)
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
                selection=selection,
                include_local_paths=include_local_paths,
            )
        except (AudioAtlasError, ValueError) as exc:
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

    from audioatlas.theme import theme_listing_text

    click.echo(theme_listing_text())


def _validate_theme_for_cli(theme: str | None) -> str:
    from audioatlas.theme import validate_theme_name

    try:
        return validate_theme_name(theme)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--theme") from exc


def _make_selection(
    cli_profile: str | None,
    cli_enable: tuple[str, ...],
    cli_disable: tuple[str, ...],
    graphs_config: Path | None,
) -> GraphSelection:
    from audioatlas.graphs import all_graphs
    from audioatlas.graphs.selection import GraphSelection, GraphSelectionError

    file_selection = _parse_graphs_config(graphs_config) if graphs_config is not None else {}
    profile = cli_profile or str(file_selection.get("profile", "standard"))
    enable = _merge_graph_key_lists(
        tuple(file_selection.get("enable", ())),
        _parse_graph_key_options(cli_enable),
    )
    disable = _merge_graph_key_lists(
        tuple(file_selection.get("disable", ())),
        _parse_graph_key_options(cli_disable),
    )
    selection = GraphSelection(profile=profile, enable=enable, disable=disable)
    try:
        selection.resolve(all_graphs())
    except GraphSelectionError as exc:
        raise click.BadParameter(str(exc), param_hint="--graphs-profile/--enable/--disable") from exc
    return selection


def _parse_graph_key_options(values: tuple[str, ...]) -> tuple[str, ...]:
    keys: list[str] = []
    for value in values:
        keys.extend(key.strip() for key in value.split(",") if key.strip())
    return tuple(dict.fromkeys(keys))


def _merge_graph_key_lists(*lists: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for values in lists:
        merged.extend(values)
    return tuple(dict.fromkeys(merged))


def _parse_graphs_config(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise click.BadParameter(f"Invalid YAML in {path}: {exc}") from exc

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise click.BadParameter(f"Graphs config {path} must be a YAML mapping.")
    graphs = loaded.get("graphs", {})
    if graphs is None:
        graphs = {}
    if not isinstance(graphs, dict):
        raise click.BadParameter(f"Graphs config {path} must contain a graphs mapping.")

    out: dict[str, Any] = {}
    if "profile" in graphs:
        profile = graphs["profile"]
        if not isinstance(profile, str):
            raise click.BadParameter(f"graphs.profile in {path} must be a string.")
        out["profile"] = profile
    if "enable" in graphs:
        out["enable"] = _string_list(graphs["enable"], source=f"graphs.enable in {path}")
    if "disable" in graphs:
        out["disable"] = _string_list(graphs["disable"], source=f"graphs.disable in {path}")
    return out


def _string_list(value: Any, *, source: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise click.BadParameter(f"{source} must be a list of strings.")
    return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))


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
    from audioatlas.config import AnalysisConfig

    return AnalysisConfig(
        n_fft=n_fft,
        hop_length=hop_length,
        rms_frame_length=rms_frame_length if rms_frame_length is not None else n_fft,
        db_floor=db_floor,
        true_peak_oversample=true_peak_oversample,
    )


if __name__ == "__main__":
    main()
