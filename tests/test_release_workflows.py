from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _manifest_field_block(text: str) -> set[str]:
    match = re.search(r"manifest_fields = \{(.*?)\}", text, re.S)
    assert match, "Release evidence manifest field block not found"
    return set(re.findall(r'"([a-z0-9_]+)"', match.group(1)))


def _workflow(name: str) -> dict:
    loaded = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _package_script():
    spec = importlib.util.spec_from_file_location(
        "package_macos_dmg",
        ROOT / "scripts" / "package_macos_dmg.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert "uv sync --locked --extra dev" in text
    assert "uv run python -m build" in text
    assert "uv run pytest" in text
    assert "uv run pip-audit --require-hashes" in text


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
    assert release["jobs"]["macos-evidence"]["needs"] == ["prepare", "macos-app"]
    assert release["jobs"]["macos-acceptance"]["needs"] == [
        "prepare",
        "macos-app",
        "macos-evidence",
    ]
    assert release["jobs"]["draft-release"]["needs"] == [
        "prepare",
        "macos-app",
        "macos-acceptance",
    ]
    assert "audioatlas-macos-app" in release_text
    assert "notarization-submission.json" in release_text
    assert "notarization-log.json" in release_text
    assert "macos-distribution-manifest.json" in release_text
    assert 'if-no-files-found: error' in release_text
    evidence_uploads = [
        step
        for step in app_job["steps"]
        if step.get("with", {}).get("name", "").startswith(
            "audioatlas-macos-notarization-evidence-"
        )
    ]
    assert len(evidence_uploads) == 1
    assert evidence_uploads[0]["if"] == "always()"
    assert evidence_uploads[0]["with"]["if-no-files-found"] == "warn"

    packaging = (ROOT / "scripts" / "package_macos_dmg.py").read_text(encoding="utf-8")
    assert '"notarytool"' in packaging
    assert '"submit"' in packaging
    assert '"log"' in packaging
    assert "ALLOWED_NOTARY_STATUS" in packaging
    assert re.search(r'"stapler",\s*"validate"', packaging)
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
    assert r'if [[ ! "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+a[0-9]+$ ]]' in text
    assert "0.2.0a7" not in text
    assert "scripts/package_macos_dmg.py" in text
    assert "audioatlas_demo.wav" in text
    assert "docs/MACOS_DEMO_GUIDE.md" in text
    assert "macos-candidate-manifest.json" in text
    for evidence_name in (
        'cp "${dmg}.sha256" "${kit}/"',
        'cp notarization-submission.json "${kit}/"',
        'cp notarization-log.json "${kit}/"',
    ):
        assert evidence_name in text
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
    assert "notarization" in guide
    assert "First report time" in guide


def test_testpypi_is_manual_and_uses_separate_environment() -> None:
    workflow = _workflow("testpypi.yml")
    text = (ROOT / ".github" / "workflows" / "testpypi.yml").read_text(encoding="utf-8")

    assert workflow["on"] == {"workflow_dispatch": {}}
    assert workflow["jobs"]["build"]["if"] == "github.ref == 'refs/heads/main'"
    assert workflow["jobs"]["publish"]["environment"]["name"] == "testpypi"
    assert workflow["jobs"]["publish"]["permissions"] == {"id-token": "write"}
    assert "verify" in workflow["jobs"]
    assert "astral-sh/setup-uv" in text
    assert "uv sync --locked --extra dev" in text
    assert "python -m pip download --no-deps" in text
    assert "uv run python -m pip download" not in text


def test_all_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    action_ref = re.compile(r"^[^@]+@[0-9a-f]{40}$")
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


def test_release_packaging_contract_contracts_match_script_contract() -> None:
    release = _workflow("release.yml")
    package = _package_script()

    release_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    manifest_fields = _manifest_field_block(release_text)
    assert "audioatlas-macos-app" in release_text
    assert "macos-distribution-manifest.json" in release_text
    for field in package.MANIFEST_REQUIRED_FIELDS:
        assert field in release_text
        assert field in manifest_fields
    assert set(package.MANIFEST_REQUIRED_FIELDS) <= manifest_fields
    assert release["jobs"]["macos-evidence"]["needs"] == ["prepare", "macos-app"]


def test_release_macos_handoff_requires_evidence_gating() -> None:
    evidence = _workflow("release.yml")["jobs"]["macos-evidence"]
    assert evidence["runs-on"] == "macos-14"
    steps = evidence.get("steps", [])
    names = [step.get("name", "") for step in steps]
    assert any(name == "Verify notarized DMG evidence artifacts" for name in names)
    assert "actions/download-artifact@" in steps[0]["uses"]
    assert evidence["needs"] == ["prepare", "macos-app"]

    release_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert release_text.count("notarization-log.json") >= 3
