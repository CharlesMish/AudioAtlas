from __future__ import annotations

from matplotlib.colors import to_rgb

from audioatlas.plot_theme import matplotlib_theme_rc, plot_palette
from audioatlas.theme import available_themes


def _relative_luminance(color: str) -> float:
    channels = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in to_rgb(color)
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    return (max(first_luminance, second_luminance) + 0.05) / (
        min(first_luminance, second_luminance) + 0.05
    )


def test_matplotlib_theme_rc_uses_report_surface_and_text_tokens():
    theme = next(item for item in available_themes() if item.theme_id == "midnight_studio")
    style = matplotlib_theme_rc(theme.theme_id)

    assert style["figure.facecolor"] == theme.tokens["surface"]
    assert style["axes.facecolor"] == theme.tokens["surface"]
    assert style["axes.titlecolor"] == theme.tokens["text"]
    assert style["grid.color"] == theme.tokens["border"]
    assert style["legend.facecolor"] == theme.tokens["surface_muted"]


def test_every_theme_plot_palette_is_distinct_and_visible():
    for theme in available_themes():
        palette = plot_palette(theme.theme_id)
        assert len(palette) >= 3, theme.theme_id
        assert len(palette) == len(set(palette)), theme.theme_id
        for color in palette:
            assert _contrast_ratio(color, theme.tokens["surface"]) >= 3.0, (
                theme.theme_id,
                color,
            )
