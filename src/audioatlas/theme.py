"""Built-in report theme helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

TOKEN_TO_CSS_VAR: dict[str, str] = {
    "bg": "--bg",
    "surface": "--surface",
    "surface_muted": "--surface-muted",
    "text": "--text",
    "text_muted": "--text-muted",
    "text_soft": "--text-soft",
    "border": "--border",
    "border_soft": "--border-soft",
    "accent": "--accent",
    "accent_muted": "--accent-muted",
    "chip_bg": "--chip-bg",
    "callout_bg": "--callout-bg",
    "callout_border": "--callout-border",
    "shadow_card": "--shadow-card",
    "issue_bg": "--issue-bg",
    "issue_text": "--issue-text",
    "issue_border": "--issue-border",
    "warning_bg": "--warning-bg",
    "warning_text": "--warning-text",
    "warning_border": "--warning-border",
    "info_bg": "--info-bg",
    "info_text": "--info-text",
    "info_border": "--info-border",
    "trait_bg": "--trait-bg",
    "trait_text": "--trait-text",
    "trait_border": "--trait-border",
    "pattern_accent": "--pattern-accent",
    "distribution_median": "--distribution-median",
    "distribution_dot": "--distribution-dot",
    "lightbox_scrim": "--lightbox-scrim",
    "lightbox_surface": "--lightbox-surface",
}

_SAFE_VALUE = re.compile(r"^[#(),.%0-9a-zA-Z\s-]+$")


@dataclass(frozen=True)
class Theme:
    """Built-in report theme metadata and normalized tokens."""

    theme_id: str
    display_name: str
    mood: str
    recommended_use: str
    accessibility_notes: str
    tokens: dict[str, str]


@cache
def _theme_data() -> dict[str, Any]:
    text = resources.files("audioatlas.themes").joinpath("all_themes.json").read_text(
        encoding="utf-8"
    )
    return json.loads(text)


def default_theme_name() -> str:
    value = _theme_data().get("default_theme")
    if not isinstance(value, str):
        raise ValueError("theme library is missing default_theme")
    return value


def featured_theme_names() -> list[str]:
    return _string_list(_theme_data().get("featured_themes"))


def friend_favorite_theme_names() -> list[str]:
    return _string_list(_theme_data().get("friend_favorites"))


def available_themes() -> list[Theme]:
    themes = _theme_data().get("themes")
    if not isinstance(themes, dict):
        raise ValueError("theme library is missing themes")
    return [_theme_from_dict(theme_id, value) for theme_id, value in themes.items()]


def available_theme_names() -> list[str]:
    return [theme.theme_id for theme in available_themes()]


def get_theme(theme_name: str | None = None) -> Theme:
    requested = theme_name or default_theme_name()
    themes = {theme.theme_id: theme for theme in available_themes()}
    try:
        return themes[requested]
    except KeyError as exc:
        valid = ", ".join(sorted(themes))
        raise ValueError(f"Unknown theme '{requested}'. Valid themes: {valid}") from exc


def validate_theme_name(theme_name: str | None) -> str:
    return get_theme(theme_name).theme_id


def theme_css_variables(theme_name: str | None = None) -> str:
    theme = get_theme(theme_name)
    lines = [":root {"]
    for token_name, css_var in TOKEN_TO_CSS_VAR.items():
        value = theme.tokens.get(token_name)
        if value is None:
            continue
        if not _is_safe_token_value(value):
            raise ValueError(f"Unsafe value for theme token '{token_name}'")
        lines.append(f"  {css_var}: {value};")
    lines.append("}")
    return "\n".join(lines)


def theme_listing_text() -> str:
    themes = {theme.theme_id: theme for theme in available_themes()}
    lines = [f"Default theme: {default_theme_name()}"]
    featured = featured_theme_names()
    if featured:
        lines.append("")
        lines.append("Featured themes:")
        for theme_id in featured:
            theme = themes.get(theme_id)
            if theme is not None:
                lines.append(f"- {theme.theme_id}: {theme.display_name}")
    favorites = friend_favorite_theme_names()
    if favorites:
        lines.append("")
        lines.append("Friend favorites:")
        for theme_id in favorites:
            theme = themes.get(theme_id)
            if theme is not None:
                lines.append(f"- {theme.theme_id}: {theme.display_name}")
    lines.append("")
    lines.append("All themes:")
    for theme in available_themes():
        lines.append(f"- {theme.theme_id}: {theme.display_name}")
    return "\n".join(lines)


def _theme_from_dict(theme_id: str, value: Any) -> Theme:
    if not isinstance(value, dict):
        raise ValueError(f"theme '{theme_id}' is not an object")
    tokens = value.get("tokens")
    if not isinstance(tokens, dict):
        raise ValueError(f"theme '{theme_id}' is missing tokens")
    normalized_tokens = {}
    for token_name, token_value in tokens.items():
        if token_name not in TOKEN_TO_CSS_VAR:
            continue
        if not isinstance(token_value, str) or not _is_safe_token_value(token_value):
            raise ValueError(f"theme '{theme_id}' has unsafe token '{token_name}'")
        normalized_tokens[token_name] = token_value
    return Theme(
        theme_id=theme_id,
        display_name=str(value.get("display_name", theme_id)),
        mood=str(value.get("mood", "")),
        recommended_use=str(value.get("recommended_use", "")),
        accessibility_notes=str(value.get("accessibility_notes", "")),
        tokens=normalized_tokens,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _is_safe_token_value(value: str) -> bool:
    return bool(_SAFE_VALUE.fullmatch(value))
