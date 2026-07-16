"""Local, static song projects built from user-asserted track revisions."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

import yaml

from audioatlas import __version__
from audioatlas.errors import ProjectError
from audioatlas.markdown import markdown_code_span, markdown_text
from audioatlas.output import (
    OUTPUT_MARKER_FILENAME,
    PROJECT_CONFIG_FILENAME,
    PROJECT_FILENAMES,
    publish_staged_output,
    staged_output_directory,
    write_output_manifest,
)
from audioatlas.presentation import (
    presentation_controls_html,
    presentation_css,
    presentation_script,
    skip_link_html,
    validate_presentation_mode,
)
from audioatlas.release import PROJECT_SCHEMA_VERSION
from audioatlas.theme import theme_css_variables, validate_theme_name

PROJECT_JSON_FILENAME = "project.json"
PROJECT_MARKDOWN_FILENAME = "project.md"
PROJECT_HTML_FILENAME = "project.html"
_PROJECT_KIND = "song-project"
_CONFIG_KEYS = {
    "schema_version",
    "name",
    "project_id",
    "created_at",
    "graphs_profile",
    "theme",
    "presentation",
    "sections",
    "revisions",
}


def init_project(
    directory: str | Path,
    *,
    name: str,
    sections: list[tuple[str, float, float | None]] | None = None,
    graphs_profile: str = "standard",
    theme: str | None = None,
    presentation: str | None = None,
) -> dict[str, Any]:
    """Create a transparent local song-project configuration and static index."""

    root = Path(directory).expanduser()
    _validate_project_name(name)
    _validate_project_destination(root)
    normalized_sections = _normalize_sections(sections or [])
    selected_theme = validate_theme_name(theme)
    selected_presentation = validate_presentation_mode(presentation)
    if graphs_profile not in {"compact", "minimal", "standard", "full"}:
        raise ProjectError(f"Unknown graph profile {graphs_profile!r}.")

    config: dict[str, Any] = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "name": name.strip(),
        "project_id": uuid.uuid4().hex,
        "created_at": _utc_timestamp(),
        "graphs_profile": graphs_profile,
        "theme": selected_theme,
        "presentation": selected_presentation,
        "sections": normalized_sections,
        "revisions": [],
    }
    _publish_project_root(root, config)
    return config


def add_project_revision(
    directory: str | Path,
    audio_file: str | Path,
    *,
    label: str,
    allow_incomparable: bool = False,
) -> dict[str, Any]:
    """Analyze and atomically append one revision to an existing song project."""

    root = Path(directory).expanduser()
    config = load_project(root)
    _validate_revision_label(label)
    source = Path(audio_file).expanduser()
    if source.is_symlink() or not source.is_file():
        raise ProjectError(f"Audio input is not a readable file: {source.name!r}.")

    revisions = list(config["revisions"])
    revision_id = _next_revision_id(revisions, label)
    report_relative = Path("reports") / revision_id
    section_root_relative = Path("sections") / revision_id
    previous = revisions[-1] if revisions else None
    diff_relative = (
        Path("diffs") / f"{previous['id']}--{revision_id}" if previous is not None else None
    )
    destinations = [root / report_relative]
    if config["sections"]:
        destinations.append(root / section_root_relative)
    if diff_relative is not None:
        destinations.append(root / diff_relative)
    for destination in destinations:
        if destination.exists() or destination.is_symlink():
            raise ProjectError(
                f"Generated project destination already exists: {destination.name!r}."
            )

    transaction = Path(
        tempfile.mkdtemp(prefix=f".{root.name}.revision-", dir=root.parent)
    )
    moved: list[Path] = []
    try:
        from audioatlas.graphs.selection import GraphSelection
        from audioatlas.pipeline import analyze_file
        from audioatlas.revision_diff import generate_revision_diff, write_revision_diff

        selection = GraphSelection(profile=config["graphs_profile"])
        staged_report = transaction / report_relative
        analyze_file(
            source,
            staged_report,
            theme_name=config["theme"],
            presentation_mode=config["presentation"],
            selection=selection,
            track_id=config["project_id"],
        )

        section_entries: list[dict[str, Any]] = []
        if config["sections"]:
            for section in config["sections"]:
                slug = _section_slug(section["name"], section["start"], section.get("end"))
                relative = section_root_relative / slug
                section_result = analyze_file(
                    source,
                    transaction / relative,
                    start_seconds=section["start"],
                    end_seconds=section.get("end"),
                    theme_name=config["theme"],
                    presentation_mode=config["presentation"],
                    selection=selection,
                    track_id=config["project_id"],
                )
                section_entries.append(
                    {
                        "name": section["name"],
                        "start": section["start"],
                        "end": section.get("end"),
                        "report": section_result.out_dir.relative_to(transaction).as_posix(),
                    }
                )

        if previous is not None and diff_relative is not None:
            payload = generate_revision_diff(
                root / previous["report"],
                staged_report,
                allow_incomparable=allow_incomparable,
                label_a=previous["label"],
                label_b=label.strip(),
            )
            write_revision_diff(
                payload,
                transaction / diff_relative,
                theme_name=config["theme"],
                presentation_mode=config["presentation"],
            )

        revision: dict[str, Any] = {
            "id": revision_id,
            "label": label.strip(),
            "source": str(source.resolve()),
            "source_filename": source.name,
            "added_at": _utc_timestamp(),
            "report": report_relative.as_posix(),
            "sections": section_entries,
        }
        if diff_relative is not None:
            revision["diff_from_previous"] = diff_relative.as_posix()
        candidate = dict(config)
        candidate["revisions"] = [*revisions, revision]

        try:
            for relative in (report_relative, section_root_relative, diff_relative):
                if relative is None:
                    continue
                staged = transaction / relative
                if not staged.exists():
                    continue
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, destination)
                moved.append(destination)
            _publish_project_root(root, candidate)
        except BaseException:
            for destination in reversed(moved):
                _remove_tree(destination)
            _remove_empty_project_containers(root)
            raise
        return revision
    finally:
        shutil.rmtree(transaction, ignore_errors=True)


def build_project(directory: str | Path) -> dict[str, Path]:
    """Validate existing revision artifacts and rebuild the static project index."""

    root = Path(directory).expanduser()
    config = load_project(root)
    _validate_revision_artifacts(root, config)
    _publish_project_root(root, config)
    return {
        "json": root / PROJECT_JSON_FILENAME,
        "markdown": root / PROJECT_MARKDOWN_FILENAME,
        "html": root / PROJECT_HTML_FILENAME,
    }


def load_project(directory: str | Path) -> dict[str, Any]:
    """Load and strictly validate one AudioAtlas project configuration."""

    root = Path(directory).expanduser()
    path = root / PROJECT_CONFIG_FILENAME
    if path.is_symlink() or not path.is_file():
        raise ProjectError(f"No {PROJECT_CONFIG_FILENAME} was found in {root.name!r}.")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProjectError(f"Could not read {PROJECT_CONFIG_FILENAME}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ProjectError(f"{PROJECT_CONFIG_FILENAME} must contain a YAML mapping.")
    unknown = sorted((key for key in loaded if key not in _CONFIG_KEYS), key=repr)
    if unknown:
        rendered = ", ".join(repr(key) for key in unknown)
        raise ProjectError(f"Unknown project configuration key(s): {rendered}.")
    if loaded.get("schema_version") != PROJECT_SCHEMA_VERSION:
        raise ProjectError(
            "Unsupported song-project schema: "
            f"{loaded.get('schema_version')!r}; expected {PROJECT_SCHEMA_VERSION!r}."
        )
    _validate_project_name(loaded.get("name"))
    project_id = loaded.get("project_id")
    if not isinstance(project_id, str) or re.fullmatch(r"[a-f0-9]{32}", project_id) is None:
        raise ProjectError("Project identity is missing or invalid.")
    if not isinstance(loaded.get("created_at"), str) or not loaded["created_at"]:
        raise ProjectError("Project creation timestamp is missing or invalid.")
    if loaded.get("graphs_profile") not in {"compact", "minimal", "standard", "full"}:
        raise ProjectError("Project graph profile is invalid.")
    loaded["theme"] = validate_theme_name(loaded.get("theme"))
    loaded["presentation"] = validate_presentation_mode(loaded.get("presentation"))
    loaded["sections"] = _normalize_sections(loaded.get("sections", []))
    revisions = loaded.get("revisions")
    if not isinstance(revisions, list):
        raise ProjectError("Project revisions must be a list.")
    _validate_revisions(revisions)
    return loaded


def _publish_project_root(root: Path, config: dict[str, Any]) -> None:
    payload = _public_project_payload(root, config)
    with staged_output_directory(root) as staging:
        (staging / PROJECT_CONFIG_FILENAME).write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        (staging / PROJECT_JSON_FILENAME).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (staging / PROJECT_MARKDOWN_FILENAME).write_text(
            _project_markdown(payload), encoding="utf-8"
        )
        (staging / PROJECT_HTML_FILENAME).write_text(
            _project_html(payload, config["theme"], config["presentation"]),
            encoding="utf-8",
        )
        write_output_manifest(
            staging,
            kind=_PROJECT_KIND,
            generated_files=[*PROJECT_FILENAMES, OUTPUT_MARKER_FILENAME],
        )
        publish_staged_output(staging, root, owned_filenames=set(PROJECT_FILENAMES))


def _public_project_payload(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    revisions: list[dict[str, Any]] = []
    for entry in config["revisions"]:
        report = root / entry["report"]
        summary_path = report / "summary.json"
        if not summary_path.is_file():
            raise ProjectError(
                f"Revision {entry['label']!r} is missing its complete report."
            )
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectError(f"Revision {entry['label']!r} has invalid summary JSON.") from exc
        levels = summary.get("levels") if isinstance(summary, dict) else {}
        if not isinstance(levels, dict):
            levels = {}
        public_entry: dict[str, Any] = {
            "id": entry["id"],
            "label": entry["label"],
            "source_filename": entry["source_filename"],
            "added_at": entry["added_at"],
            "report": entry["report"],
            "duration_seconds": levels.get("duration_seconds"),
            "sections": entry.get("sections", []),
        }
        if "diff_from_previous" in entry:
            public_entry["diff_from_previous"] = entry["diff_from_previous"]
        revisions.append(public_entry)
    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "audioatlas_version": __version__,
        "project_kind": "same-track-song-workspace",
        "name": config["name"],
        "project_id_sha256": hashlib.sha256(config["project_id"].encode("utf-8")).hexdigest(),
        "graphs_profile": config["graphs_profile"],
        "revisions": revisions,
        "interpretation_boundary": (
            "Revision order and deltas are descriptive. AudioAtlas does not select a winner, "
            "assign quality, or infer that a numerical direction is preferable."
        ),
    }


def _project_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# AudioAtlas song project: {markdown_text(payload['name'])}",
        "",
        payload["interpretation_boundary"],
        "",
        f"- Project schema: {markdown_code_span(payload['schema_version'])}",
        f"- Graph profile: {markdown_code_span(payload['graphs_profile'])}",
        f"- Revisions: {len(payload['revisions'])}",
        "",
        "## Revisions",
        "",
    ]
    if not payload["revisions"]:
        lines.append("No revisions have been added yet.")
    for index, revision in enumerate(payload["revisions"], start=1):
        lines.extend(
            [
                f"### {index}. {markdown_text(revision['label'])}",
                "",
                f"- Source label: {markdown_code_span(revision['source_filename'])}",
                f"- [Open report]({revision['report']}/report.html)",
            ]
        )
        diff = revision.get("diff_from_previous")
        if diff:
            lines.append(f"- [Compare with prior revision]({diff}/revision_diff.html)")
        for section in revision.get("sections", []):
            lines.append(
                f"- Section {markdown_text(section['name'])}: "
                f"[open report]({section['report']}/report.html)"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _project_html(payload: dict[str, Any], theme: str, presentation: str) -> str:
    cards: list[str] = []
    for index, revision in enumerate(payload["revisions"], start=1):
        links = [
            f'<a class="primary" href="{escape(revision["report"], quote=True)}/report.html">Open report</a>'
        ]
        diff = revision.get("diff_from_previous")
        if diff:
            links.append(
                f'<a href="{escape(diff, quote=True)}/revision_diff.html">Compare with prior</a>'
            )
        section_links = "".join(
            "<li>"
            f'<a href="{escape(section["report"], quote=True)}/report.html">'
            f'{escape(str(section["name"]))}</a>'
            "</li>"
            for section in revision.get("sections", [])
        )
        sections = (
            f"<details><summary>{len(revision['sections'])} manual section report(s)</summary>"
            f"<ul>{section_links}</ul></details>"
            if revision.get("sections")
            else ""
        )
        duration = revision.get("duration_seconds")
        duration_text = f"{float(duration):.1f}s" if isinstance(duration, (int, float)) else "n/a"
        cards.append(
            '<article class="revision">'
            f'<p class="eyebrow">Revision {index}</p>'
            f'<h2>{escape(str(revision["label"]))}</h2>'
            f'<p><code>{escape(str(revision["source_filename"]))}</code> · {duration_text}</p>'
            f'<div class="actions">{"".join(links)}</div>{sections}'
            "</article>"
        )
    empty = '<p class="empty">No revisions have been added yet.</p>' if not cards else ""
    selected = validate_presentation_mode(presentation)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AudioAtlas song project · {escape(str(payload['name']))}</title>
<style>
{theme_css_variables(theme)}
{presentation_css()}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, sans-serif; line-height: 1.55; }}
.container {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 20px 0 64px; }}
header {{ padding: 28px; border: 1px solid var(--border); border-radius: 18px; background: var(--surface); }}
h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 6vw, 3.5rem); line-height: 1.05; }}
.boundary {{ max-width: 74ch; color: var(--text-muted); }}
.meta {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 0; list-style: none; }}
.meta li {{ padding: 6px 10px; border-radius: 999px; background: var(--chip-bg); }}
.revisions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; margin-top: 28px; }}
.revision {{ padding: 22px; border: 1px solid var(--border); border-radius: 16px; background: var(--surface); box-shadow: var(--shadow-card); }}
.revision h2 {{ margin: 4px 0 8px; }}
.eyebrow {{ margin: 0; color: var(--accent); font-weight: 750; text-transform: uppercase; letter-spacing: .06em; font-size: .78rem; }}
.actions {{ display: flex; flex-wrap: wrap; gap: 9px; margin: 18px 0 8px; }}
.actions a {{ padding: 8px 11px; border: 1px solid var(--border); border-radius: 9px; color: var(--accent); font-weight: 700; text-decoration: none; }}
.actions a.primary {{ color: var(--surface); background: var(--accent); border-color: var(--accent); }}
details {{ margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border-soft); }}
.empty {{ padding: 24px; border: 1px dashed var(--border); border-radius: 12px; }}
@media print {{ .actions {{ display: none; }} }}
</style>
</head>
<body data-presentation="{escape(selected, quote=True)}">
{skip_link_html()}
<main id="main-content" class="container">
<header>
{presentation_controls_html(selected)}
<p class="eyebrow">Local song workspace</p>
<h1>{escape(str(payload['name']))}</h1>
<p class="boundary">{escape(str(payload['interpretation_boundary']))}</p>
<ul class="meta"><li>{len(payload['revisions'])} revision(s)</li><li>{escape(str(payload['graphs_profile']))} plots</li><li>project schema {escape(str(payload['schema_version']))}</li></ul>
</header>
<section class="revisions" aria-label="Song revisions">{''.join(cards)}</section>
{empty}
</main>
{presentation_script(selected)}
</body>
</html>
"""


def _validate_project_destination(root: Path) -> None:
    if root.exists() and not root.is_dir():
        raise ProjectError(f"Project destination is not a directory: {root.name!r}.")
    if (root / PROJECT_CONFIG_FILENAME).exists():
        raise ProjectError(f"A song project already exists in {root.name!r}.")
    marker = root / OUTPUT_MARKER_FILENAME
    generated = {"summary.json", "catalog_summary.json", "revision_diff.json"}
    if marker.exists() or any((root / name).exists() for name in generated):
        raise ProjectError("Choose a folder that is not already an AudioAtlas output root.")


def _validate_project_name(value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProjectError("Project name cannot be blank.")
    if len(value.strip()) > 160 or any(char in value for char in ("\r", "\n", "\0")):
        raise ProjectError("Project name must be one line and 160 characters or fewer.")


def _validate_revision_label(value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProjectError("Revision label cannot be blank.")
    if len(value.strip()) > 160 or any(char in value for char in ("\r", "\n", "\0")):
        raise ProjectError("Revision label must be one line and 160 characters or fewer.")


def _normalize_sections(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ProjectError("Project sections must be a list.")
    normalized: list[dict[str, Any]] = []
    slugs: set[str] = set()
    for index, item in enumerate(value, start=1):
        if isinstance(item, tuple) and len(item) == 3:
            name, start, end = item
        elif isinstance(item, dict):
            unknown = set(item) - {"name", "start", "end"}
            if unknown:
                raise ProjectError(f"Section {index} has unknown keys: {sorted(unknown)!r}.")
            name, start, end = item.get("name"), item.get("start"), item.get("end")
        else:
            raise ProjectError(f"Section {index} must be a name/start/end mapping.")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 160:
            raise ProjectError(f"Section {index} has an invalid name.")
        if isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start):
            raise ProjectError(f"Section {index} start must be a finite number.")
        if start < 0:
            raise ProjectError(f"Section {index} start must be non-negative.")
        if end is not None:
            if isinstance(end, bool) or not isinstance(end, (int, float)) or not math.isfinite(end):
                raise ProjectError(f"Section {index} end must be a finite number or omitted.")
            if end <= start:
                raise ProjectError(f"Section {index} end must be greater than its start.")
        entry = {"name": name.strip(), "start": float(start), "end": float(end) if end is not None else None}
        slug = _section_slug(entry["name"], entry["start"], entry["end"])
        if slug in slugs:
            raise ProjectError(f"Section {index} collides with another section output folder.")
        slugs.add(slug)
        normalized.append(entry)
    return normalized


def _validate_revisions(revisions: list[Any]) -> None:
    ids: set[str] = set()
    for index, revision in enumerate(revisions, start=1):
        if not isinstance(revision, dict):
            raise ProjectError(f"Revision {index} must be a mapping.")
        required = {"id", "label", "source", "source_filename", "added_at", "report", "sections"}
        allowed = required | {"diff_from_previous"}
        if set(revision) - allowed or not required <= set(revision):
            raise ProjectError(f"Revision {index} has an invalid field set.")
        revision_id = revision["id"]
        if not isinstance(revision_id, str) or not revision_id or Path(revision_id).name != revision_id:
            raise ProjectError(f"Revision {index} has an invalid ID.")
        if revision_id in ids:
            raise ProjectError(f"Revision ID {revision_id!r} is duplicated.")
        ids.add(revision_id)
        _validate_revision_label(revision["label"])
        for key in ("source", "source_filename", "added_at", "report"):
            if not isinstance(revision[key], str) or not revision[key]:
                raise ProjectError(f"Revision {index} has an invalid {key} value.")
        if Path(revision["source_filename"]).name != revision["source_filename"]:
            raise ProjectError(f"Revision {index} source filename must be portable.")
        _validate_relative_artifact_path(
            revision["report"], expected_prefix="reports", expected_id=revision_id
        )
        diff = revision.get("diff_from_previous")
        if diff is not None:
            _validate_relative_artifact_path(diff, expected_prefix="diffs")
        if not isinstance(revision["sections"], list):
            raise ProjectError(f"Revision {index} sections must be a list.")
        for section_index, section in enumerate(revision["sections"], start=1):
            if not isinstance(section, dict) or set(section) != {
                "name",
                "start",
                "end",
                "report",
            }:
                raise ProjectError(
                    f"Revision {index} section {section_index} has an invalid field set."
                )
            _normalize_sections(
                [{"name": section["name"], "start": section["start"], "end": section["end"]}]
            )
            _validate_relative_artifact_path(
                section["report"], expected_prefix="sections", expected_id=revision_id
            )


def _validate_relative_artifact_path(
    value: Any,
    *,
    expected_prefix: str,
    expected_id: str | None = None,
) -> None:
    if not isinstance(value, str) or not value:
        raise ProjectError("Project artifact path is missing or invalid.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ProjectError(f"Project artifact path must remain inside {expected_prefix!r}.")
    if path.parts[0] != expected_prefix or len(path.parts) not in {2, 3}:
        raise ProjectError(f"Project artifact path must remain inside {expected_prefix!r}.")
    if expected_id is not None and (len(path.parts) < 2 or path.parts[1] != expected_id):
        raise ProjectError("Project artifact path does not match its revision ID.")


def _validate_revision_artifacts(root: Path, config: dict[str, Any]) -> None:
    for revision in config["revisions"]:
        report = root / revision["report"]
        if not (report / "summary.json").is_file() or not (report / "report.html").is_file():
            raise ProjectError(f"Revision {revision['label']!r} is missing report artifacts.")
        diff = revision.get("diff_from_previous")
        if diff and not (root / diff / "revision_diff.html").is_file():
            raise ProjectError(f"Revision {revision['label']!r} is missing its prior diff.")
        for section in revision.get("sections", []):
            if not isinstance(section, dict) or not (root / str(section.get("report", "")) / "report.html").is_file():
                raise ProjectError(f"Revision {revision['label']!r} is missing a section report.")


def _next_revision_id(revisions: list[dict[str, Any]], label: str) -> str:
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", label.lower())).strip("-")
    slug = slug or "revision"
    used = {entry["id"] for entry in revisions}
    counter = len(revisions) + 1
    while True:
        candidate = f"{counter:03d}-{slug}"
        if candidate not in used:
            return candidate
        counter += 1


def _section_slug(name: str, start: float, end: float | None) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip()).strip("_") or "section"
    start_label = f"{start:07.3f}".replace(".", "p")
    end_label = "EOF" if end is None else f"{end:07.3f}".replace(".", "p")
    return f"{start_label}_{end_label}_{safe_name}"


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _remove_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _remove_empty_project_containers(root: Path) -> None:
    for name in ("reports", "sections", "diffs"):
        path = root / name
        with suppress(OSError):
            path.rmdir()
