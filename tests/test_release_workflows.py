from __future__ import annotations

import re
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
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["deploy"]["permissions"] == {
        "pages": "write",
        "id-token": "write",
    }
    assert workflow["jobs"]["deploy"]["environment"]["name"] == "github-pages"
    text = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "examples/demo_audio/audioatlas_demo.wav" in text
    assert "--graphs-profile standard" in text
    assert "--theme midnight_studio" in text
    assert 'summary["metadata"]["filename"] == "audioatlas_demo.wav"' in text
    assert 'len(summary["graphs"]["selected_filenames"]) == 14' in text
    assert "assert not list(site.rglob(\"*.wav\"))" in text


def test_release_requires_version_tag_and_uses_trusted_publishing() -> None:
    workflow = _workflow("release.yml")

    assert workflow["on"] == {"push": {"tags": ["v*"]}}
    assert workflow["jobs"]["pypi"]["permissions"] == {
        "actions": "read",
        "id-token": "write",
    }
    assert workflow["jobs"]["pypi"]["environment"]["name"] == "pypi"
    assert workflow["jobs"]["draft-release"]["environment"]["name"] == "github-release"
    assert workflow["jobs"]["finalize-release"]["environment"]["name"] == "github-release"
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "pypa/gh-action-pypi-publish@" in text
    assert 'test "${GITHUB_REF_NAME}" = "v${version}"' in text
    assert "git merge-base --is-ancestor" in text
    assert "testpypi.yml/runs?head_sha=${GITHUB_SHA}&status=success" in text
    assert "--draft" in text
    assert "--draft=false" in text
    assert "--require-present" in text


def test_testpypi_is_manual_and_uses_separate_environment() -> None:
    workflow = _workflow("testpypi.yml")

    assert workflow["on"] == {"workflow_dispatch": {}}
    publish = workflow["jobs"]["publish"]
    assert workflow["jobs"]["build"]["if"] == "github.ref == 'refs/heads/main'"
    assert publish["environment"]["name"] == "testpypi"
    assert publish["permissions"] == {"id-token": "write"}
    assert "verify" in workflow["jobs"]


def test_all_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    action_ref = re.compile(r"^[^\s@]+@[0-9a-f]{40}$")
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        workflow = _workflow(path.name)
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                used = step.get("uses")
                if used is not None:
                    assert action_ref.fullmatch(used), f"{path.name}: {used}"


def test_ci_audits_the_hashed_locked_runtime_dependencies() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "Runtime dependency audit" in text
    assert "uv export --locked --no-dev --no-emit-project" in text
    assert "pip-audit --require-hashes" in text
