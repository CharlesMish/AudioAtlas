"""Matplotlib styling derived from the built-in report theme library."""

from __future__ import annotations

from typing import Any

import matplotlib as mpl
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
_ESSENTIAL_ALPHA_TARGET = 3.1


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
        "legend.facecolor": tokens["surface"],
        "legend.framealpha": 1.0,
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


def _contrast_ratio(first: str | tuple[float, ...], second: str | tuple[float, ...]) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    return (max(first_luminance, second_luminance) + 0.05) / (
        min(first_luminance, second_luminance) + 0.05
    )


def _relative_luminance(color: str | tuple[float, ...]) -> float:
    red, green, blue = to_rgb(color)
    channels = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in (red, green, blue)
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


# Fixed roles never consume the mutable Axes property cycle. Optional marks
# therefore keep the same color whether earlier conditional marks exist or not.
_ROLE_INDEX = {
    "s1": 0, "s2": 1, "s3": 2,
    "waveform": 0, "rms": 1, "median": 1,
    "event": 1, "threshold": 2, "fill": 1,
}


def plot_role(role: str, *, alpha: float = 1.0, essential: bool = True) -> dict[str, Any]:
    """Resolve a role in the current scoped theme and protect essential opacity.

    Contrast is evaluated after sRGB compositing on the axes panel. The minimum
    applies to nominal stroke interiors, not antialiased edges or intersections.
    Decorative fills and grid lines need not meet the data-mark threshold.
    """
    if role in {"reference", "labels"}:
        color = mpl.rcParams["axes.labelcolor"]
    elif role == "grid":
        color = mpl.rcParams["grid.color"]
    else:
        colors = mpl.rcParams["axes.prop_cycle"].by_key()["color"]
        color = colors[_ROLE_INDEX[role] % len(colors)]
    if not 0 <= alpha <= 1:
        raise ValueError("Plot alpha must lie between 0 and 1")
    if essential:
        foreground = to_rgb(color)
        background = to_rgb(mpl.rcParams["axes.facecolor"])

        def contrast(opacity: float) -> float:
            blended = tuple(opacity * f + (1 - opacity) * b
                            for f, b in zip(foreground, background, strict=True))
            return _contrast_ratio(blended, background)

        if contrast(alpha) < _ESSENTIAL_ALPHA_TARGET:
            low, high = alpha, 1.0
            # The report palettes already pass at full opacity. Keep a safe
            # fallback for direct visualization calls with external rc styles.
            if contrast(high) >= _ESSENTIAL_ALPHA_TARGET:
                for _ in range(24):
                    midpoint = (low + high) / 2
                    if contrast(midpoint) >= _ESSENTIAL_ALPHA_TARGET:
                        high = midpoint
                    else:
                        low = midpoint
            alpha = high
    return {"color": color, "alpha": alpha}
