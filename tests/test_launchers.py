from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _launcher_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "AudioAtlas With Spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    launcher = scripts / "run_audioatlas_mac.command"
    shutil.copy2(ROOT / "scripts" / launcher.name, launcher)
    return root, launcher


def test_mac_launcher_reports_missing_command_and_waits(tmp_path: Path) -> None:
    _, launcher = _launcher_tree(tmp_path)
    result = subprocess.run(
        ["/bin/bash", str(launcher)],
        input="\n",
        text=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode == 1
    assert "AudioAtlas was not found" in result.stdout
    assert "Press Return to close this window" in result.stdout


def test_mac_launcher_preserves_paths_and_reports_analysis_failure(tmp_path: Path) -> None:
    root, launcher = _launcher_tree(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "audioatlas"
    fake.write_text("#!/bin/bash\nprintf '%s\\n' \"$@\"\nexit 7\n", encoding="utf-8")
    fake.chmod(0o755)
    input_dir = root / "input_audio"
    input_dir.mkdir()
    keep = input_dir / "keep me.txt"
    keep.write_text("human file\n", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    result = subprocess.run(
        ["/bin/bash", str(launcher)],
        input="\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 7
    assert str(input_dir) in result.stdout
    assert str(root / "output_reports") in result.stdout
    assert "failed with exit status 7" in result.stdout
    assert keep.read_text(encoding="utf-8") == "human file\n"
