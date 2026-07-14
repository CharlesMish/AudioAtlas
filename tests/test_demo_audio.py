from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_audio_rights_are_separate_from_unchanged_software_license() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["license"] == {"file": "LICENSE"}
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")

    notice = (ROOT / "AUDIO_RIGHTS.md").read_text(encoding="utf-8")
    assert "Copyright © 2026 Charles Mish" in notice
    assert "CC BY 4.0 applies only to material Charles Mish is authorized to license" in notice
    assert "standalone samples" in notice


def test_distribution_configuration_keeps_rights_notice_but_excludes_demo_audio() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sdist = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]

    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel == {"packages": ["src/audioatlas"]}
    assert "/examples/demo_audio/**" in sdist["exclude"]
    assert "/tests/test_demo_audio_source.py" in sdist["exclude"]
    assert "/tests/test_distribution_artifacts.py" in sdist["exclude"]
    assert "/AUDIO_RIGHTS.md" in sdist["include"]
