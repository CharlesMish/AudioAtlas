"""Safe publication helpers for generated AudioAtlas report folders."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout
from platformdirs import user_cache_path

from audioatlas import __version__
from audioatlas.errors import OutputBusyError, OutputOwnershipError

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
SOURCE_BINDING_FORMAT = "audioatlas-source-binding"
SOURCE_BINDING_VERSION = 1
SOURCE_BINDING_ALGORITHM = "sha256"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_GENERATED_FILENAMES_BY_KIND = {
    "single-track-report": frozenset(SINGLE_REPORT_FILENAMES | PLOT_FILENAMES),
    "batch-catalog": CATALOG_FILENAMES,
    "same-track-revision-diff": REVISION_DIFF_FILENAMES,
    "song-project": PROJECT_FILENAMES,
}


@dataclass(frozen=True)
class OutputTransaction:
    """Opaque proof that one canonical output destination is locked."""

    destination: Path


@dataclass(frozen=True)
class SourceBinding:
    """Opaque source identity serialized without its local filesystem fields."""

    digest: str
    source_identity: tuple[int, int, int, int] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if not _SHA256_HEX.fullmatch(self.digest):
            raise ValueError("Source binding digest must be lowercase SHA-256 hex")

    def to_manifest_dict(self) -> dict[str, object]:
        return {
            "format": SOURCE_BINDING_FORMAT,
            "version": SOURCE_BINDING_VERSION,
            "algorithm": SOURCE_BINDING_ALGORITHM,
            "digest": self.digest,
        }


@dataclass(frozen=True)
class _ManifestOwnership:
    """Validated file and directory declarations from one output manifest."""

    kind: str
    files: frozenset[str]
    directories: frozenset[str]
    source_binding_digest: str | None


@contextmanager
def output_transaction(destination: str | Path) -> Iterator[OutputTransaction]:
    """Serialize one output destination across threads and processes."""

    target = Path(destination).expanduser()
    if target.is_symlink():
        raise OutputOwnershipError("Refusing to publish through an output-folder symlink.")
    canonical = target.resolve(strict=False)
    # normcase is a no-op on POSIX and folds case/separators on Windows, where
    # spelling variants of one not-yet-created NTFS destination must share a lock.
    digest = _output_lock_digest(canonical)
    user_key = str(getattr(os, "getuid", lambda: "user")())
    guard_root = Path(tempfile.gettempdir()) / f"audioatlas-output-locks-{user_key}"
    try:
        guard_root.mkdir(parents=True, exist_ok=True)
        guard_lock = FileLock(guard_root / f"{digest}.lock", timeout=0)
        guard_lock.acquire()
    except Timeout as exc:
        raise _output_busy_error() from exc
    except OSError as exc:
        raise OutputBusyError(
            "AudioAtlas could not create its local output lock. "
            "Check the account's temporary-folder permissions and try again."
        ) from exc

    cache_lock: FileLock | None = None
    try:
        cache_root = user_cache_path("AudioAtlas", appauthor=False) / "output-locks"
        try:
            cache_root.mkdir(parents=True, exist_ok=True)
            cache_lock = FileLock(cache_root / f"{digest}.lock", timeout=0)
            cache_lock.acquire()
        except Timeout as exc:
            raise _output_busy_error() from exc
        except OSError:
            # Restricted application contexts can expose the cache directory
            # while denying new files inside it. The per-user guard remains the
            # common serialization point for all current AudioAtlas processes.
            cache_lock = None

        _validate_output_root(target)
        yield OutputTransaction(destination=canonical)
    finally:
        if cache_lock is not None:
            cache_lock.release()
        guard_lock.release()


def _output_busy_error() -> OutputBusyError:
    return OutputBusyError(
        "Another AudioAtlas operation is already updating this report. "
        "Wait for it to finish, then try again."
    )


def _output_lock_digest(canonical: Path) -> str:
    lock_identity = os.path.normcase(str(canonical))
    return hashlib.sha256(lock_identity.encode("utf-8")).hexdigest()


@contextmanager
def staged_output_directory(destination: str | Path) -> Iterator[Path]:
    """Yield a sibling staging directory and clean it after use.

    The destination is not touched until all analysis artifacts have been
    rendered successfully. This preserves a previous complete report when a
    decoder, analysis, plotting, or writer step fails.
    """

    target = Path(destination).expanduser()
    if target.is_symlink():
        raise OutputOwnershipError("Refusing to stage through an output-folder symlink.")
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
    source_binding: SourceBinding | None = None,
) -> Path:
    """Write the ownership manifest included in every generated report folder."""

    out = Path(staging) / OUTPUT_MARKER_FILENAME
    payload: dict[str, Any] = {
        "format": "audioatlas-output-manifest",
        "manifest_version": 1,
        "audioatlas_version": __version__,
        "kind": kind,
        "generated_files": sorted(generated_files),
        "generated_directories": sorted(generated_directories or []),
    }
    if source_binding is not None:
        payload["source_binding"] = source_binding.to_manifest_dict()
    _manifest_ownership(payload, context="Output manifest")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def publish_staged_output(
    staging: str | Path,
    destination: str | Path,
    *,
    allowed_staged_filenames: set[str],
    transaction: OutputTransaction | None = None,
) -> None:
    """Publish a completed staging directory while preserving unknown files.

    ``allowed_staged_filenames`` constrains what the current producer may stage;
    it does not claim existing destination files. Prior-file authority comes
    only from the destination's validated ownership manifest. Existing owned
    artifacts are first moved into a sibling backup; if any publication step
    fails, the previous generated set is restored.
    """

    source = Path(staging)
    target = Path(destination).expanduser()
    if transaction is None:
        with output_transaction(target) as acquired:
            publish_staged_output(
                source,
                target,
                allowed_staged_filenames=allowed_staged_filenames,
                transaction=acquired,
            )
        return
    if transaction.destination != target.resolve(strict=False):
        raise ValueError("Output transaction does not match the publication destination")
    if source.is_symlink():
        raise OutputOwnershipError("Refusing to publish from a staging-folder symlink.")
    _validate_output_root(target)
    if not source.is_dir():
        raise ValueError(f"Staging path is not a folder: {source}")
    if source.resolve() == target.resolve():
        raise ValueError("Staging and destination folders must be different")
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
    staged_manifest = _validate_staging_manifest(
        source,
        staged_names,
        staged_directories,
        allowed_staged_filenames=allowed_staged_filenames,
    )
    if (
        (target / PROJECT_CONFIG_FILENAME).is_file()
        and staged_manifest.kind != "song-project"
    ):
        raise OutputOwnershipError(
            "Refusing to publish a report into an AudioAtlas song-project root. "
            "Choose a separate output folder."
        )

    previous = _previous_owned_entries(target)
    if (
        staged_manifest.kind == "single-track-report"
        and staged_manifest.source_binding_digest is not None
        and previous.kind == "single-track-report"
        and previous.source_binding_digest != staged_manifest.source_binding_digest
    ):
        raise OutputOwnershipError(
            "Refusing to replace a report created for a different or ambiguously "
            "bound source. Choose a different output folder."
        )

    # Validate every predictable collision before deleting or replacing
    # anything. AudioAtlas may update directories it can independently
    # recognize as its own output, but it must never erase an unrelated folder
    # merely because a track slug happens to match that folder's name.
    for filename in staged_names:
        destination_path = target / filename
        if destination_path.is_symlink():
            raise OutputOwnershipError(
                "Refusing to replace an output-file symlink: "
                f"{filename!r}"
            )
        if destination_path.is_dir():
            raise OutputOwnershipError(
                "Refusing to replace an output directory with a file: "
                f"{filename!r}"
            )
        if destination_path.exists() and filename not in previous.files:
            raise OutputOwnershipError(
                "Refusing to replace an unowned output file: "
                f"{filename!r}. Choose a different output folder or move the file."
            )

    for filename in previous.files:
        destination_path = target / filename
        if destination_path.is_symlink() or (
            destination_path.exists() and not destination_path.is_file()
        ):
            raise OutputOwnershipError(
                "The previous ownership manifest declares a file with an unsafe "
                f"destination type: {filename!r}"
            )

    for directory_name in staged_directories:
        destination_path = target / directory_name
        if (
            destination_path.exists() or destination_path.is_symlink()
        ) and directory_name not in previous.directories:
            raise OutputOwnershipError(
                "Refusing to replace an unowned output directory: "
                f"{directory_name!r}"
            )

    affected_files = set(previous.files) | staged_names | {OUTPUT_MARKER_FILENAME}
    affected_directories = set(previous.directories) | staged_directories
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
    *,
    allowed_staged_filenames: set[str],
) -> _ManifestOwnership:
    """Require the staging manifest to describe the staged artifact set."""

    manifest = _read_output_manifest(source / OUTPUT_MARKER_FILENAME)
    if manifest is None:
        raise ValueError("Staging folder lacks a recognized AudioAtlas output manifest")
    ownership = _manifest_ownership(manifest, context="Staging manifest")
    if "source_binding" in manifest and ownership.source_binding_digest is None:
        raise ValueError("Staging manifest contains an unsupported or malformed source binding")
    _validate_allowed_staged_filenames(allowed_staged_filenames)
    allowed = allowed_staged_filenames | {OUTPUT_MARKER_FILENAME}
    unexpected_files = staged_names - allowed
    if unexpected_files:
        joined = ", ".join(repr(name) for name in sorted(unexpected_files))
        raise ValueError(f"Refusing to publish unowned staged file(s): {joined}")

    if ownership.files != staged_names:
        raise ValueError(
            "Staging manifest does not match generated files: "
            f"declared={sorted(ownership.files)!r}, actual={sorted(staged_names)!r}"
        )
    if ownership.directories != staged_directories:
        raise ValueError(
            "Staging manifest does not match generated directories: "
            f"declared={sorted(ownership.directories)!r}, "
            f"actual={sorted(staged_directories)!r}"
        )
    return ownership


def _validate_output_root(target: Path) -> None:
    """Refuse a destination that cannot be safely recognized before work."""

    if target.is_symlink():
        raise OutputOwnershipError("Refusing to publish through an output-folder symlink.")
    if target.exists() and not target.is_dir():
        raise OutputOwnershipError("Output path exists and is not a folder.")
    if not target.is_dir() or not any(target.iterdir()):
        return
    marker = target / OUTPUT_MARKER_FILENAME
    if marker.exists() or marker.is_symlink():
        _previous_owned_entries(target)
        return
    legacy_catalog = bool(_legacy_owned_directories(target))
    legacy_project = (target / PROJECT_CONFIG_FILENAME).is_file()
    if not legacy_catalog and not legacy_project:
        raise OutputOwnershipError(
            "The selected output folder is not owned by AudioAtlas. "
            "Choose an empty folder or a different report location."
        )


def _validate_allowed_staged_filenames(names: set[str]) -> None:
    """Validate a producer's allowlist without turning it into prior ownership."""

    invalid = {
        name
        for name in names
        if not isinstance(name, str)
        or not _is_simple_name(name)
        or name not in ALL_GENERATED_FILENAMES
    }
    if invalid:
        joined = ", ".join(repr(name) for name in sorted(invalid, key=repr))
        raise ValueError(f"Unsupported staged output filename(s): {joined}")


def _manifest_ownership(
    manifest: dict[str, Any],
    *,
    context: str,
) -> _ManifestOwnership:
    """Validate declarations without inferring ownership from global names."""

    kind = manifest.get("kind")
    if not isinstance(kind, str) or kind not in _GENERATED_FILENAMES_BY_KIND:
        raise ValueError(f"{context} has an unsupported output kind: {kind!r}")
    allowed_files = _GENERATED_FILENAMES_BY_KIND[kind] | {OUTPUT_MARKER_FILENAME}
    files = _manifest_name_set(
        manifest.get("generated_files"),
        "files",
        context=context,
        allowed_names=allowed_files,
    )
    directories = _manifest_name_set(
        manifest.get("generated_directories"),
        "directories",
        context=context,
        directory_names=True,
    )
    if directories and kind != "batch-catalog":
        raise ValueError(
            f"{context} kind {kind!r} cannot declare generated directories"
        )

    files.add(OUTPUT_MARKER_FILENAME)
    file_keys = {name.casefold() for name in files}
    directory_keys = {name.casefold() for name in directories}
    overlap = file_keys & directory_keys
    if overlap:
        raise ValueError(
            f"{context} ambiguously declares the same file and directory name: "
            f"{sorted(overlap)!r}"
        )
    return _ManifestOwnership(
        kind=kind,
        files=frozenset(files),
        directories=frozenset(directories),
        source_binding_digest=_source_binding_digest(manifest.get("source_binding")),
    )


def manifest_matches_source_binding(
    manifest: dict[str, Any], source_binding: SourceBinding
) -> bool:
    """Return whether a manifest has this exact supported source binding."""

    return _source_binding_digest(manifest.get("source_binding")) == source_binding.digest


def _source_binding_digest(value: Any) -> str | None:
    """Return a supported binding digest; reject legacy, future, or malformed values."""

    if not isinstance(value, dict) or set(value) != {
        "format",
        "version",
        "algorithm",
        "digest",
    }:
        return None
    if value.get("format") != SOURCE_BINDING_FORMAT:
        return None
    if value.get("version") != SOURCE_BINDING_VERSION:
        return None
    if value.get("algorithm") != SOURCE_BINDING_ALGORITHM:
        return None
    digest = value.get("digest")
    if not isinstance(digest, str) or not _SHA256_HEX.fullmatch(digest):
        return None
    return digest


def _manifest_name_set(
    value: Any,
    label: str,
    *,
    context: str,
    allowed_names: frozenset[str] | None = None,
    directory_names: bool = False,
) -> set[str]:
    """Validate a manifest filename/directory list and reject ambiguity."""

    if not isinstance(value, list):
        raise ValueError(f"{context} generated_{label} must be a list")
    names: set[str] = set()
    normalized_names: set[str] = set()
    for item in value:
        valid_name = isinstance(item, str) and _is_simple_name(item)
        if directory_names:
            valid_name = valid_name and _is_supported_directory_name(item)
        elif allowed_names is not None:
            valid_name = valid_name and item in allowed_names
        if not valid_name:
            raise ValueError(
                f"{context} contains an invalid or unsupported generated_{label} entry: "
                f"{item!r}"
            )
        normalized = item.casefold()
        if normalized in normalized_names:
            raise ValueError(
                f"{context} contains a duplicate or ambiguous generated_{label} "
                f"entry: {item!r}"
            )
        names.add(item)
        normalized_names.add(normalized)
    return names


def _is_simple_name(name: str) -> bool:
    """Return whether a name is one cross-platform path component."""

    return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name


def _is_supported_directory_name(name: str) -> bool:
    """Match the direct-child names emitted by the batch slug generator."""

    return (
        name == name.strip("-_")
        and all(character.isalnum() or character in {"-", "_"} for character in name)
    )


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


def _previous_owned_entries(target: Path) -> _ManifestOwnership:
    """Return only entries authorized by a validated previous manifest."""

    marker = target / OUTPUT_MARKER_FILENAME
    if not marker.exists() and not marker.is_symlink():
        legacy_directories = _legacy_owned_directories(target)
        return _ManifestOwnership(
            kind="batch-catalog" if legacy_directories else "",
            files=frozenset(),
            directories=frozenset(legacy_directories),
            source_binding_digest=None,
        )

    payload = _read_output_manifest(marker)
    if payload is None:
        raise OutputOwnershipError(
            "The existing AudioAtlas ownership manifest is unreadable or unrecognized. "
            "Choose a different output folder."
        )
    try:
        declared = _manifest_ownership(payload, context="Existing output manifest")
    except ValueError as exc:
        raise OutputOwnershipError(
            "The existing AudioAtlas ownership manifest has unsafe or malformed "
            f"declarations: {exc}"
        ) from exc

    owned_directories: set[str] = set()
    for name in declared.directories:
        report_dir = target / name
        if report_dir.is_symlink():
            raise OutputOwnershipError(
                "The previous ownership manifest declares a directory symlink: "
                f"{name!r}"
            )
        if not report_dir.exists():
            continue
        if not report_dir.is_dir():
            raise OutputOwnershipError(
                "The previous ownership manifest declares a directory with an unsafe "
                f"destination type: {name!r}"
            )
        child_marker = report_dir / OUTPUT_MARKER_FILENAME
        child_manifest = _read_output_manifest(child_marker)
        if child_manifest is None:
            continue
        try:
            child = _manifest_ownership(
                child_manifest,
                context=f"Child output manifest for {name!r}",
            )
        except ValueError as exc:
            raise OutputOwnershipError(
                "A child AudioAtlas ownership manifest has unsafe or malformed "
                f"declarations: {exc}"
            ) from exc
        if child.kind == "single-track-report":
            owned_directories.add(name)

    return _ManifestOwnership(
        kind=declared.kind,
        files=declared.files,
        directories=frozenset(owned_directories),
        source_binding_digest=declared.source_binding_digest,
    )


def _legacy_owned_directories(target: Path) -> set[str]:
    """Return narrowly recognized pre-manifest catalog report directories."""

    # Compatibility recovery never grants authority over root files. A directory
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
