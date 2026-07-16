"""Safe publication helpers for generated AudioAtlas report folders."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from audioatlas import __version__

OUTPUT_MARKER_FILENAME = ".audioatlas-output.json"
PROJECT_CONFIG_FILENAME = "audioatlas-project.yaml"
SINGLE_REPORT_FILENAMES = frozenset(
    {"summary.json", "findings.json", "report.md", "report.html"}
)
CATALOG_FILENAMES = frozenset(
    {"catalog_summary.json", "catalog.md", "catalog.html"}
)
REVISION_DIFF_FILENAMES = frozenset(
    {"revision_diff.json", "revision_diff.md", "revision_diff.html"}
)
PROJECT_FILENAMES = frozenset(
    {PROJECT_CONFIG_FILENAME, "project.json", "project.md", "project.html"}
)
ROOT_GENERATED_FILENAMES = frozenset(
    SINGLE_REPORT_FILENAMES | CATALOG_FILENAMES | REVISION_DIFF_FILENAMES | PROJECT_FILENAMES
)
# Kept lightweight so report publication and the diff command can clean stale
# plots without importing Matplotlib. ``tests/test_graph_registry.py`` locks
# this set to the graph registry.
PLOT_FILENAMES = frozenset(
    {
        "waveform_rms.png",
        "rms_timeline.png",
        "crest_factor_timeline.png",
        "log_spectrogram.png",
        "average_spectrum.png",
        "sample_histogram.png",
        "stereo_correlation.png",
        "mid_side_energy.png",
        "spectral_shape.png",
        "band_energy_timeline.png",
        "onset_density.png",
        "chroma_cqt.png",
        "short_term_lufs.png",
        "peak_timeline.png",
        "peak_vs_rms.png",
        "rms_histogram.png",
        "stereo_correlation_histogram.png",
    }
)
ALL_GENERATED_FILENAMES = frozenset(ROOT_GENERATED_FILENAMES | PLOT_FILENAMES)


@contextmanager
def staged_output_directory(destination: str | Path) -> Iterator[Path]:
    """Yield a sibling staging directory and clean it after use.

    The destination is not touched until all analysis artifacts have been
    rendered successfully. This preserves a previous complete report when a
    decoder, analysis, plotting, or writer step fails.
    """

    target = Path(destination)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.audioatlas-", dir=parent))
    try:
        yield staging
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def write_output_manifest(
    staging: str | Path,
    *,
    kind: str,
    generated_files: list[str],
    generated_directories: list[str] | None = None,
) -> Path:
    """Write the ownership manifest included in every generated report folder."""

    out = Path(staging) / OUTPUT_MARKER_FILENAME
    payload: dict[str, Any] = {
        "format": "audioatlas-output-manifest",
        "manifest_version": 1,
        "audioatlas_version": __version__,
        "kind": kind,
        "generated_files": sorted(dict.fromkeys(generated_files)),
        "generated_directories": sorted(
            dict.fromkeys(generated_directories or [])
        ),
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def publish_staged_output(
    staging: str | Path,
    destination: str | Path,
    *,
    owned_filenames: set[str],
) -> None:
    """Publish a completed staging directory while preserving unknown files.

    Known AudioAtlas filenames that are absent from the new run are removed,
    which prevents a full-to-compact rerun from leaving stale plots. Files not
    owned by AudioAtlas are left untouched. Existing generated artifacts are
    first moved into a sibling backup; if any individual publication step
    fails, the previous generated set is restored.
    """

    source = Path(staging)
    target = Path(destination)
    if not source.is_dir():
        raise ValueError(f"Staging path is not a folder: {source}")
    if source.resolve() == target.resolve():
        raise ValueError("Staging and destination folders must be different")
    if target.exists() and not target.is_dir():
        raise ValueError(f"Output path exists and is not a folder: {target}")
    target.mkdir(parents=True, exist_ok=True)

    source_entries = sorted(source.iterdir(), key=lambda item: item.name)
    for path in source_entries:
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(
                "Staging contains an unsupported filesystem entry: "
                f"{path.name!r}"
            )

    staged_names = {path.name for path in source_entries if path.is_file()}
    staged_directories = {path.name for path in source_entries if path.is_dir()}
    _validate_staging_manifest(source, staged_names, staged_directories)
    staged_manifest = _read_output_manifest(source / OUTPUT_MARKER_FILENAME)
    if (
        (target / PROJECT_CONFIG_FILENAME).is_file()
        and (staged_manifest or {}).get("kind") != "song-project"
    ):
        raise ValueError(
            "Refusing to publish a report into an AudioAtlas song-project root. "
            "Choose a separate output folder."
        )

    allowed_staged_files = owned_filenames | {OUTPUT_MARKER_FILENAME}
    unexpected_files = staged_names - allowed_staged_files
    if unexpected_files:
        joined = ", ".join(repr(name) for name in sorted(unexpected_files))
        raise ValueError(f"Refusing to publish unowned staged file(s): {joined}")

    invalid_owned_names = {
        name
        for name in allowed_staged_files
        if not name or Path(name).name != name
    }
    if invalid_owned_names:
        joined = ", ".join(repr(name) for name in sorted(invalid_owned_names))
        raise ValueError(f"Owned output names must be simple filenames: {joined}")

    previous_directories = _previous_owned_directories(target)

    # Validate every predictable collision before deleting or replacing
    # anything. AudioAtlas may update directories it can independently
    # recognize as its own output, but it must never erase an unrelated folder
    # merely because a track slug happens to match that folder's name.
    for filename in staged_names:
        destination_path = target / filename
        if destination_path.is_dir() and not destination_path.is_symlink():
            raise ValueError(
                "Refusing to replace an output directory with a file: "
                f"{filename!r}"
            )

    for directory_name in staged_directories:
        destination_path = target / directory_name
        if (
            destination_path.exists() or destination_path.is_symlink()
        ) and directory_name not in previous_directories:
            raise ValueError(
                "Refusing to replace an unowned output directory: "
                f"{directory_name!r}"
            )

    affected_files = allowed_staged_files | staged_names
    affected_directories = previous_directories | staged_directories
    backup = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent)
    )
    backup_files = backup / "files"
    backup_directories = backup / "directories"
    backup_files.mkdir()
    backup_directories.mkdir()

    backed_up_files: set[str] = set()
    backed_up_directories: set[str] = set()
    published_files: set[str] = set()
    published_directories: set[str] = set()
    preserve_backup = False

    try:
        # Move the entire generated set aside before publishing any new item.
        # This gives the multi-file report an application-level rollback path
        # while retaining same-filesystem atomic renames for each item.
        for filename in sorted(affected_files):
            old_path = target / filename
            if old_path.is_symlink() or old_path.is_file():
                os.replace(old_path, backup_files / filename)
                backed_up_files.add(filename)

        for directory_name in sorted(affected_directories):
            old_path = target / directory_name
            if old_path.is_symlink() or old_path.is_dir():
                os.replace(old_path, backup_directories / directory_name)
                backed_up_directories.add(directory_name)

        for path in source_entries:
            destination_path = target / path.name
            os.replace(path, destination_path)
            if destination_path.is_dir() and not destination_path.is_symlink():
                published_directories.add(path.name)
            else:
                published_files.add(path.name)
    except BaseException as publish_error:
        rollback_errors = _rollback_publication(
            target=target,
            backup_files=backup_files,
            backup_directories=backup_directories,
            backed_up_files=backed_up_files,
            backed_up_directories=backed_up_directories,
            published_files=published_files,
            published_directories=published_directories,
        )
        if rollback_errors:
            preserve_backup = True
            details = "; ".join(rollback_errors)
            raise RuntimeError(
                "AudioAtlas publication failed and rollback was incomplete. "
                f"Recovery files were preserved at {backup}: {details}"
            ) from publish_error
        raise
    finally:
        if not preserve_backup:
            shutil.rmtree(backup, ignore_errors=True)


def _validate_staging_manifest(
    source: Path,
    staged_names: set[str],
    staged_directories: set[str],
) -> None:
    """Require the staging manifest to describe the staged artifact set."""

    manifest = _read_output_manifest(source / OUTPUT_MARKER_FILENAME)
    if manifest is None:
        raise ValueError("Staging folder lacks a recognized AudioAtlas output manifest")

    declared_files = _manifest_name_set(manifest.get("generated_files"), "files")
    declared_directories = _manifest_name_set(
        manifest.get("generated_directories", []), "directories"
    )
    declared_files.add(OUTPUT_MARKER_FILENAME)

    if declared_files != staged_names:
        raise ValueError(
            "Staging manifest does not match generated files: "
            f"declared={sorted(declared_files)!r}, actual={sorted(staged_names)!r}"
        )
    if declared_directories != staged_directories:
        raise ValueError(
            "Staging manifest does not match generated directories: "
            f"declared={sorted(declared_directories)!r}, "
            f"actual={sorted(staged_directories)!r}"
        )


def _manifest_name_set(value: Any, label: str) -> set[str]:
    """Validate a manifest filename/directory list and return unique names."""

    if not isinstance(value, list):
        raise ValueError(f"Staging manifest generated_{label} must be a list")
    names: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item or Path(item).name != item:
            raise ValueError(
                f"Staging manifest contains an invalid generated_{label} entry: "
                f"{item!r}"
            )
        names.add(item)
    return names


def _rollback_publication(
    *,
    target: Path,
    backup_files: Path,
    backup_directories: Path,
    backed_up_files: set[str],
    backed_up_directories: set[str],
    published_files: set[str],
    published_directories: set[str],
) -> list[str]:
    """Remove partially published items and restore the prior generated set."""

    errors: list[str] = []
    for name in sorted(published_directories):
        try:
            _remove_path(target / name)
        except OSError as exc:
            errors.append(f"could not remove published directory {name!r}: {exc}")
    for name in sorted(published_files):
        try:
            _remove_path(target / name)
        except OSError as exc:
            errors.append(f"could not remove published file {name!r}: {exc}")

    for name in sorted(backed_up_directories):
        source_path = backup_directories / name
        destination_path = target / name
        try:
            if destination_path.exists() or destination_path.is_symlink():
                raise OSError("destination became occupied during rollback")
            os.replace(source_path, destination_path)
        except OSError as exc:
            errors.append(f"could not restore directory {name!r}: {exc}")
    for name in sorted(backed_up_files):
        source_path = backup_files / name
        destination_path = target / name
        try:
            if destination_path.exists() or destination_path.is_symlink():
                raise OSError("destination became occupied during rollback")
            os.replace(source_path, destination_path)
        except OSError as exc:
            errors.append(f"could not restore file {name!r}: {exc}")
    return errors


def _remove_path(path: Path) -> None:
    """Remove one file, symlink, or directory if it exists."""

    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _previous_owned_directories(target: Path) -> set[str]:
    """Read directories demonstrably owned by an earlier AudioAtlas batch."""

    marker = target / OUTPUT_MARKER_FILENAME
    if marker.exists():
        payload = _read_output_manifest(marker)
        if payload is None or payload.get("kind") != "batch-catalog":
            return set()
        values = payload.get("generated_directories")
        if not isinstance(values, list):
            return set()
        owned: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value or Path(value).name != value:
                continue
            report_dir = target / value
            if report_dir.is_symlink() or not report_dir.is_dir():
                continue
            child_manifest = _read_output_manifest(
                report_dir / OUTPUT_MARKER_FILENAME
            )
            if child_manifest is not None and child_manifest.get("kind") == (
                "single-track-report"
            ):
                owned.add(value)
        return owned

    # Narrow compatibility recovery for legacy pre-manifest catalogs. A directory
    # is adopted only when the catalog has the exact old schema, its report path
    # is one direct child, and the expected AudioAtlas report files are present.
    catalog_path = target / "catalog_summary.json"
    if not catalog_path.is_file():
        return set()
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if (
        not isinstance(catalog, dict)
        or catalog.get("schema_version") != "0.1.0"
        or not isinstance(catalog.get("tracks"), list)
    ):
        return set()

    out: set[str] = set()
    for track in catalog["tracks"]:
        if not isinstance(track, dict):
            continue
        report_path = track.get("report_path")
        if not isinstance(report_path, str):
            continue
        parts = Path(report_path).parts
        if len(parts) != 2 or parts[1] != "report.html":
            continue
        directory_name = parts[0]
        if not directory_name or Path(directory_name).name != directory_name:
            continue
        report_dir = target / directory_name
        expected = ("report.html", "summary.json", "findings.json")
        if report_dir.is_dir() and all((report_dir / name).is_file() for name in expected):
            out.add(directory_name)
    return out


def _read_output_manifest(path: Path) -> dict[str, Any] | None:
    """Return a recognized AudioAtlas ownership manifest, otherwise ``None``."""

    if path.is_symlink() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("format") != "audioatlas-output-manifest":
        return None
    if payload.get("manifest_version") != 1:
        return None
    return payload


def read_output_manifest(path: str | Path) -> dict[str, Any] | None:
    """Return a recognized ownership manifest without exposing parser details."""

    return _read_output_manifest(Path(path))
