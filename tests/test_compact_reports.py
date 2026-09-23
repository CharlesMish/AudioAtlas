"""Compact reports must distinguish skipped work from measured results."""

from pathlib import Path

from audioatlas.catalog_report import (
    build_catalog_summary,
    track_record_from_run,
    write_catalog_html,
    write_catalog_md,
)
from audioatlas.html_report import write_report_html
from audioatlas.report import write_report_md


def _summary(*, average: bool = False, onset: bool = False) -> dict:
    computed = ["levels", "rms", "peaks", "stereo", "mid_side", "spectral_shape", "spectrogram"]
    skipped = ["crest", "short_term", "average_spectrum", "band_power", "onset", "chroma"]
    summary = {
        "schema_version": "0.3.0",
        "metadata": {"filename": "track.wav", "samplerate": 44100, "channels": 2},
        "levels": {"duration_seconds": 10.0, "rms_dbfs": -12.0, "clipped_samples": 0},
        "rms_envelope": {"frames": 100},
        "stereo_correlation": {"correlation_median": 0.9},
        "mid_side_energy": {"side_to_mid_ratio_db_median": -15.0},
        "analysis_execution": {
            "mode": "compact", "computed": computed, "skipped": skipped,
            "summary_blocks": [], "findings_coverage": "complete",
        },
    }
    if average:
        computed.append("average_spectrum")
        skipped.remove("average_spectrum")
        summary["average_spectrum"] = {"strongest_band": "bass"}
    if onset:
        computed.append("onset")
        skipped.remove("onset")
        summary["onset_density"] = {"onset_density_median": 2.0}
    return summary


def _record(summary: dict, name: str = "track.wav") -> dict:
    return track_record_from_run(
        filename=name, report_path=f"{name}/report.html", summary=summary,
        findings={"findings": [], "analysis_execution": summary["analysis_execution"]},
    )


def _catalog(tmp_path: Path, tracks: list[dict]) -> dict:
    return build_catalog_summary(
        input_folder=tmp_path / "input", output_folder=tmp_path,
        tracks=tracks, skipped_files=[],
    )


def test_compact_reports_explain_skips_and_omit_uncomputed_sections(tmp_path):
    summary = _summary()
    md = write_report_md(summary, [], tmp_path).read_text()
    html = write_report_html(summary, [], tmp_path).read_text()
    for text in (md, html):
        assert "Compact computation retains headline metrics and all current finding checks." in text
        assert "Not computed: crest factor timeline, short-term LUFS, average spectrum" in text
        assert "Skipped analyses are not zero measurements." in text
    assert "## Average spectrum summary" not in md
    assert "<summary>Spectrum metrics</summary>" not in html
    assert "## Frame RMS envelope summary" in md
    assert "Median stereo correlation" in html


def test_explicitly_requested_analyses_appear_in_compact_reports(tmp_path):
    summary = _summary(average=True, onset=True)
    md = write_report_md(summary, [], tmp_path).read_text()
    html = write_report_html(summary, [], tmp_path).read_text()
    assert "## Average spectrum summary" in md
    assert "## Onset / transient density summary" in md
    assert "<summary>Spectrum metrics</summary>" in html
    assert "<summary>Onset density</summary>" in html


def test_full_reports_do_not_add_compact_scope(tmp_path):
    summary = _summary(average=True, onset=True)
    summary["analysis_execution"]["mode"] = "full"
    for path in (
        write_report_md(summary, [], tmp_path),
        write_report_html(summary, [], tmp_path),
    ):
        text = path.read_text()
        assert "Compact computation" not in text
        assert "Analysis scope" not in text


def test_compact_catalog_exposes_coverage_without_zero_filling(tmp_path):
    summary = _summary()
    record = _record(summary)
    assert record["analysis_execution"] == summary["analysis_execution"]
    assert record["strongest_band"] is None
    assert record["onset_density_median"] is None
    catalog = _catalog(tmp_path, [record])
    assert catalog["analysis_coverage"]["average_spectrum"] == {"computed_count": 0, "skipped_count": 1}
    assert catalog["statistics"]["onset_density_median"]["count"] == 0
    assert catalog["statistics"]["onset_density_median"]["median"] is None
    assert catalog["common_patterns"] == []
    for path in (write_catalog_md(catalog, tmp_path), write_catalog_html(catalog, tmp_path)):
        text = path.read_text()
        assert "Average spectrum: computed for 0 of 1 tracks." in text
        assert "Onset density: computed for 0 of 1 tracks." in text
        assert "Not computed" in text
        if path.suffix == ".html":
            assert "Highest mean-power band Not computed" in text


def test_mixed_catalog_pattern_uses_only_measured_spectrum_tracks(tmp_path):
    catalog = _catalog(tmp_path, [
        _record(_summary(average=True, onset=True), "measured.wav"),
        _record(_summary(), "skipped1.wav"),
        _record(_summary(), "skipped2.wav"),
    ])
    pattern = next(item for item in catalog["common_patterns"] if item["id"] == "bass_sub_highest_mean_power_band")
    assert pattern["evaluated_count"] == pattern["count"] == 1
    assert pattern["track_count"] == 3
    assert pattern["share"] == 1.0
    assert catalog["statistics"]["onset_density_median"]["median"] == 2.0
    assert catalog["statistics"]["onset_density_median"]["missing_count"] == 2
    for path in (write_catalog_md(catalog, tmp_path), write_catalog_html(catalog, tmp_path)):
        text = path.read_text()
        assert "1 of 1 measured tracks" in text
        assert "Folder total: 3 tracks" in text


def test_legacy_full_catalog_does_not_add_compact_coverage(tmp_path):
    record = _record(_summary(average=True, onset=True))
    record.pop("analysis_execution")
    catalog = _catalog(tmp_path, [record])
    assert "analysis_coverage" not in catalog
    pattern = next(item for item in catalog["common_patterns"] if item["id"] == "bass_sub_highest_mean_power_band")
    assert "evaluated_count" not in pattern
    for path in (write_catalog_md(catalog, tmp_path), write_catalog_html(catalog, tmp_path)):
        assert "Analysis coverage" not in path.read_text()


def test_mixed_catalog_excludes_undefined_band_from_measured_denominator(tmp_path):
    undefined = _summary(average=True)
    undefined["average_spectrum"] = {"highest_mean_power_band": None}
    catalog = _catalog(tmp_path, [
        _record(_summary(average=True), "measured.wav"),
        _record(undefined, "undefined.wav"), _record(_summary(), "skipped.wav"),
    ])
    pattern = next(p for p in catalog["common_patterns"] if p["id"] == "bass_sub_highest_mean_power_band")
    assert pattern["evaluated_count"] == 1
    assert pattern["share"] == 1.0
    assert catalog["analysis_coverage"]["average_spectrum"]["computed_count"] == 2
