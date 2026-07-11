from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import soundfile as sf


def _load_generator_module():
    path = Path(__file__).parents[1] / "scripts" / "generate_calibration_fixtures.py"
    spec = importlib.util.spec_from_file_location("audioatlas_fixture_generator", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_calibration_fixture_generator_is_deterministic_and_decodable(tmp_path):
    module = _load_generator_module()
    first = tmp_path / "first"
    second = tmp_path / "second"

    manifest_one = module.generate(first)
    manifest_two = module.generate(second)

    assert manifest_one == manifest_two
    assert json.loads((first / "manifest.json").read_text()) == manifest_one
    assert (first / "corrupt_header.wav").read_bytes() == (
        second / "corrupt_header.wav"
    ).read_bytes()

    for record in manifest_one["fixtures"]:
        path = first / record["filename"]
        assert path.exists()
        if record.get("expected_status") == "analysis_failed":
            continue
        info = sf.info(path)
        assert info.frames > 0
        assert info.samplerate == module.SAMPLE_RATE
