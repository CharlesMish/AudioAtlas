from __future__ import annotations

import tomllib
from pathlib import Path

import audioatlas
from audioatlas.release import (
    CALIBRATION_REPLAY_SCHEMA_VERSION,
    CATALOG_SCHEMA_VERSION,
    FINDING_RULESET_VERSION,
    FINDINGS_SCHEMA_VERSION,
    RELEASE_LABEL,
    REVISION_DIFF_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
)

ROOT = Path(__file__).resolve().parents[1]


def test_package_and_project_versions_match():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == audioatlas.__version__


def test_release_contract_has_one_consistent_alpha_identity():
    assert audioatlas.RELEASE_LABEL == RELEASE_LABEL
    assert audioatlas.SUMMARY_SCHEMA_VERSION == SUMMARY_SCHEMA_VERSION
    assert audioatlas.FINDINGS_SCHEMA_VERSION == FINDINGS_SCHEMA_VERSION
    assert audioatlas.CATALOG_SCHEMA_VERSION == CATALOG_SCHEMA_VERSION
    assert audioatlas.REVISION_DIFF_SCHEMA_VERSION == REVISION_DIFF_SCHEMA_VERSION
    assert audioatlas.CALIBRATION_REPLAY_SCHEMA_VERSION == CALIBRATION_REPLAY_SCHEMA_VERSION
    assert audioatlas.FINDING_RULESET_VERSION == FINDING_RULESET_VERSION
    assert "alpha 4" in RELEASE_LABEL
    assert audioatlas.__version__ == "0.2.0a4"
    assert SUMMARY_SCHEMA_VERSION == "0.2.1"
    assert FINDINGS_SCHEMA_VERSION == CATALOG_SCHEMA_VERSION == "0.2.0"
    assert REVISION_DIFF_SCHEMA_VERSION == CALIBRATION_REPLAY_SCHEMA_VERSION == "0.1.0"
    # This pass changes calibration and delivery workflow, not finding semantics.
    assert FINDING_RULESET_VERSION == "0.2.0a2"
    assert audioatlas.__version__ != FINDING_RULESET_VERSION


def test_declared_license_file_exists_and_is_not_empty():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    license_path = ROOT / pyproject["project"]["license"]["file"]

    assert license_path.is_file()
    assert "MIT License" in license_path.read_text(encoding="utf-8")


def test_runtime_dependency_contract_pins_verified_numba_line():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "numba>=0.65.1,<0.66" in dependencies
