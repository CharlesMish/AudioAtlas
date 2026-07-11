from __future__ import annotations

import tomllib
from pathlib import Path

import audioatlas
from audioatlas.release import (
    CATALOG_SCHEMA_VERSION,
    FINDING_RULESET_VERSION,
    FINDINGS_SCHEMA_VERSION,
    RELEASE_LABEL,
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
    assert audioatlas.FINDING_RULESET_VERSION == FINDING_RULESET_VERSION
    assert "alpha 2" in RELEASE_LABEL
    assert SUMMARY_SCHEMA_VERSION == FINDINGS_SCHEMA_VERSION == CATALOG_SCHEMA_VERSION == "0.2.0"
    assert audioatlas.__version__ == FINDING_RULESET_VERSION


def test_declared_license_file_exists_and_is_not_empty():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    license_path = ROOT / pyproject["project"]["license"]["file"]

    assert license_path.is_file()
    assert "MIT License" in license_path.read_text(encoding="utf-8")
