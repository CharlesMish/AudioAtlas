from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from audioatlas.cli import main
from audioatlas.errors import AudioLoadError
from audioatlas.io import load_audio

FIXTURES = Path(__file__).parent / "fixtures" / "malformed"
MALFORMED_FILES = tuple(sorted(FIXTURES.iterdir()))


@pytest.mark.parametrize("fixture", MALFORMED_FILES, ids=lambda path: path.name)
def test_committed_malformed_fixtures_raise_redacted_domain_error(
    fixture: Path, tmp_path: Path
) -> None:
    private = tmp_path / "private user" / fixture.name
    private.parent.mkdir()
    shutil.copyfile(fixture, private)

    with pytest.raises(AudioLoadError) as caught:
        load_audio(private)

    message = str(caught.value)
    assert private.name in message
    assert str(private.parent) not in message
    assert str(tmp_path) not in message
    assert "Traceback" not in message


@pytest.mark.parametrize("fixture", MALFORMED_FILES, ids=lambda path: path.name)
def test_analyze_cli_keeps_malformed_file_errors_concise(
    fixture: Path, tmp_path: Path
) -> None:
    private = tmp_path / "private layout" / fixture.name
    private.parent.mkdir()
    shutil.copyfile(fixture, private)

    result = CliRunner().invoke(
        main,
        ["analyze", str(private), "--out", str(tmp_path / "report")],
    )

    assert result.exit_code != 0
    assert f"Could not read audio file '{fixture.name}'" in result.output
    assert str(private.parent) not in result.output
    assert str(tmp_path) not in result.output
    assert "Traceback" not in result.output
    assert not (tmp_path / "report").exists()


def test_batch_records_all_malformed_supported_files_without_leaking_paths(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "private person" / "audio inputs"
    input_dir.mkdir(parents=True)
    for fixture in MALFORMED_FILES:
        shutil.copyfile(fixture, input_dir / fixture.name)
    out = tmp_path / "catalog"

    result = CliRunner().invoke(
        main,
        ["batch", str(input_dir), "--out", str(out), "--graphs-profile", "minimal"],
    )

    assert result.exit_code != 0
    catalog_text = (out / "catalog_summary.json").read_text(encoding="utf-8")
    catalog = json.loads(catalog_text)
    assert catalog["track_count"] == 0
    assert len(catalog["skipped_files"]) == len(MALFORMED_FILES)
    assert {item["filename"] for item in catalog["skipped_files"]} == {
        path.name for path in MALFORMED_FILES
    }
    assert all(item["status"] == "analysis_failed" for item in catalog["skipped_files"])
    assert str(input_dir) not in catalog_text
    assert str(tmp_path) not in catalog_text
    assert "Traceback" not in catalog_text
