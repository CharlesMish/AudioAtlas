from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_public_tree.py"


def _module():
    spec = importlib.util.spec_from_file_location("audioatlas_public_export", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_export_excludes_stewardship_material_but_keeps_user_contracts():
    module = _module()

    excluded = [
        "PROJECT_CHARTER.md",
        "docs/AGENT_TASKS.md",
        "docs/HOPEFUL_SKEPTIC_PROJECT_EDITION.md",
        "docs/LAUNCHER_REHEARSAL.md",
        "docs/calibration/README.md",
        "docs/stewardship/PUBLIC_RELEASE_MODEL.md",
        "scripts/prepare_calibration_review.py",
        "starter_kit/LAUNCHER_REHEARSAL_LOG.md",
        "tests/test_calibration_replay.py",
        "tests/test_public_export.py",
    ]
    included = [
        "AUDIO_RIGHTS.md",
        "README.md",
        "README_EASY_RUN.md",
        "docs/USER_GUIDE.md",
        "docs/FINDING_RULES.md",
        "docs/ALPHA_LIMITATIONS.md",
        "src/audioatlas/pipeline.py",
        "tests/test_pipeline.py",
        ".github/workflows/ci.yml",
        "examples/demo_audio/README.md",
        "examples/demo_audio/guitar.wav",
        "examples/demo_audio/guitar_koto_cello_drums.wav",
    ]

    assert all(module._is_stewardship_only(Path(path)) for path in excluded)
    assert not any(module._is_stewardship_only(Path(path)) for path in included)
