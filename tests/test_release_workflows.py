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
    assert "--graphs-profile compact" in text
    assert "--graphs-profile full" in text
    assert "--theme default" in text
    assert "--presentation studio" in text
    assert 'summary["metadata"]["filename"] == "audioatlas_demo.wav"' in text
    assert 'profiles = {"compact": 4, "full": 17}' in text
    assert 'href="compact/"' in text
    assert 'href="full/"' in text
    assert ".github/pages-assets/audioatlas-0.2.0a8-release-hero.png" in text
    assert "rm site/compact/.audioatlas-output.json" in text
    assert "rm site/full/.audioatlas-output.json" in text
    assert "if path.is_file() and path.name != \".nojekyll\"" in text
    assert 'assert not list(site.rglob(".audioatlas-*"))' in text
    assert "assert not list(site.rglob(\"*.wav\"))" in text


def test_release_requires_version_tag_and_uses_trusted_publishing() -> None:
    workflow = _workflow("release.yml")

    assert workflow["on"] == {
        "push": {"tags": ["v*", "!v0.2.0a8"]},
        "workflow_dispatch": {
            "inputs": {
                "release_mode": {
                    "description": "Publication route",
                    "required": True,
                    "type": "choice",
                    "default": "python-only",
                    "options": ["python-only"],
                },
                "release_tag": {
                    "description": "Immutable release tag",
                    "required": True,
                    "type": "string",
                    "default": "v0.2.0a8",
                },
            }
        },
    }
    assert workflow["jobs"]["pypi"]["permissions"] == {
        "actions": "read",
        "id-token": "write",
    }
    assert workflow["jobs"]["pypi"]["environment"]["name"] == "pypi"
    assert workflow["jobs"]["draft-release"]["environment"]["name"] == "github-release"
    assert workflow["jobs"]["finalize-release"]["environment"]["name"] == "github-release"
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "pypa/gh-action-pypi-publish@" in text
    assert "git merge-base --is-ancestor" in text
    assert "testpypi.yml/runs?head_sha=${source_commit}&status=success" in text
    assert "--draft" in text
    assert "--draft=false" in text
    assert "--require-present" in text
    assert "uv sync --locked --extra dev" in text
    assert "uv run python -m build" in text
    assert "uv run --with twine python -m twine check dist/*" in text
    assert "uv run python -m twine check dist/*" not in text
    assert "uv run python -m pytest" in text
    assert "uv run pytest" not in text
    assert "uv run pip-audit --require-hashes" in text


def test_python_only_release_is_manual_exact_and_native_free() -> None:
    workflow = _workflow("release.yml")
    jobs = workflow["jobs"]
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert workflow["permissions"] == {"contents": "read", "actions": "read"}
    assert "pull_request" not in workflow["on"]

    assert jobs["prepare"]["outputs"]["release_mode"] == (
        "${{ steps.package.outputs.release_mode }}"
    )
    assert jobs["prepare"]["outputs"]["release_tag"] == (
        "${{ steps.package.outputs.release_tag }}"
    )
    assert jobs["prepare"]["outputs"]["source_commit"] == (
        "${{ steps.package.outputs.source_commit }}"
    )
    assert 'test "${GITHUB_REF}" = "refs/heads/main"' in text
    assert 'test "${version}" = "0.2.0a8"' in text
    assert 'release_mode="python-only"' in text
    assert 'release_mode="native"' in text
    assert 'test "${GITHUB_SHA}" = "$(git rev-parse origin/main)"' in text
    assert 'test "${GITHUB_SHA}" != "${expected_source_commit}"' in text

    expected_tag_object = "c54c85baaa7f7fa7f25d900a585be99e7f75879a"
    expected_source_commit = "bab9802e786caadfeb2bb609a49a062a0a93c074"
    assert f'expected_tag_object="{expected_tag_object}"' in text
    assert f'expected_source_commit="{expected_source_commit}"' in text
    assert (
        'test "$(git cat-file -t "refs/tags/${RELEASE_TAG_INPUT}")" = "tag"'
        in text
    )
    assert (
        'test "$(git rev-parse "refs/tags/${RELEASE_TAG_INPUT}")" = '
        '"${expected_tag_object}"' in text
    )
    assert (
        'test "$(git rev-parse "refs/tags/${RELEASE_TAG_INPUT}^{}")" = '
        '"${expected_source_commit}"' in text
    )
    assert (
        'git ls-remote --refs --tags origin "refs/tags/${RELEASE_TAG_INPUT}"'
        in text
    )
    assert (
        'git ls-remote --tags origin "refs/tags/${RELEASE_TAG_INPUT}^{}"'
        in text
    )
    assert 'test "$(git rev-parse HEAD)" = "${expected_source_commit}"' in text

    prepare_checkout = jobs["prepare"]["steps"][0]
    assert prepare_checkout["with"]["fetch-depth"] == 0
    assert prepare_checkout["with"]["ref"] == (
        "${{ github.event_name == 'workflow_dispatch' && "
        f"'{expected_source_commit}' || github.sha }}}}"
    )
    for job_name in ("macos-app", "index-state", "verify-index", "pypi-smoke"):
        checkout = jobs[job_name]["steps"][0]
        assert checkout["with"]["ref"] == "${{ needs.prepare.outputs.source_commit }}"

    for forbidden in (
        "git tag ",
        "git push",
        "git update-ref",
        "--force",
        "gh api -X DELETE",
    ):
        assert forbidden not in text

    for native_job in ("macos-app", "macos-evidence", "macos-acceptance", "draft-release"):
        assert jobs[native_job]["if"] == "needs.prepare.outputs.release_mode == 'native'"

    python_assets = jobs["python-release-assets"]
    assert python_assets["needs"] == [
        "prepare",
        "macos-app",
        "macos-evidence",
        "macos-acceptance",
    ]
    assert python_assets["permissions"] == {"contents": "write", "actions": "read"}
    assert "needs.prepare.outputs.release_mode == 'python-only'" in python_assets["if"]
    assert all(
        "actions/checkout@" not in step.get("uses", "")
        for step in python_assets["steps"]
    )
    python_assets_commands = "\n".join(
        step.get("run", "") for step in python_assets["steps"]
    )
    assert python_assets_commands.count("gh release view") == 3
    assert python_assets_commands.count("gh release download") == 1
    for forbidden in (
        "gh release create",
        "gh release edit",
        "gh release upload",
        "gh release delete",
        "gh api",
        "git push",
        "git tag",
        "git update-ref",
    ):
        assert forbidden not in python_assets_commands
    assert 'test "${MACOS_APP_RESULT}" = "skipped"' in text
    assert 'test "${MACOS_EVIDENCE_RESULT}" = "skipped"' in text
    assert 'test "${MACOS_ACCEPTANCE_RESULT}" = "skipped"' in text
    assert jobs["pypi"]["needs"] == ["prepare", "index-state", "release-assets-ready"]
    assert jobs["pypi"]["if"] == (
        "${{ always() && needs.prepare.result == 'success' && "
        "needs.index-state.result == 'success' && "
        "needs.release-assets-ready.result == 'success' }}"
    )
    assert "needs.pypi.result == 'success'" in jobs["verify-index"]["if"]
    assert "needs.pypi.result == 'skipped'" not in jobs["verify-index"]["if"]

    expected_assets = {
        "audioatlas-0.2.0a8-py3-none-any.whl",
        "audioatlas-0.2.0a8.tar.gz",
        "AudioAtlas-0.2.0a8-public-source-3c9841e.zip",
        "AudioAtlas-0.2.0a8-canonical-compact-example-3c9841e.zip",
        "AudioAtlas-0.2.0a8-canonical-full-example-3c9841e.zip",
        "SHA256SUMS.txt",
        "ARTIFACT_MANIFEST.json",
    }
    for asset in expected_assets:
        assert text.count(f'"{asset}"') >= 2
    for digest in (
        "f4546ca18499299a8108312a95f9e1d527565ecc8e8fea62f64144b7b5a7fde7",
        "9ccb7566ac5c8cf4c5eaaaa8728b99a80f7f4b3da283350901b9754a83733c0c",
        "d9f83ec1c3a88fe72db0a89ae64d5eb3442cb95bbdc799a0a2b84a3261e50968",
        "4e13a63daa1307c5798035c75b334d7bc5a84a294f8a4bebeb0bf263f62cfa1c",
        "9d6bff6a6018c6040bdb3e74e4e9d6e5066e3ea3dbf153fd6e9478145ea4c296",
        "ef43619285432430e5bb8565b0b2d476fe1882d96818a9c044770a5b22b12ade",
        "6c039a367ed5cf3569d3de2b83eb6361c945404d33f033928469ff2f128d61ca",
    ):
        assert text.count(digest) == 2
    for size in (166024, 1442625, 19576394, 2203840, 4025986, 659, 2709):
        assert f'"size": {size}' in text
    assert "Release asset size mismatch" in text
    assert "Release asset boundary mismatch" in text
    assert "Release asset boundary changed after PyPI verification" in text
    assert "AudioAtlas 0.2.0a8 — Public Alpha" in text


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
    assert "0.2.0a8" not in text
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


def test_private_windows_candidate_workflow_cannot_publish() -> None:
    workflow = _workflow("windows-demo-candidate.yml")
    text = (ROOT / ".github" / "workflows" / "windows-demo-candidate.yml").read_text(
        encoding="utf-8"
    )

    assert workflow["on"] == {"workflow_dispatch": {}}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["build-internal-candidate"]
    assert job["runs-on"] == "windows-2022"
    assert "refs/heads/main" in text
    assert "scripts/build_windows_app.py" in text
    assert "scripts/package_windows_candidate.py" in text
    assert "innosetup-7.0.2-x64.exe" in text
    assert "gh release verify is-7_0_2 --repo jrsoftware/issrc" in text
    assert "gh release verify-asset is-7_0_2 $tool --repo jrsoftware/issrc" in text
    assert "Get-AuthenticodeSignature" in text
    assert "--ui-smoke" in text
    assert "scripts/audit_windows_distribution.py" in text
    assert "scripts/verify_windows_candidate.py" in text
    assert "candidate-extracted" in text
    assert "$env:LOCALAPPDATA/Programs/AudioAtlas" in text
    assert "/DIR=$installRoot" not in text
    assert "install-fresh.log" in text
    assert "install-upgrade.log" in text
    assert "uninstall.log" in text
    assert "if: always()" in text
    assert "retention-days: 14" in text
    for step in job["steps"]:
        if step.get("shell") == "pwsh":
            run = step.get("run", "")
            assert "$ErrorActionPreference = 'Stop'" in run
            assert "$PSNativeCommandUseErrorActionPreference = $true" in run
    for promised in (
        "README_FIRST.txt",
        "windows-candidate-manifest.json",
        "*-installer-test-kit.zip",
        "*-installer-test-kit.zip.sha256",
        "*-portable-test-kit.zip",
        "*-portable-test-kit.zip.sha256",
        "candidate-verification.json",
    ):
        assert promised in text
    uploads = [step for step in job["steps"] if "actions/upload-artifact@" in step.get("uses", "")]
    assert len(uploads) == 3
    diagnostic_upload = next(
        step for step in uploads if step["with"]["name"].endswith("-diagnostics")
    )
    assert diagnostic_upload["if"] == "always()"
    assert diagnostic_upload["with"]["path"] == "dist/windows/evidence"
    successful_uploads = [step for step in uploads if step is not diagnostic_upload]
    assert all(step["if"] == "success()" for step in successful_uploads)
    assert all(
        "windows-candidate-manifest.json" in step["with"]["path"] for step in successful_uploads
    )
    assert "*-setup.exe" not in "\n".join(
        str(step["with"]["path"]) for step in successful_uploads
    )
    assert "*-portable.zip\n" not in "\n".join(
        str(step["with"]["path"]) for step in successful_uploads
    )
    for forbidden in (
        "gh release create",
        "twine upload",
        "gh-action-pypi-publish",
        "git tag",
    ):
        assert forbidden not in text


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
    assert "uv run --with twine python -m twine check dist/*" in text
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
