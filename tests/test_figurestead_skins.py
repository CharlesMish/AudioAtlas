"""Optional skins and palette metadata, independent of shared renderer styling."""

from __future__ import annotations

from dataclasses import replace

import pytest

from audioatlas import plot_theme
from audioatlas.theme import _theme_from_dict, featured_theme_names, get_theme

SERIES = {
    "lavender_fog_notebook": ("#6855A8", "#18776D", "#9B5B16", "#A44E5E", "#326D9B", "#52752C"),
    "ultraviolet_laboratory": ("#B59BFF", "#67D7C4", "#F2A65A", "#E57FA6", "#8DB7FF", "#BBD66B"),
}


@pytest.mark.parametrize("name,series", SERIES.items())
def test_optional_skin_series_match_authoritative_figurestead_tokens(name, series):
    # Figurestead 2fcff6c6f898ed96d9f1e6ab0c4eb915a3d9f0cd.
    assert get_theme(name).plot_series == series
    assert plot_theme.plot_palette(name) == series
    assert name not in featured_theme_names()


@pytest.mark.parametrize("name", SERIES)
def test_skin_plot_series_are_independent_of_ui_severity_colors(name, monkeypatch):
    theme = get_theme(name)
    altered_tokens = dict(theme.tokens, issue_text="#FFFFFF", warning_text="#FFFFFF",
                          info_text="#FFFFFF", trait_text="#FFFFFF")
    monkeypatch.setattr(plot_theme, "get_theme", lambda _: replace(theme, tokens=altered_tokens))
    assert plot_theme.plot_palette(name) == SERIES[name]


def test_old_theme_loader_accepts_absent_palette_metadata():
    theme = _theme_from_dict("existing", {"tokens": {"surface": "#FFFFFF"}})
    assert theme.plot_series == ()


@pytest.mark.parametrize("series", [None, "#FFFFFF", ["#000000"],
                                    ["#000000", "#111111", "url(example)"],
                                    ["#000000", "#111111", 123]])
def test_invalid_optional_palette_metadata_rejected(series):
    with pytest.raises(ValueError, match="invalid plot_series"):
        _theme_from_dict("invalid", {"tokens": {}, "plot_series": series})


@pytest.mark.parametrize("series", [("#6855A8", "#6855A8", "#18776D"),
                                    ("#FFFFFF", "#FFFFFE", "#FFFFFD")])
def test_duplicate_or_low_contrast_explicit_palette_rejected(series, monkeypatch):
    theme = replace(get_theme("lavender_fog_notebook"), plot_series=series)
    monkeypatch.setattr(plot_theme, "get_theme", lambda _: theme)
    with pytest.raises(ValueError, match="duplicate or low-contrast"):
        plot_theme.plot_palette("lavender_fog_notebook")
