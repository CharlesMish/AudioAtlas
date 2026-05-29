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
from audioatlas.pipeline import analyze_file

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3"}


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
) -> BatchRunResult:
    """Analyze supported audio files in a folder and write catalog reports."""

    cfg = config or AnalysisConfig()
    cfg.validate()
    input_path = Path(input_folder)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    tracks: list[dict[str, Any]] = []
    skipped_files: list[dict[str, str]] = []
    used_names: set[str] = set()

    for path in sorted(input_path.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            skipped_files.append(
                {"filename": path.name, "reason": "unsupported file extension"}
            )
            continue

        track_dir_name = _unique_track_dir_name(_safe_stem(path.stem), used_names)
        track_out = out / track_dir_name
        run = analyze_file(
            path,
            track_out,
            config=cfg,
            max_duration_seconds=max_duration_seconds,
        )
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
    )
    summary_path = write_catalog_summary_json(catalog, out)
    md_path = write_catalog_md(catalog, out)
    html_path = write_catalog_html(catalog, out)
    return BatchRunResult(
        out_dir=out,
        catalog_summary_path=summary_path,
        catalog_md_path=md_path,
        catalog_html_path=html_path,
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
