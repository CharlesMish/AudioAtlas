from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from audioatlas.cli import main
from audioatlas.theme import (
    available_theme_names,
    available_themes,
    default_theme_name,
    featured_theme_names,
    friend_favorite_theme_names,
    theme_css_variables,
)


def _relative_luminance(color: str) -> float:
    values = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in values
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def test_theme_library_exposes_all_theme_groups():
    names = available_theme_names()

    assert len(names) == 25
    assert default_theme_name() == "default"
    assert "midnight_studio" in names
    assert "default" in featured_theme_names()
    assert "cyan_terminal" in friend_favorite_theme_names()


def test_theme_css_variables_are_builtin_and_safe():
    css = theme_css_variables("midnight_studio")

    assert "--bg: #0b1120;" in css
    assert "--warning-bg:" in css
    assert "--lightbox-scrim:" in css
    assert "http://" not in css
    assert "https://" not in css
    assert "<script" not in css


def test_all_theme_text_pairs_meet_aa_normal_text_contrast():
    pairs = [
        ("text", "bg"),
        ("text", "surface"),
        ("text_muted", "bg"),
        ("text_muted", "surface"),
        ("text_soft", "bg"),
        ("text_soft", "surface"),
        ("accent", "bg"),
        ("accent", "surface"),
        ("issue_text", "issue_bg"),
        ("warning_text", "warning_bg"),
        ("info_text", "info_bg"),
        ("trait_text", "trait_bg"),
    ]
    for theme in available_themes():
        for foreground, background in pairs:
            ratio = _contrast_ratio(theme.tokens[foreground], theme.tokens[background])
            assert ratio >= 4.5, f"{theme.theme_id}: {foreground}/{background} = {ratio:.2f}"


def test_cli_themes_lists_all_theme_ids():
    result = CliRunner().invoke(main, ["themes"])

    assert result.exit_code == 0
    assert "Default theme: default" in result.output
    assert "Featured themes:" in result.output
    assert "Friend favorites:" in result.output
    for theme_id in available_theme_names():
        assert theme_id in result.output


def test_invalid_theme_name_fails_cleanly(tmp_path: Path):
    input_path = tmp_path / "placeholder.wav"
    input_path.write_bytes(b"not audio")
    result = CliRunner().invoke(
        main,
        ["analyze", str(input_path), "--out", str(tmp_path / "out"), "--theme", "nope"],
    )

    assert result.exit_code != 0
    assert "Invalid value for --theme" in result.output
    assert "Valid themes:" in result.output
    assert "midnight_studio" in result.output
