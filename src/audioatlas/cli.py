"""Command line interface for AudioAtlas.

Keep this module thin. Argument parsing only. All work is done in
``audioatlas.pipeline.analyze_file``.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import yaml

from audioatlas import __version__
from audioatlas.errors import AudioAtlasError, RevisionDiffError
from audioatlas.graph_profiles import VALID_PROFILES
from audioatlas.markdown import markdown_code_span, markdown_text
from audioatlas.presentation import VALID_PRESENTATION_MODES

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
    type=click.Path(file_okay=False, path_type=Path), required=False,
    help="Output directory. Defaults to ./audioatlas-report-<filename>.",
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
    "--presentation",
    type=click.Choice(VALID_PRESENTATION_MODES),
    default=None,
    help="Opening report view. Defaults to Studio; every HTML report can switch views.",
)
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
    "--track-id",
    default=None,
    help=(
        "Optional opaque revision token. AudioAtlas stores only its SHA-256 digest so "
        "separately named exports can carry matching identity evidence."
    ),
)
@click.option(
    "--include-local-paths",
    is_flag=True,
    help="Include resolved machine-local paths in JSON metadata (off by default for sharing).",
)
def analyze(
    input_path: Path,
    out_dir: Path | None,
    max_duration: float | None,
    start_seconds: float | None,
    end_seconds: float | None,
    n_fft: int,
    hop_length: int,
    rms_frame_length: int | None,
    db_floor: float,
    true_peak_oversample: int,
    theme: str | None,
    presentation: str | None,
    graphs_profile: str | None,
    graph_enable: tuple[str, ...],
    graph_disable: tuple[str, ...],
    graphs_config: Path | None,
    track_id: str | None,
    include_local_paths: bool,
) -> None:
    """Analyze one audio file and write a report folder."""

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    _validate_source_range_options(start_seconds, end_seconds, max_duration)
    selected_theme = _validate_theme_for_cli(theme)
    selection = _make_selection(graphs_profile, graph_enable, graph_disable, graphs_config)
    if out_dir is None:
        out_dir = _default_report_out(input_path)
        click.echo(f"No --out supplied; using: {out_dir}")
    click.echo(f"Preparing AudioAtlas analysis for: {input_path.name}")
    from audioatlas.pipeline import analyze_file

    try:
        result = analyze_file(
            input_path,
            out_dir,
            config=cfg,
            max_duration_seconds=max_duration,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            theme_name=selected_theme,
            presentation_mode=presentation,
            selection=selection,
            include_local_paths=include_local_paths,
            track_id=track_id,
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
    "--presentation",
    type=click.Choice(VALID_PRESENTATION_MODES),
    default=None,
    help="Opening report view. Defaults to Studio; every HTML report can switch views.",
)
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
    presentation: str | None,
    graphs_profile: str | None,
    graph_enable: tuple[str, ...],
    graph_disable: tuple[str, ...],
    graphs_config: Path | None,
    strict: bool,
    include_local_paths: bool,
) -> None:
    """Analyze a folder of audio files and write a neutral catalog."""

    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    _validate_optional_seconds(max_duration, option="--max-duration", allow_zero=False)
    selected_theme = _validate_theme_for_cli(theme)
    selection = _make_selection(graphs_profile, graph_enable, graph_disable, graphs_config)
    click.echo(f"Preparing AudioAtlas batch from: {input_folder.name}")
    from audioatlas.batch import analyze_folder

    try:
        result = analyze_folder(
            input_folder,
            out_dir,
            config=cfg,
            max_duration_seconds=max_duration,
            theme_name=selected_theme,
            presentation_mode=presentation,
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
    "--presentation",
    type=click.Choice(VALID_PRESENTATION_MODES),
    default=None,
    help="Opening report view. Defaults to Studio; every HTML report can switch views.",
)
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
    "--track-id",
    default=None,
    help=(
        "Optional opaque revision token. Only its SHA-256 digest is stored; all section "
        "reports from this run receive the same identity."
    ),
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
    presentation: str | None,
    graphs_profile: str | None,
    graph_enable: tuple[str, ...],
    graph_disable: tuple[str, ...],
    graphs_config: Path | None,
    track_id: str | None,
    include_local_paths: bool,
) -> None:
    """Analyze manually supplied sections from one audio file.

    AudioAtlas does not detect song sections here. It runs the same report
    pipeline on explicit source ranges supplied by the user.
    """

    parsed_sections = _collect_section_definitions(section_specs, config_path)
    cfg = _make_config(n_fft, hop_length, rms_frame_length, db_floor, true_peak_oversample)
    selected_theme = _validate_theme_for_cli(theme)
    selection = _make_selection(graphs_profile, graph_enable, graph_disable, graphs_config)
    click.echo(f"Preparing {len(parsed_sections)} manual section report(s) for: {input_path.name}")
    from audioatlas.pipeline import analyze_file

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
                presentation_mode=presentation,
                selection=selection,
                include_local_paths=include_local_paths,
                track_id=track_id,
            )
        except (AudioAtlasError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc

        section_results.append((name, start_seconds, end_seconds, result))
        click.echo(f"Section report written to: {result.out_dir}")

    # Build enhanced index with comparison table using existing summary data
    index_lines: list[str] = [
        "# AudioAtlas section reports",
        "",
        f"Input: {markdown_code_span(input_path.name)}",
        "",
        "These are manually supplied sections, not automatically detected song sections.",
        "",
    ]
    index_lines.extend(_build_section_comparison_table(section_results))

    index_path = out_dir / "section_index.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    click.echo(f"Section index: {index_path}")


@main.command(name="diff")
@click.argument(
    "report_a",
    type=click.Path(exists=True, path_type=Path),
)
@click.argument(
    "report_b",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="Output directory for the static revision-delta report.",
)
@click.option(
    "--confirm-same-track",
    is_flag=True,
    help=(
        "Assert that both reports are revisions of the same track when matching "
        "--track-id digests are unavailable. Conflicting digests are never overridden."
    ),
)
@click.option(
    "--allow-incomparable",
    is_flag=True,
    help=(
        "Generate a prominently caveated report when analysis provenance differs or is missing."
    ),
)
@click.option("--label-a", default=None, help="Optional display label for report A.")
@click.option("--label-b", default=None, help="Optional display label for report B.")
@click.option("--theme", default=None, help="Built-in report theme ID. Run `audioatlas themes`.")
@click.option(
    "--presentation",
    type=click.Choice(VALID_PRESENTATION_MODES),
    default=None,
    help="Opening report view. Defaults to Studio; the HTML diff can switch views.",
)
def diff_reports(
    report_a: Path,
    report_b: Path,
    out_dir: Path,
    confirm_same_track: bool,
    allow_incomparable: bool,
    label_a: str | None,
    label_b: str | None,
    theme: str | None,
    presentation: str | None,
) -> None:
    """Compare two completed reports for revisions of the same track."""

    from audioatlas.revision_diff import (
        generate_revision_diff,
        load_report_inputs,
        write_revision_diff,
    )

    selected_theme = _validate_theme_for_cli(theme)
    try:
        source_directories = {
            load_report_inputs(report_a).directory.resolve(),
            load_report_inputs(report_b).directory.resolve(),
        }
        if out_dir.expanduser().resolve() in source_directories:
            raise RevisionDiffError(
                "The revision-diff output must be separate from both source report folders."
            )
        payload = generate_revision_diff(
            report_a,
            report_b,
            confirm_same_track=confirm_same_track,
            allow_incomparable=allow_incomparable,
            label_a=label_a,
            label_b=label_b,
        )
        paths = write_revision_diff(
            payload,
            out_dir,
            theme_name=selected_theme,
            presentation_mode=presentation,
        )
    except (AudioAtlasError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"AudioAtlas revision delta written to: {out_dir}")
    click.echo(f"JSON:     {paths['json']}")
    click.echo(f"Markdown: {paths['markdown']}")
    click.echo(f"HTML:     {paths['html']}")


@main.group()
def project() -> None:
    """Keep same-track revisions in one private, static song workspace."""


@project.command(name="init")
@click.argument("directory", type=click.Path(file_okay=False, path_type=Path))
@click.option("--name", required=True, help="Human-readable song or project name.")
@click.option(
    "--sections",
    "sections_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional YAML file with a reusable top-level sections list.",
)
@click.option(
    "--graphs-profile",
    type=click.Choice(VALID_PROFILES),
    default="standard",
    show_default=True,
    help="Plot depth used for every revision and manual section.",
)
@click.option("--theme", default=None, help="Built-in report theme ID.")
@click.option(
    "--presentation",
    type=click.Choice(VALID_PRESENTATION_MODES),
    default=None,
    help="Opening view used for project, revision, diff, and section reports.",
)
def project_init(
    directory: Path,
    name: str,
    sections_path: Path | None,
    graphs_profile: str,
    theme: str | None,
    presentation: str | None,
) -> None:
    """Create a new local song workspace."""

    from audioatlas.project import init_project

    sections = _parse_sections_from_yaml(sections_path) if sections_path is not None else []
    selected_theme = _validate_theme_for_cli(theme)
    try:
        init_project(
            directory,
            name=name,
            sections=sections,
            graphs_profile=graphs_profile,
            theme=selected_theme,
            presentation=presentation,
        )
    except (AudioAtlasError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"AudioAtlas song project created: {directory}")
    click.echo(f"Add a revision: audioatlas project add {directory} song.wav --label 'Mix 1'")
    click.echo(f"Project index: {directory / 'project.html'}")


@project.command(name="add")
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.argument(
    "audio_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--label", required=True, help="Human-readable revision label, such as Mix 2.")
@click.option(
    "--allow-incomparable",
    is_flag=True,
    help="Allow a prominently caveated adjacent diff when analysis provenance changed.",
)
def project_add(
    directory: Path,
    audio_file: Path,
    label: str,
    allow_incomparable: bool,
) -> None:
    """Analyze and append one user-asserted revision of the project song."""

    from audioatlas.project import add_project_revision

    click.echo(f"Preparing project revision for: {audio_file.name}")
    try:
        revision = add_project_revision(
            directory,
            audio_file,
            label=label,
            allow_incomparable=allow_incomparable,
        )
    except (AudioAtlasError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Revision added: {revision['label']} ({revision['id']})")
    click.echo(f"Report: {directory / revision['report'] / 'report.html'}")
    if revision.get("diff_from_previous"):
        click.echo(
            "Prior delta: "
            f"{directory / revision['diff_from_previous'] / 'revision_diff.html'}"
        )
    click.echo(f"Project index: {directory / 'project.html'}")


@project.command(name="build")
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
def project_build(directory: Path) -> None:
    """Validate completed artifacts and rebuild the static project index."""

    from audioatlas.project import build_project

    try:
        paths = build_project(directory)
    except (AudioAtlasError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"AudioAtlas song project rebuilt: {directory}")
    click.echo(f"JSON:     {paths['json']}")
    click.echo(f"Markdown: {paths['markdown']}")
    click.echo(f"HTML:     {paths['html']}")


@main.command()
def themes() -> None:
    """List built-in static report themes."""

    from audioatlas.theme import theme_listing_text

    click.echo(theme_listing_text())


def _default_report_out(input_path: Path) -> Path:
    """Return a predictable friendly output folder for one-track analysis."""

    chars = [char.lower() if char.isalnum() else "-" for char in input_path.stem]
    slug = re.sub(r"-+", "-", "".join(chars)).strip("-") or "track"
    return Path.cwd() / f"audioatlas-report-{slug}"


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
    loaded = _load_yaml_mapping(path, label="Graphs config")
    graphs = loaded.get("graphs", {})
    if graphs is None:
        graphs = {}
    if not isinstance(graphs, dict):
        raise click.BadParameter(f"Graphs config {path} must contain a graphs mapping.")
    _reject_unknown_keys(
        graphs,
        allowed={"profile", "enable", "disable"},
        source=f"graphs block in {path}",
    )

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


def _load_yaml_mapping(path: Path, *, label: str) -> dict[Any, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise click.BadParameter(f"Could not read {label.lower()} {path}: {exc}") from exc
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise click.BadParameter(f"Invalid YAML in {path}: {exc}") from exc

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise click.BadParameter(f"{label} {path} must be a YAML mapping.")
    _reject_unknown_keys(
        loaded,
        allowed={"graphs", "sections"},
        source=f"top level of {path}",
    )
    return loaded


def _reject_unknown_keys(
    mapping: dict[Any, Any],
    *,
    allowed: set[str],
    source: str,
) -> None:
    unknown = [key for key in mapping if key not in allowed]
    if not unknown:
        return
    rendered = ", ".join(repr(key) for key in sorted(unknown, key=repr))
    raise click.BadParameter(f"Unknown key(s) in {source}: {rendered}.")


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
    _validate_unique_section_slugs(parsed)
    return parsed


def _normalize_section(
    name: str,
    start: float,
    end: float | None,
) -> tuple[str, float, float | None]:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise click.BadParameter("Section name cannot be blank")
    if len(cleaned_name) > 160:
        raise click.BadParameter("Section name must be 160 characters or fewer")
    if any(character in cleaned_name for character in ("\r", "\n", "\0")):
        raise click.BadParameter("Section name cannot contain line breaks or null characters")
    if not math.isfinite(start):
        raise click.BadParameter("Section start time must be finite")
    if start < 0:
        raise click.BadParameter("Section start time must be non-negative")
    if end is not None:
        if not math.isfinite(end):
            raise click.BadParameter("Section end time must be finite")
        if end <= start:
            raise click.BadParameter("Section end time must be greater than start time")
    return cleaned_name, start, end


def _validate_unique_section_slugs(
    sections: list[tuple[str, float, float | None]],
) -> None:
    by_slug: dict[str, str] = {}
    for name, start, end in sections:
        slug = _section_slug(name, start, end)
        previous_name = by_slug.get(slug)
        if previous_name is not None:
            raise click.BadParameter(
                "Section definitions produce the same output folder "
                f"{slug!r}: {previous_name!r} and {name!r}."
            )
        by_slug[slug] = name


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
    loaded = _load_yaml_mapping(path, label="Section config")

    sections = loaded.get("sections")
    if not isinstance(sections, list) or not sections:
        raise click.BadParameter(f"Section config {path} must contain a non-empty sections list.")

    parsed: list[tuple[str, float, float | None]] = []
    for index, entry in enumerate(sections, start=1):
        if not isinstance(entry, dict):
            raise click.BadParameter(f"Section entry {index} in {path} must be a mapping.")
        _reject_unknown_keys(
            entry,
            allowed={"name", "start", "end"},
            source=f"section entry {index} in {path}",
        )
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
            f"| {markdown_text(name)} | {src} | {_fmt(dur, 1)} | {_fmt(lufs, 1)} | {_fmt(plr, 1)} | "
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

    config = AnalysisConfig(
        n_fft=n_fft,
        hop_length=hop_length,
        rms_frame_length=rms_frame_length if rms_frame_length is not None else n_fft,
        db_floor=db_floor,
        true_peak_oversample=true_peak_oversample,
    )
    try:
        config.validate()
    except ValueError as exc:
        raise click.BadParameter(
            str(exc),
            param_hint=(
                "--n-fft/--hop-length/--rms-frame-length/"
                "--db-floor/--true-peak-oversample"
            ),
        ) from exc
    return config


def _validate_optional_seconds(
    value: float | None,
    *,
    option: str,
    allow_zero: bool,
) -> None:
    if value is None:
        return
    if not math.isfinite(value):
        raise click.BadParameter("must be finite", param_hint=option)
    if value < 0 or (value == 0 and not allow_zero):
        comparison = "non-negative" if allow_zero else "positive"
        raise click.BadParameter(f"must be {comparison}", param_hint=option)


def _validate_source_range_options(
    start_seconds: float | None,
    end_seconds: float | None,
    max_duration_seconds: float | None,
) -> None:
    _validate_optional_seconds(start_seconds, option="--start", allow_zero=True)
    _validate_optional_seconds(end_seconds, option="--end", allow_zero=False)
    _validate_optional_seconds(
        max_duration_seconds,
        option="--max-duration",
        allow_zero=False,
    )
    if (
        start_seconds is not None
        and end_seconds is not None
        and end_seconds <= start_seconds
    ):
        raise click.BadParameter("must be greater than --start", param_hint="--end")


if __name__ == "__main__":
    main()
