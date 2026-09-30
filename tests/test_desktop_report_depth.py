"""Real desktop report presets retain the existing pipeline and output contracts."""

from __future__ import annotations

import json
import shutil
from functools import partial
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

import audioatlas.app_core as app_core
from audioatlas.config import AnalysisConfig
from audioatlas.errors import AnalysisCancelled
from audioatlas.graphs import GraphSelection
from audioatlas.output import EVIDENCE_REPORT_FILENAMES, OUTPUT_MARKER_FILENAME
from audioatlas.pipeline import analyze_file
from audioatlas.run_contract import AnalysisProgress, AnalysisRunResult, CancellationToken

_SOURCE = Path(__file__).parent / "fixtures" / "sine_1k_-6dbfs_2s.wav"
_PRESETS = [
    ("overview", "compact", "compact", 4),
    ("standard", "full", "standard", 14),
    ("detailed", "full", "full", 18),
]
_CONFIG = AnalysisConfig(
    n_fft=512,
    hop_length=128,
    rms_frame_length=512,
    welch_nperseg=512,
    true_peak_oversample=1,
)


@pytest.fixture(scope="module")
def depth_reports(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, tuple[AnalysisRunResult, AnalysisRunResult]]:
    """Share immutable reports so numerical parity needs only six pipeline runs."""
    root = tmp_path_factory.mktemp("desktop-depth")
    reports = {}
    with pytest.MonkeyPatch.context() as patch:
        # Keep the desktop entry point real, using the same small config on both paths.
        patch.setattr(app_core, "_analyze_file", partial(analyze_file, config=_CONFIG))
        for depth, mode, profile, _ in _PRESETS:
            desktop = app_core.analyze_for_app(
                _SOURCE, output_parent=root / depth / "desktop", report_depth=depth
            )
            matched = analyze_file(
                _SOURCE,
                root / depth / "matched",
                config=_CONFIG,
                analysis_mode=mode,
                selection=GraphSelection(profile=profile),
            )
            reports[depth] = desktop, matched
    return reports


class _Links(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id") is not None:
            self.ids.add(values["id"])
        if tag == "a" and values.get("href") is not None:
            self.hrefs.append(values["href"])


@pytest.mark.parametrize("depth,mode,profile,count", _PRESETS)
def test_desktop_presets_match_exact_pipeline_outputs(
    depth_reports: dict[str, tuple[AnalysisRunResult, AnalysisRunResult]],
    depth: str,
    mode: str,
    profile: str,
    count: int,
) -> None:
    desktop, matched = depth_reports[depth]
    assert desktop.summary == matched.summary
    assert desktop.findings == matched.findings
    assert desktop.summary["graphs"]["profile"] == profile
    assert len(desktop.plot_paths) == len(list(desktop.out_dir.glob("*.png"))) == count
    assert {path.name for path in desktop.plot_paths} == {path.name for path in matched.plot_paths}
    for path in desktop.plot_paths:
        assert path.read_bytes() == (matched.out_dir / path.name).read_bytes(), path.name
    for filename in ("summary.json", "findings.json"):
        assert json.loads((desktop.out_dir / filename).read_text()) == json.loads(
            (matched.out_dir / filename).read_text()
        )

    html = desktop.html_report_path.read_text(encoding="utf-8")
    assert '<body data-presentation="studio">' in html
    assert str(_SOURCE.parent) not in html
    assert str(_SOURCE.parent) not in json.dumps(desktop.summary)
    manifest = json.loads((desktop.out_dir / OUTPUT_MARKER_FILENAME).read_text())
    if depth != "detailed":
        assert all(not (desktop.out_dir / name).exists() for name in EVIDENCE_REPORT_FILENAMES)
        assert not EVIDENCE_REPORT_FILENAMES.intersection(manifest["generated_files"])
        assert "Evidence navigator" not in html
        return

    assert "Evidence navigator" in html
    assert set(manifest["generated_files"]) >= EVIDENCE_REPORT_FILENAMES
    documents = {
        name: _Links(desktop.out_dir / name)
        for name in ("report.html", "evidence_ranges.html")
    }
    assert "evidence_ranges.html#evidence-ledger" in documents["report.html"].hrefs
    for name, document in documents.items():
        for href in document.hrefs:
            link = urlsplit(href)
            if link.scheme or link.netloc or link.path not in documents:
                continue
            assert (desktop.out_dir / link.path).is_file(), (name, href)
            if link.fragment:
                assert link.fragment in documents[link.path].ids, (name, href)
    markdown = desktop.report_path.read_text(encoding="utf-8")
    assert "evidence_ranges.md" in markdown
    assert (desktop.out_dir / "evidence_ranges.md").is_file()

    # Standard and Detailed change presentation breadth, preserving all measurements.
    standard = depth_reports["standard"][0]
    display_fields = {"plots", "graphs"}
    assert {key: value for key, value in desktop.summary.items() if key not in display_fields} == {
        key: value for key, value in standard.summary.items() if key not in display_fields
    }
    assert desktop.findings == standard.findings


@pytest.mark.parametrize("depth,count", [("standard", 14), ("overview", 4)])
def test_desktop_depth_downgrade_removes_owned_companions_and_preserves_user_files(
    depth_reports: dict[str, tuple[AnalysisRunResult, AnalysisRunResult]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    depth: str,
    count: int,
) -> None:
    out = tmp_path / app_core.default_report_directory(_SOURCE).name
    shutil.copytree(depth_reports["detailed"][0].out_dir, out)
    notes = out / "listening-notes.txt"
    notes.write_bytes(b"user listening notes\x00")
    user_folder = out / "user-material"
    user_folder.mkdir()
    (user_folder / "evidence_ranges.html").write_bytes(b"user companion namesake\x00")
    monkeypatch.setattr(app_core, "_analyze_file", partial(analyze_file, config=_CONFIG))

    result = app_core.analyze_for_app(_SOURCE, output_parent=tmp_path, report_depth=depth)

    assert result.out_dir == out
    assert len(list(out.glob("*.png"))) == count
    assert all(not (out / name).exists() for name in EVIDENCE_REPORT_FILENAMES)
    manifest = json.loads((out / OUTPUT_MARKER_FILENAME).read_text())
    assert not EVIDENCE_REPORT_FILENAMES.intersection(manifest["generated_files"])
    assert notes.read_bytes() == b"user listening notes\x00"
    assert (user_folder / "evidence_ranges.html").read_bytes() == b"user companion namesake\x00"


def test_desktop_cancelled_depth_change_preserves_complete_previous_report(
    depth_reports: dict[str, tuple[AnalysisRunResult, AnalysisRunResult]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / app_core.default_report_directory(_SOURCE).name
    shutil.copytree(depth_reports["detailed"][0].out_dir, out)
    before = {path.relative_to(out): path.read_bytes() for path in out.rglob("*") if path.is_file()}
    token = CancellationToken()
    monkeypatch.setattr(app_core, "_analyze_file", partial(analyze_file, config=_CONFIG))

    def cancel_after_first_plot(progress: AnalysisProgress) -> None:
        if progress.stage == "rendering" and progress.completed == 1:
            token.cancel()

    with pytest.raises(AnalysisCancelled):
        app_core.analyze_for_app(
            _SOURCE,
            output_parent=tmp_path,
            report_depth="overview",
            progress_callback=cancel_after_first_plot,
            cancellation_token=token,
        )

    assert {path.relative_to(out): path.read_bytes() for path in out.rglob("*") if path.is_file()} == before
    assert not list(tmp_path.glob(f".{out.name}.audioatlas-*"))
