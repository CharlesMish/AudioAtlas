from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> dict:
    loaded = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_live_demo_deploys_only_from_main_or_manual_dispatch() -> None:
    workflow = _workflow("pages.yml")

    assert workflow["on"] == {"push": {"branches": ["main"]}, "workflow_dispatch": {}}
    assert workflow["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    text = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "examples/demo_audio/guitar.wav" in text
    assert "--graphs-profile standard" in text
    assert "assert not list(site.rglob(\"*.wav\"))" in text


def test_release_requires_version_tag_and_uses_trusted_publishing() -> None:
    workflow = _workflow("release.yml")

    assert workflow["on"] == {"push": {"tags": ["v*"]}}
    assert workflow["jobs"]["pypi"]["permissions"] == {"id-token": "write"}
    assert workflow["jobs"]["pypi"]["environment"] == {"name": "pypi"}
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "pypa/gh-action-pypi-publish@release/v1" in text
    assert 'test "${GITHUB_REF_NAME}" = "v${version}"' in text
    assert "--prerelease" in text


def test_testpypi_is_manual_and_uses_separate_environment() -> None:
    workflow = _workflow("testpypi.yml")

    assert workflow["on"] == {"workflow_dispatch": {}}
    publish = workflow["jobs"]["publish"]
    assert publish["environment"] == {"name": "testpypi"}
    assert publish["permissions"] == {"id-token": "write"}
