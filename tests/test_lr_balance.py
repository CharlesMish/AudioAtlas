"""Scientific contract and integration checks for signed channel RMS balance."""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pytest
import soundfile as sf
from matplotlib.figure import Figure

from audioatlas.analysis.bundle import _COMPUTE
from audioatlas.analysis.lr_balance import compute_lr_balance
from audioatlas.config import AnalysisConfig
from audioatlas.graphs import GraphSelection
from audioatlas.pipeline import analyze_file
from audioatlas.provenance import build_analysis_provenance
from audioatlas.report_depth import resolve_report_plan
from audioatlas.visualize.lr_balance import plot_lr_balance

SR = 48000


def constant(left, right, n=4096):
    return np.tile(np.array([left, right], dtype=np.float32), (n, 1))


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (0.25, 0.25, 0),
        (0.5, 0.125, 12.041199826559248),
        (0.125, 0.5, -12.041199826559248),
        (1, 0.25, 12.041199826559248),
    ],
)
def test_known_ratios_and_complete_center_frames(left, right, expected):
    r = compute_lr_balance(constant(left, right, 6145), SR)
    np.testing.assert_allclose(r.balance_db, expected, rtol=0, atol=1e-13)
    np.testing.assert_array_equal(r.times_seconds, np.array([2048, 3072, 4096]) / SR)
    assert r.frame_status.tolist() == ["defined"] * 3
    assert r.to_summary_dict()["defined_frame_coverage"] == 1


@pytest.mark.parametrize(
    "left,right,reason",
    [
        (0, 0.25, "left_below_floor"),
        (0.25, 0, "right_below_floor"),
        (0, 0, "both_below_floor"),
        (1e-5, 1e-5, "both_below_floor"),
    ],
)
def test_reason_coded_nulls(left, right, reason):
    r = compute_lr_balance(constant(left, right), SR)
    assert np.isnan(r.balance_db).all()
    d = r.to_summary_dict()
    assert d["balance_db_median"] is None and d["defined_frame_coverage"] == 0
    assert d["timeline"]["balance_db"] == [None]
    assert d["timeline"]["status"] == [reason]
    assert d["undefined_reason_counts"][reason] == 1
    json.dumps(d, allow_nan=False)


def test_floor_sensitivity_nearest_float32_and_crossings():
    floor = 1e-4
    below = np.float32(floor)
    above = np.nextafter(below, np.float32(np.inf))
    assert float(below) < floor < float(above)
    y = np.concatenate(
        [constant(below, 0.25), constant(above, 0.25), constant(0.25, above), constant(0.25, below)]
    )
    r = compute_lr_balance(y, SR, AnalysisConfig(hop_length=4096))
    assert r.frame_status.tolist() == [
        "left_below_floor",
        "defined",
        "defined",
        "right_below_floor",
    ]
    assert np.isfinite(r.balance_db).tolist() == [False, True, True, False]
    # Exact boundary representable in decoded audio: 0 dBFS floor and RMS 1.
    assert (
        compute_lr_balance(
            constant(1, 1), SR, AnalysisConfig(lr_balance_min_rms_dbfs=0)
        ).frame_status[0]
        == "defined"
    )
    assert r.to_summary_dict()["defined_frame_coverage"] == 0.5


def test_alternation_swap_and_common_gain():
    y = np.concatenate([constant(0.5, 0.125), constant(0.125, 0.5), constant(0, 0)])
    cfg = AnalysisConfig(hop_length=4096)
    r = compute_lr_balance(y, SR, cfg)
    swapped = compute_lr_balance(y[:, ::-1], SR, cfg)
    np.testing.assert_array_equal(swapped.balance_db, -r.balance_db)
    np.testing.assert_allclose(
        r.balance_db[:2], [12.041199826559248, -12.041199826559248], atol=1e-13
    )
    for gain in [0.5, 2, -1, -0.25]:
        np.testing.assert_allclose(
            compute_lr_balance(y * gain, SR, cfg).balance_db,
            r.balance_db,
            atol=1e-13,
            rtol=0,
            equal_nan=True,
        )
    rng = np.random.default_rng(12)
    y = rng.normal(0, 0.15, (16000, 2)).astype(np.float32)
    r = compute_lr_balance(y, SR)
    np.testing.assert_array_equal(compute_lr_balance(y[:, ::-1], SR).balance_db, -r.balance_db)
    # Arbitrary gain rounds decoded float32 samples; tolerate only that rounding.
    np.testing.assert_allclose(
        compute_lr_balance(y * 0.37, SR).balance_db, r.balance_db, atol=1e-6, rtol=0
    )
    # Invariance holds only while both operands remain measurable.
    assert compute_lr_balance(y * 1e-5, SR).to_summary_dict()["defined_frames"] == 0


@pytest.mark.parametrize(
    "channels,status",
    [
        (1, "not_applicable_mono"),
        (3, "not_applicable_multichannel"),
        (6, "not_applicable_multichannel"),
    ],
)
def test_channel_policy(channels, status):
    d = compute_lr_balance(np.ones((8192, channels)), SR).to_summary_dict()
    assert d["status"] == status and d["frames"] == 0
    assert d["balance_db_median"] is None and d["defined_frame_coverage"] is None
    assert d["timeline"]["times_seconds"] == []


@pytest.mark.parametrize("n", [0, 1, 4095])
def test_too_short(n):
    d = compute_lr_balance(np.zeros((n, 2)), SR).to_summary_dict()
    assert d["status"] == "insufficient_samples" and d["frames"] == 0
    assert d["balance_db_p10"] is None and d["balance_db_p90"] is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1, -10000])
def test_invalid_floor(value):
    with pytest.raises(ValueError):
        compute_lr_balance(constant(1, 1), SR, AnalysisConfig(lr_balance_min_rms_dbfs=value))


def test_asymmetric_clipped_against_independent_rms():
    x = np.linspace(-2, 2, 8192, dtype=np.float32)
    y = np.column_stack([np.clip(x, -1, 1), 0.2 * x])
    r = compute_lr_balance(y, SR)
    expected = []
    for start in range(0, len(y) - 4096 + 1, 1024):
        rms = np.sqrt(np.mean(y[start : start + 4096].astype(np.float64) ** 2, axis=0))
        expected.append(20 * np.log10(rms[0] / rms[1]))
    np.testing.assert_allclose(r.balance_db, expected, atol=1e-12, rtol=0)


def test_plot_keeps_gaps_and_neutral_zero(tmp_path, monkeypatch):
    r = compute_lr_balance(
        np.concatenate([constant(0.5, 0.125), constant(0, 0), constant(0.125, 0.5)]),
        SR,
        AnalysisConfig(hop_length=4096),
    )
    captured = []

    def capture(fig, *args, **kwargs):
        ax = fig.axes[0]
        captured.append(ax.lines[0].get_ydata())
        assert ax.get_ylim()[0] == -ax.get_ylim()[1]
        np.testing.assert_array_equal(ax.lines[1].get_ydata(), [0, 0])
        assert any(
            "Left higher RMS" in t.get_text() and "Right higher RMS" in t.get_text()
            for t in ax.texts
        )
        assert len(ax.patches) == 0  # No acceptable band or defect region.

    monkeypatch.setattr(Figure, "savefig", capture)
    plot_lr_balance(r, tmp_path / "plot.png")
    np.testing.assert_array_equal(captured[0], r.balance_db)
    assert np.isnan(captured[0][1])


def test_pipeline_restoration_range_and_reports(tmp_path, monkeypatch):
    y = constant(0.25, 0.125, SR * 2)
    path = tmp_path / "audio.wav"
    sf.write(path, y, SR, subtype="FLOAT")
    calls = Counter()
    for name, fn in tuple(_COMPUTE.items()):

        def counted(*args, _name=name, _fn=fn, **kwargs):
            calls[_name] += 1
            return _fn(*args, **kwargs)

        monkeypatch.setitem(_COMPUTE, name, counted)
    sel = GraphSelection(profile="compact", enable=("lr_balance", "lr_balance"))
    plan = resolve_report_plan(None, "compact", sel)
    assert "lr_balance" in plan.restored
    r = analyze_file(
        path,
        tmp_path / "range",
        analysis_mode="compact",
        selection=sel,
        start_seconds=0.5,
        end_seconds=1.5,
    )
    assert calls["lr_balance"] == 1
    assert r.summary["schema_version"] == "0.4.0"
    assert r.summary["lr_balance"]["timeline"]["times_seconds"][0] == 2048 / SR
    assert r.summary["analysis_execution"]["computed"].count("lr_balance") == 1
    assert "lr_balance" not in r.summary["analysis_execution"]["skipped"]
    for f in ["report.html", "report.md"]:
        text = (tmp_path / "range" / f).read_text()
        assert "Left higher RMS" in text and "Right higher RMS" in text
        assert "Times in plots and findings are relative to this analyzed range" in text
        assert "not a quality threshold" in text
    json.loads(
        (tmp_path / "range" / "summary.json").read_text(), parse_constant=lambda x: pytest.fail(x)
    )
    p = r.summary["analysis_provenance"]["measurement_methods"]["lr_balance"]
    assert p["channels"] == "exactly_two" and p["min_rms_dbfs_per_channel"] == -80
    calls.clear()
    c = analyze_file(path, tmp_path / "compact", analysis_mode="compact")
    assert calls["lr_balance"] == 0 and "lr_balance" not in c.summary
    assert "lr_balance" in c.summary["analysis_execution"]["skipped"]
    assert "L/R RMS balance" in (tmp_path / "compact" / "report.html").read_text()
    assert c.findings["findings"] == r.findings["findings"]


def test_provenance_floor_sensitive():
    a = build_analysis_provenance(AnalysisConfig())
    b = build_analysis_provenance(AnalysisConfig(lr_balance_min_rms_dbfs=-90))
    assert a["compatible_analysis_sha256"] != b["compatible_analysis_sha256"]
    assert a["finding_rule_code_sha256"] == b["finding_rule_code_sha256"]


def test_historical_absence_is_not_a_revision_delta_zero():
    from audioatlas.revision_diff import _metric_deltas
    old = {"levels": {"rms_dbfs": -20.0}}
    current = {**old, "lr_balance": {"balance_db_median": 6.0}}
    assert _metric_deltas(old, current) == _metric_deltas(old, old)


def test_nonfinite_and_invalid_shape_rejected():
    for y in (np.full((4096, 2), np.nan), np.zeros((2, 3, 4))):
        with pytest.raises(ValueError):
            compute_lr_balance(y, SR)
