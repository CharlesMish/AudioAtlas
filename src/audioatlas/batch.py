"""Batch/catalog orchestration for AudioAtlas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audioatlas.catalog_report import (
    build_catalog_summary,
    track_record_from_run,
    write_catalog_html,
    write_catalog_md,
    write_catalog_summary_json,
)
from audioatlas.config import AnalysisConfig
from audioatlas.errors import AudioAtlasError
from audioatlas.graphs import all_graphs
from audioatlas.graphs.selection import GraphSelection
from audioatlas.output import (
    CATALOG_FILENAMES,
    OUTPUT_MARKER_FILENAME,
    SINGLE_REPORT_FILENAMES,
    publish_staged_output,
    staged_output_directory,
    write_output_manifest,
)
from audioatlas.pipeline import analyze_file

SUPPORTED_AUDIO_EXTENSIONS = {".aif", ".aiff", ".flac", ".mp3", ".ogg", ".wav", ".wave"}


@dataclass(frozen=True)
class BatchRunResult:
    """Paths and in-memory summary produced by a batch run."""

    out_dir: Path
    catalog_summary_path: Path
    catalog_md_path: Path
    catalog_html_path: Path
    catalog: dict[str, Any]


def analyze_folder(
    input_folder: str | Path,
    out_dir: str | Path,
    *,
    config: AnalysisConfig | None = None,
    max_duration_seconds: float | None = None,
    theme_name: str | None = None,
    selection: GraphSelection | None = None,
    strict: bool = False,
    include_local_paths: bool = False,
) -> BatchRunResult:
    """Analyze supported audio files in a folder and write catalog reports.

    Decode failures are recorded in ``skipped_files`` and do not discard
    successful track reports. Set ``strict`` to stop on the first bad file.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    if selection is not None:
        selection.resolve(all_graphs())
    input_path = Path(input_folder)
    if not input_path.exists():
        raise ValueError(f"Input folder does not exist: {input_path}")
    if not input_path.is_dir():
        raise ValueError(f"Input path is not a folder: {input_path}")
    out = Path(out_dir)

    tracks: list[dict[str, Any]] = []
    skipped_files: list[dict[str, str]] = []
    used_names: set[str] = set()
    track_directories: list[str] = []

    with staged_output_directory(out) as staging:
        for path in sorted(input_path.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                skipped_files.append(
                    {
                        "filename": path.name,
                        "reason": "unsupported file extension",
                        "status": "skipped",
                    }
                )
                continue

            track_dir_name = _unique_track_dir_name(_safe_stem(path.stem), used_names)
            track_out = staging / track_dir_name
            try:
                run = analyze_file(
                    path,
                    track_out,
                    config=cfg,
                    max_duration_seconds=max_duration_seconds,
                    theme_name=theme_name,
                    selection=selection,
                    include_local_paths=include_local_paths,
                )
            except (AudioAtlasError, ValueError) as exc:
                if strict:
                    raise
                skipped_files.append(
                    {
                        "filename": path.name,
                        "reason": str(exc),
                        "status": "analysis_failed",
                    }
                )
                continue
            track_directories.append(track_dir_name)
            tracks.append(
                track_record_from_run(
                    filename=path.name,
                    report_path=str((Path(track_dir_name) / "report.html").as_posix()),
                    summary=run.summary,
                    findings=run.findings,
                )
            )

        catalog = build_catalog_summary(
            input_folder=input_path,
            output_folder=out,
            tracks=tracks,
            skipped_files=skipped_files,
            include_local_paths=include_local_paths,
        )
        write_catalog_summary_json(catalog, staging)
        write_catalog_md(catalog, staging)
        write_catalog_html(catalog, staging, theme_name=theme_name)
        write_output_manifest(
            staging,
            kind="batch-catalog",
            generated_files=[*CATALOG_FILENAMES, OUTPUT_MARKER_FILENAME],
            generated_directories=track_directories,
        )
        # Clear only known single-report roots/plots if the same destination is
        # intentionally repurposed as a catalog. Human files remain untouched.
        owned_names = set(CATALOG_FILENAMES | SINGLE_REPORT_FILENAMES)
        owned_names.update(graph.filename for graph in all_graphs())
        publish_staged_output(staging, out, owned_filenames=owned_names)

    return BatchRunResult(
        out_dir=out,
        catalog_summary_path=out / "catalog_summary.json",
        catalog_md_path=out / "catalog.md",
        catalog_html_path=out / "catalog.html",
        catalog=catalog,
    )


def _safe_stem(stem: str) -> str:
    chars = [char if char.isalnum() or char in ("-", "_") else "-" for char in stem]
    value = "".join(chars).strip("-_")
    return value or "track"


def _unique_track_dir_name(stem: str, used_names: set[str]) -> str:
    candidate = stem
    index = 2
    while candidate in used_names:
        candidate = f"{stem}-{index}"
        index += 1
    used_names.add(candidate)
    return candidate
