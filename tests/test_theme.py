from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from audioatlas.cli import main
from audioatlas.theme import (
    available_theme_names,
    default_theme_name,
    featured_theme_names,
    friend_favorite_theme_names,
    theme_css_variables,
)


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
