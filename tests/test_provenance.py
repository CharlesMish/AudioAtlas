from __future__ import annotations

import json

import pytest

from audioatlas.config import AnalysisConfig
from audioatlas.provenance import (
    build_analysis_provenance,
    canonical_json_sha256,
    track_identity_block,
)


def test_track_identity_is_deterministic_and_does_not_store_raw_token() -> None:
    token = "private-song-token-with-spaces"

    first = track_identity_block(token)
    second = track_identity_block(f"  {token}  ")

    assert first == second
    assert first["kind"] == "user-supplied-sha256"
    assert isinstance(first["track_id_sha256"], str)
    assert len(first["track_id_sha256"]) == 64
    assert token not in json.dumps(first)
    assert track_identity_block(None) == {"kind": "none", "track_id_sha256": None}


@pytest.mark.parametrize("value", ["", "   ", "line\nbreak", "null\x00byte"])
def test_track_identity_rejects_unsafe_or_empty_tokens(value: str) -> None:
    with pytest.raises(ValueError):
        track_identity_block(value)


def test_analysis_provenance_is_path_safe_and_configuration_sensitive(tmp_path) -> None:
    base = build_analysis_provenance(AnalysisConfig(true_peak_oversample=1))
    changed = build_analysis_provenance(AnalysisConfig(true_peak_oversample=4))

    assert base["format_version"] == 1
    for key in (
        "analysis_config_sha256",
        "measurement_code_sha256",
        "finding_rule_code_sha256",
        "compatible_analysis_sha256",
        "exact_environment_sha256",
    ):
        assert isinstance(base[key], str)
        assert len(base[key]) == 64
    assert base["analysis_config_sha256"] != changed["analysis_config_sha256"]
    assert base["compatible_analysis_sha256"] != changed["compatible_analysis_sha256"]
    assert base["measurement_code_sha256"] == changed["measurement_code_sha256"]
    assert base["measurement_methods"]["approximate_true_peak"]["oversample_factor"] == 1
    assert changed["measurement_methods"]["approximate_true_peak"]["oversample_factor"] == 4
    assert str(tmp_path) not in json.dumps(base)


def test_canonical_json_hash_is_order_independent() -> None:
    assert canonical_json_sha256({"a": 1, "b": [2, 3]}) == canonical_json_sha256(
        {"b": [2, 3], "a": 1}
    )
