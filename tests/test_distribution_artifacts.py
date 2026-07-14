from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_free_sdist_has_a_coherent_distributed_test_contract(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(dist)],
        cwd=ROOT,
        check=True,
    )
    archive = next(dist.glob("audioatlas-*.tar.gz"))
    with tarfile.open(archive, "r:gz") as source:
        names = source.getnames()
        assert not any(name.endswith(".wav") and "/examples/demo_audio/" in name for name in names)
        assert any(name.endswith("/AUDIO_RIGHTS.md") for name in names)
        assert any(name.endswith("/tests/test_demo_audio.py") for name in names)
        assert not any(name.endswith("/tests/test_demo_audio_source.py") for name in names)
        assert not any(name.endswith("/tests/test_distribution_artifacts.py") for name in names)
        source.extractall(tmp_path / "extracted", filter="data")

    extracted = next((tmp_path / "extracted").iterdir())
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_demo_audio.py", "-q"],
        cwd=extracted,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
