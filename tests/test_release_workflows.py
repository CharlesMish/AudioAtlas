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


def test_macos_app_has_separate_beta_and_notarized_release_gates() -> None:
    beta = _workflow("macos-app.yml")
    release = _workflow("release.yml")

    assert beta["jobs"]["build-and-smoke"]["runs-on"] == "macos-14"
    beta_text = (ROOT / ".github" / "workflows" / "macos-app.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/build_macos_app.py" in beta_text
    assert "--smoke-analyze" in beta_text
    assert "assert frozen == wheel" in beta_text
    assert "compressed_bytes" in beta_text
    assert 'MACOSX_DEPLOYMENT_TARGET: "14.0"' in beta_text
    assert "AUDIOATLAS_BUNDLE_BUILD_NUMBER" in beta_text
    assert "omppool" in beta_text

    app_job = release["jobs"]["macos-app"]
    assert app_job["environment"]["name"] == "macos-release"
    release_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "MACOS_CERTIFICATE_P12" in release_text
    assert "Preflight signing and notarization credentials" in release_text
    assert "scripts/package_macos_dmg.py" in release_text
    assert "notarization-log.json" in release_text
    assert "MACOS_TEAM_ID" in release_text
    assert "flags=.*runtime" in release_text
    assert "com.apple.security.get-task-allow" in release_text
    assert "Clean signing material" in release_text
    assert 'name: macos-acceptance' in release_text
    assert release["jobs"]["macos-acceptance"]["needs"] == ["prepare", "macos-app"]
    assert release["jobs"]["draft-release"]["needs"] == [
        "prepare",
        "macos-app",
        "macos-acceptance",
    ]

    packaging = (ROOT / "scripts" / "package_macos_dmg.py").read_text(encoding="utf-8")
    assert '"notarytool"' in packaging
    assert '"submit"' in packaging
    assert '"log"' in packaging
    assert 'log_payload.get("status") != "Accepted"' in packaging
    assert '"stapler", "validate"' in packaging
    assert '"spctl",' in packaging
    assert "DMG must contain exactly AudioAtlas.app and Applications" in packaging


def test_private_macos_demo_candidate_cannot_publish() -> None:
    workflow = _workflow("macos-demo-candidate.yml")
    text = (ROOT / ".github" / "workflows" / "macos-demo-candidate.yml").read_text(
        encoding="utf-8"
    )

    assert workflow["on"] == {"workflow_dispatch": {}}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["build-private-candidate"]
    assert job["runs-on"] == "macos-14"
    assert job["environment"]["name"] == "macos-release"
    assert 'test "${GITHUB_REF}" = "refs/heads/main"' in text
    assert 'test "${GITHUB_SHA}" = "$(git rev-parse origin/main)"' in text
    assert 'test "${version}" = "0.2.0a7"' in text
    assert "scripts/package_macos_dmg.py" in text
    assert "audioatlas_demo.wav" in text
    assert "docs/MACOS_DEMO_GUIDE.md" in text
    assert "macos-candidate-manifest.json" in text
    assert "retention-days: 14" in text
    assert "Clean signing material" in text
    assert "gh release" not in text
    assert "twine upload" not in text
    assert "gh-action-pypi-publish" not in text

    release_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/package_macos_dmg.py" in release_text


def test_macos_demo_guide_is_a_fillable_clean_machine_gate() -> None:
    guide = (ROOT / "docs" / "MACOS_DEMO_GUIDE.md").read_text(encoding="utf-8")

    assert "Candidate ID:" in guide
    assert "Mac model:" in guide
    assert "Apple chip:" in guide
    assert "Cold launch time:" in guide
    assert "First report time:" in guide
    assert "Do not bypass or disable macOS security checks" in guide
    assert "No Python, Terminal, administrator access" in guide
    assert "macos-acceptance" in guide


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
