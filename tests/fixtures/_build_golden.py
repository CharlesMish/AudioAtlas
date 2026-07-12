"""Regenerate the golden fixture WAV and its expected-values JSON.

Run from the repo root:

    python tests/fixtures/_build_golden.py

The .wav and .expected.json files are checked into version control. This
script exists so an agent (or human) can reproduce them deterministically
if they need to be regenerated.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48_000
DURATION_SECONDS = 2.0


def main() -> None:
    fixtures = Path(__file__).resolve().parent
    fixtures.mkdir(parents=True, exist_ok=True)

    n = int(SR * DURATION_SECONDS)
    t = np.arange(n, dtype=np.float64) / SR

    # -6 dBFS peak, 1 kHz sine, mono. Stable, well-defined peak / RMS / spectrum.
    amp = 10 ** (-6.0 / 20.0)
    y = (amp * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    sf.write(fixtures / "sine_1k_-6dbfs_2s.wav", y, SR, subtype="PCM_16")

    expected = {
        "duration_seconds": DURATION_SECONDS,
        "sample_rate": SR,
        "channels": 1,
        "sample_peak_dbfs_approx": -6.0,
        "sample_peak_dbfs_tolerance": 0.5,
        "rms_dbfs_approx": -9.01,
        "rms_dbfs_tolerance": 0.5,
        "crest_factor_db_approx": 3.01,
        "crest_factor_db_tolerance": 0.5,
        "strongest_bin_hz_approx": 1000.0,
        "strongest_bin_hz_tolerance": 50.0,
        "clipped_samples": 0,
        "near_clipping_samples": 0,
    }
    (fixtures / "sine_1k_-6dbfs_2s.expected.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True), encoding="utf-8"
    )
    print("Wrote:", sorted(p.name for p in fixtures.iterdir()))


if __name__ == "__main__":
    main()
