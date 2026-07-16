"""Matplotlib styling derived from the built-in report theme library."""

from __future__ import annotations

from typing import Any

from cycler import cycler
from matplotlib.colors import to_rgb

from audioatlas.theme import default_theme_name, get_theme

_PALETTE_TOKEN_ORDER = (
    "accent",
    "distribution_dot",
    "pattern_accent",
    "text_muted",
    "issue_text",
    "warning_text",
    "info_text",
    "trait_text",
)
_MIN_DATA_CONTRAST = 3.0


def matplotlib_theme_rc(theme_name: str | None = None) -> dict[str, Any]:
    """Return a scoped Matplotlib rc mapping for one report theme."""

    theme = get_theme(theme_name or default_theme_name())
    tokens = theme.tokens
    return {
        "figure.facecolor": tokens["surface"],
        "figure.edgecolor": tokens["surface"],
        "savefig.facecolor": tokens["surface"],
        "savefig.edgecolor": tokens["surface"],
        "axes.facecolor": tokens["surface"],
        "axes.edgecolor": tokens["border"],
        "axes.labelcolor": tokens["text_muted"],
        "axes.titlecolor": tokens["text"],
        "axes.prop_cycle": cycler(color=plot_palette(theme.theme_id)),
        "text.color": tokens["text"],
        "xtick.color": tokens["text_muted"],
        "ytick.color": tokens["text_muted"],
        "grid.color": tokens["border"],
        "legend.facecolor": tokens["surface_muted"],
        "legend.edgecolor": tokens["border"],
        "legend.labelcolor": tokens["text_muted"],
    }


def plot_palette(theme_name: str | None = None) -> tuple[str, ...]:
    """Return distinct theme colors with sufficient contrast for plotted data."""

    theme = get_theme(theme_name or default_theme_name())
    surface = theme.tokens["surface"]
    colors: list[str] = []
    for token_name in _PALETTE_TOKEN_ORDER:
        color = theme.tokens[token_name]
        if color in colors or _contrast_ratio(color, surface) < _MIN_DATA_CONTRAST:
            continue
        colors.append(color)
    return tuple(colors)


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    return (max(first_luminance, second_luminance) + 0.05) / (
        min(first_luminance, second_luminance) + 0.05
    )


def _relative_luminance(color: str) -> float:
    red, green, blue = to_rgb(color)
    channels = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in (red, green, blue)
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
