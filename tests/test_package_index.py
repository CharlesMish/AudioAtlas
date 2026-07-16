from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from scripts.check_package_index import compare_release, distribution_hashes


def _write_distributions(root: Path) -> dict[str, str]:
    (root / "audioatlas-0.2.0a7-py3-none-any.whl").write_bytes(b"wheel")
    (root / "audioatlas-0.2.0a7.tar.gz").write_bytes(b"source")
    return distribution_hashes(root)


def _payload(version: str, hashes: dict[str, str]) -> dict:
    return {
        "releases": {
            version: [
                {"filename": name, "digests": {"sha256": digest}}
                for name, digest in hashes.items()
            ]
        }
    }


def test_distribution_hashes_requires_one_wheel_and_one_sdist(tmp_path: Path) -> None:
    expected = _write_distributions(tmp_path)

    assert expected == {
        "audioatlas-0.2.0a7-py3-none-any.whl": hashlib.sha256(b"wheel").hexdigest(),
        "audioatlas-0.2.0a7.tar.gz": hashlib.sha256(b"source").hexdigest(),
    }


def test_compare_release_distinguishes_absent_and_exact(tmp_path: Path) -> None:
    expected = _write_distributions(tmp_path)

    assert compare_release(None, version="0.2.0a7", expected=expected) == "absent"
    assert compare_release({"releases": {}}, version="0.2.0a7", expected=expected) == "absent"
    assert (
        compare_release(_payload("0.2.0a7", expected), version="0.2.0a7", expected=expected)
        == "exact"
    )


def test_compare_release_refuses_digest_or_file_conflicts(tmp_path: Path) -> None:
    expected = _write_distributions(tmp_path)
    conflicting = dict(expected)
    conflicting["audioatlas-0.2.0a7.tar.gz"] = "0" * 64

    with pytest.raises(ValueError, match="conflicts with prepared distributions"):
        compare_release(
            _payload("0.2.0a7", conflicting),
            version="0.2.0a7",
            expected=expected,
        )
