from __future__ import annotations

import hashlib
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "examples" / "demo_audio"
EXPECTED = {
    "guitar.wav": {
        "sha256": "1ecba759cf090f06dc6446cba8ec392e2a10aeaa0dd2a6ad6e7b863a32ddc3b0",
        "frames": 607_131,
    },
    "guitar_koto_cello_drums.wav": {
        "sha256": "3735e5a3bf10d6038811643a65b2c6fde0a1cc704810fd73e843d568fc3c9d84",
        "frames": 1_159_891,
    },
}


def test_intended_demo_wavs_are_tracked_pcm16_stereo_44100() -> None:
    expected_paths = [f"examples/demo_audio/{name}" for name in EXPECTED]
    actual_paths = [path.relative_to(ROOT).as_posix() for path in sorted(DEMO_DIR.glob("*.wav"))]
    assert actual_paths == expected_paths

    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", "examples/demo_audio/*.wav"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert tracked == expected_paths

    for filename, expected in EXPECTED.items():
        path = DEMO_DIR / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"]
        with wave.open(str(path), "rb") as source:
            assert source.getnchannels() == 2
            assert source.getsampwidth() == 2
            assert source.getframerate() == 44_100
            assert source.getnframes() == expected["frames"]
            assert source.getcomptype() == "NONE"
