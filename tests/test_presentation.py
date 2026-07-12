from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from audioatlas.html_report import write_report_html
from audioatlas.presentation import (
    DEFAULT_PRESENTATION_MODE,
    presentation_controls_html,
    presentation_css,
    presentation_script,
    validate_presentation_mode,
)


def _report_test_helpers():
    path = Path(__file__).with_name("test_report.py")
    spec = importlib.util.spec_from_file_location("audioatlas_test_report_helpers", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._make_summary, module._html_findings


def test_presentation_modes_validate_without_loading_scientific_stack():
    assert DEFAULT_PRESENTATION_MODE == "focus"
    assert validate_presentation_mode(None) == "focus"
    assert validate_presentation_mode("focus") == "focus"
    assert validate_presentation_mode("studio") == "studio"
    with pytest.raises(ValueError, match="Unknown presentation mode"):
        validate_presentation_mode("cinematic")


def test_presentation_shell_is_accessible_local_and_data_preserving():
    controls = presentation_controls_html("focus")
    css = presentation_css()
    script = presentation_script("focus")

    assert 'role="group"' in controls
    assert 'aria-pressed="true"' in controls
    assert 'data-presentation-choice="studio"' in controls
    assert 'body[data-presentation="studio"]' in css
    assert ".plot-image-wrapper img" in css
    assert "filter:" not in css
    assert "window.localStorage" in script
    assert "fetch(" not in script
    assert "http://" not in script
    assert "https://" not in script


def test_report_html_can_open_in_studio_and_switch_back_to_focus(tmp_path: Path):
    make_summary, html_findings = _report_test_helpers()
    summary = make_summary()
    path = write_report_html(
        summary,
        summary["plots"],
        tmp_path,
        html_findings(),
        presentation_mode="studio",
    )
    text = path.read_text(encoding="utf-8")

    assert '<body data-presentation="studio">' in text
    assert 'data-presentation-choice="focus"' in text
    assert 'data-presentation-choice="studio"' in text
    assert 'body[data-presentation="studio"] .plot-card' in text
    assert 'var fallback="studio"' in text
    assert "audioatlas:presentation:" in text
