"""Deterministic shared plot-role identity and composited contrast for existing themes."""

from __future__ import annotations

from dataclasses import replace

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure

from audioatlas.analysis.levels import compute_peak_timeline
from audioatlas.config import AnalysisConfig
from audioatlas.plot_theme import matplotlib_theme_rc, plot_palette, plot_role
from audioatlas.theme import available_themes, default_theme_name, featured_theme_names
from audioatlas.visualize.waveform import plot_peak_timeline

REPRESENTATIVE_THEMES = ("default", "midnight_studio", "high_contrast_clean")


def _luminance(rgb):
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722), strict=True))


def _composited_contrast(color, background, alpha):
    # Eight-bit nominal interior compositing includes channel quantization.
    bg = to_rgb(background)
    rgb = tuple(round(255 * (alpha * f + (1 - alpha) * b)) / 255
                for f, b in zip(to_rgb(color), bg, strict=True))
    a, b = sorted((_luminance(rgb), _luminance(bg)))
    return (b + .05) / (a + .05)


def test_shared_style_preserves_existing_defaults():
    assert default_theme_name() == "default"
    assert featured_theme_names() == ["default", "midnight_studio", "warm_tape", "studio_blue",
                                      "moss", "high_contrast_clean", "charcoal_gold", "solarized_dark"]


@pytest.mark.parametrize("theme", [t.theme_id for t in available_themes()])
def test_every_theme_essential_roles_pass_composited_panel_and_legend(theme):
    with mpl.rc_context(matplotlib_theme_rc(theme)):
        assert mpl.rcParams["legend.facecolor"] == mpl.rcParams["axes.facecolor"]
        assert mpl.rcParams["legend.framealpha"] == 1.0
        for role, alpha in [("s1", .45), ("s2", 1), ("s3", 1), ("waveform", .8),
                            ("rms", .9), ("reference", .45), ("event", .75),
                            ("threshold", .9), ("median", 1)]:
            actual = plot_role(role, alpha=alpha)
            assert actual["alpha"] >= alpha
            for substrate in ("axes.facecolor", "legend.facecolor"):
                assert _composited_contrast(actual["color"], mpl.rcParams[substrate],
                                           actual["alpha"]) >= 3.0, (theme, role, substrate)
        assert plot_role("fill", alpha=.2, essential=False)["alpha"] == .2
        assert plot_role("grid", alpha=.25, essential=False)["alpha"] == .25


@pytest.mark.parametrize("theme", REPRESENTATIVE_THEMES)
def test_explicit_roles_do_not_consume_axes_cycler(theme):
    with mpl.rc_context(matplotlib_theme_rc(theme)):
        fig, ax = plt.subplots()
        roles = {name: plot_role(name) for name in ("s1", "s2", "s3", "threshold", "event")}
        for _ in range(9):
            ax.plot([0, 1], [0, 1])
        assert roles == {name: plot_role(name) for name in roles}
        assert roles["s1"]["color"] == plot_palette(theme)[0]
        assert roles["event"]["color"] == plot_palette(theme)[1]
        assert roles["threshold"]["color"] == plot_palette(theme)[2]
        plt.close(fig)


@pytest.mark.parametrize("theme", REPRESENTATIVE_THEMES)
def test_conditional_peak_events_keep_color_and_marker_identity(theme, tmp_path, monkeypatch):
    peaks = compute_peak_timeline(np.full((48000, 2), .5), 48000, AnalysisConfig())
    colors = []

    def capture(figure, *args, **kwargs):
        colors.append({item.get_label(): item.get_facecolor().tolist()
                       for item in figure.axes[0].collections})

    monkeypatch.setattr(Figure, "savefig", capture)
    with mpl.rc_context(matplotlib_theme_rc(theme)):
        for include_near in (False, True):
            result = replace(peaks, near_clipping_counts=np.full_like(peaks.near_clipping_counts, int(include_near)),
                             clipped_counts=np.ones_like(peaks.clipped_counts))
            plot_peak_timeline(result, tmp_path / "events.png")
    assert colors[0]["Clipping-threshold frame"] == colors[1]["Clipping-threshold frame"]
    assert colors[1]["Clipping-threshold frame"] != colors[1]["Near-clipping frame"]
