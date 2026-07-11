#!/usr/bin/env python3
"""Generate rights-safe deterministic audio fixtures for AudioAtlas calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 44_100
DURATION_SECONDS = 2.0


def _time(duration: float = DURATION_SECONDS) -> np.ndarray:
    return np.arange(int(round(SAMPLE_RATE * duration)), dtype=np.float64) / SAMPLE_RATE


def _write(path: Path, audio: np.ndarray, *, subtype: str = "PCM_16") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.asarray(audio, dtype=np.float32), SAMPLE_RATE, subtype=subtype)


def generate(output_dir: Path) -> dict[str, object]:
    """Generate deterministic public fixtures and return their manifest."""

    output_dir.mkdir(parents=True, exist_ok=True)
    t = _time()
    sine = 0.5 * np.sin(2.0 * np.pi * 1_000.0 * t)
    multitone = (
        0.20 * np.sin(2.0 * np.pi * 80.0 * t)
        + 0.18 * np.sin(2.0 * np.pi * 440.0 * t)
        + 0.14 * np.sin(2.0 * np.pi * 5_000.0 * t)
    )

    rng = np.random.default_rng(20_260_711)
    left_noise = rng.normal(0.0, 0.12, len(t))
    right_noise = rng.normal(0.0, 0.12, len(t))

    impulse = np.zeros_like(t)
    impulse[:: SAMPLE_RATE // 4] = 0.9

    clipped = 1.4 * np.sin(2.0 * np.pi * 220.0 * t)
    clipped = np.clip(clipped, -1.0, 1.0)

    fixtures: list[tuple[str, np.ndarray, str, str]] = [
        ("silence.wav", np.zeros((len(t), 1)), "PCM_16", "silence / floor handling"),
        ("sine_1k_minus_6dbfs.wav", sine[:, None], "PCM_16", "narrow-band deterministic tone"),
        ("multitone.wav", multitone[:, None], "PCM_16", "known broad spectral components"),
        ("impulses.wav", impulse[:, None], "PCM_16", "sparse transient and crest behavior"),
        ("dual_mono.wav", np.column_stack([sine, sine]), "PCM_16", "correlation near +1"),
        ("anti_phase.wav", np.column_stack([sine, -sine]), "PCM_16", "correlation near -1"),
        (
            "decorrelated_stereo.wav",
            np.column_stack([left_noise, right_noise]),
            "PCM_16",
            "seeded low-correlation stereo",
        ),
        ("clipped_flat_tops.wav", clipped[:, None], "PCM_16", "stored samples at full scale"),
        (
            "over_nominal_float.wav",
            (1.1 * np.sin(2.0 * np.pi * 997.0 * t))[:, None],
            "FLOAT",
            "floating-point samples above nominal full scale",
        ),
        (
            "short_100ms.wav",
            (0.5 * np.sin(2.0 * np.pi * 440.0 * _time(0.1)))[:, None],
            "PCM_16",
            "short-input warning and padding behavior",
        ),
    ]

    records: list[dict[str, object]] = []
    for filename, audio, subtype, purpose in fixtures:
        path = output_dir / filename
        _write(path, audio, subtype=subtype)
        info = sf.info(path)
        records.append(
            {
                "filename": filename,
                "purpose": purpose,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "frames": info.frames,
                "subtype": info.subtype,
            }
        )

    corrupt_path = output_dir / "corrupt_header.wav"
    corrupt_path.write_bytes(b"RIFF-not-a-valid-audio-file\x00\x01AudioAtlas")
    records.append(
        {
            "filename": corrupt_path.name,
            "purpose": "friendly decoder failure and partial batch success",
            "expected_status": "analysis_failed",
        }
    )

    manifest: dict[str, object] = {
        "format": "audioatlas-calibration-fixtures",
        "version": 1,
        "license": "MIT; project-generated synthetic fixtures with no third-party audio",
        "sample_rate": SAMPLE_RATE,
        "seed": 20_260_711,
        "fixtures": records,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_dir",
        nargs="?",
        type=Path,
        default=Path("calibration_audio/generated"),
        help="Destination folder (default: calibration_audio/generated)",
    )
    args = parser.parse_args()
    manifest = generate(args.output_dir)
    print(f"Generated {len(manifest['fixtures'])} fixtures in {args.output_dir}")


if __name__ == "__main__":
    main()
