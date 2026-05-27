# AudioAtlas Agent Brief

You are working on AudioAtlas, a local single-track audio analysis tool
intended for producers, mix engineers, mastering engineers, and deep
listeners.

If you only read one document, read this one. Then read
`docs/ARCHITECTURE.md` and `docs/AGENT_TASKS.md`.

---

## Product framing

AudioAtlas is a **song microscope**. It analyzes one audio file and
produces factual visual maps and metering-style measurements.

**It does not judge.** Avoid statements like "this mix is bad", "your low
end is muddy", or "needs more compression". Prefer measured facts:

- "Sample peak is -0.2 dBFS."
- "342 samples are above 0.99."
- "Integrated loudness: -10.8 LUFS."
- "RMS envelope rises by about 5 dB in the final chorus."

The human reading the report decides what to do about those numbers.

---

## Hard constraints

These are not negotiable. If a request seems to require breaking one,
push back rather than complying silently.

- Python package under `src/audioatlas`.
- Internal audio convention: `y.shape == (n_samples, n_channels)`. Use
  `audioatlas.utils.ensure_2d_audio` to enforce it at boundaries.
- **Do not auto-normalize input audio.** Original level matters; tools
  that quietly normalize are useless for mastering inspection.
- Analysis modules do not know about file paths. They take arrays in
  and return dataclasses out.
- Visualization modules do not recompute analysis. They render existing
  dataclass results.
- The CLI stays thin. All real work is in `pipeline.py` and below.
- Add tests for every new analysis function.
- Keep v0.1 boring and correct. Cleverness goes in v0.2+.
- All user-visible dBFS / dBTP / dB values are clamped to `cfg.db_floor`
  (default -100). Use `linear_to_dbfs(..., floor_db=cfg.db_floor)` and
  `power_to_db(..., floor_db=cfg.db_floor)`.
- Names must reflect what is measured. RMS is not loudness. Centroid is
  not "brightness." Don't paper over the difference with a marketing-y
  name.

---

## Stack

`numpy`, `scipy`, `soundfile`, `librosa`, `matplotlib`, `pyloudnorm`,
`click`, `pytest`. Don't add new top-level dependencies casually. If you
need one, declare it in `pyproject.toml` in the same change that uses it
and explain why in the commit message.

---

## The feature-slice recipe

Every measurement is added the same way. Don't skip steps and don't
reorder them.

1. **Dataclass** in `src/audioatlas/analysis/<topic>.py`.
2. **Pure function** `compute_<thing>(y, sr, config) -> Result`.
3. **Tests** in `tests/test_<topic>.py` using synthetic signals.
4. **Visualization** in `src/audioatlas/visualize/<topic>.py` if there's
   anything visual.
5. **Summary entry** added to the dict in `pipeline.py`.
6. **Report entry** in `report.py` (table row or section).
7. **Pipeline wiring** in `pipeline.py`: import, call, append plot,
   add summary key.

A complete worked example follows.

---

## Worked example: adding "zero-crossing rate" (hypothetical)

Suppose you've been asked to add a per-frame zero-crossing rate (ZCR)
measurement. Here's exactly what lands in each file. **This is a
template, not a task** — ZCR is not on the real roadmap.

### Step 1. Dataclass + function — `src/audioatlas/analysis/zcr.py`

```python
"""Zero-crossing rate analysis."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig
from audioatlas.utils import to_mono


@dataclass(frozen=True)
class ZcrResult:
    times_seconds: NDArray[np.float64]
    zcr: NDArray[np.float64]
    sample_rate: int
    frame_length: int
    hop_length: int

    def to_summary_dict(self) -> dict[str, object]:
        if len(self.zcr) == 0:
            return {"frames": 0}
        return {
            "frames": int(len(self.zcr)),
            "median": float(np.median(self.zcr)),
            "p90": float(np.percentile(self.zcr, 90)),
            "p10": float(np.percentile(self.zcr, 10)),
        }


def compute_zcr(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> ZcrResult:
    cfg = config or AnalysisConfig()
    cfg.validate()
    mono = to_mono(y)
    zcr = librosa.feature.zero_crossing_rate(
        y=mono,
        frame_length=cfg.rms_frame_length,
        hop_length=cfg.hop_length,
        center=True,
    )[0].astype(np.float64)
    times = librosa.frames_to_time(
        np.arange(len(zcr)), sr=sr, hop_length=cfg.hop_length
    ).astype(np.float64)
    return ZcrResult(
        times_seconds=times,
        zcr=zcr,
        sample_rate=int(sr),
        frame_length=cfg.rms_frame_length,
        hop_length=cfg.hop_length,
    )
```

### Step 2. Tests — `tests/test_zcr.py`

```python
import numpy as np
import pytest

from audioatlas.analysis.zcr import compute_zcr
from audioatlas.config import AnalysisConfig


def test_zcr_higher_for_high_frequency_sine(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048)
    t = np.arange(int(sr), dtype=np.float64) / sr

    low = (0.5 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)[:, None]
    high = (0.5 * np.sin(2 * np.pi * 5000 * t)).astype(np.float32)[:, None]

    low_zcr = float(np.median(compute_zcr(low, sr, cfg).zcr))
    high_zcr = float(np.median(compute_zcr(high, sr, cfg).zcr))

    assert high_zcr > low_zcr * 5
```

### Step 3. Visualization — `src/audioatlas/visualize/zcr.py`

```python
from __future__ import annotations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.zcr import ZcrResult


def plot_zcr(zcr: ZcrResult, out_path: str | Path,
             *, title: str = "Zero-Crossing Rate") -> Path:
    fig, ax = plt.subplots(figsize=(14, 3))
    ax.plot(zcr.times_seconds, zcr.zcr, linewidth=1.0)
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("ZCR")
    ax.set_ylim(0, max(0.5, float(zcr.zcr.max() * 1.1)))
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
```

### Step 4. Pipeline wiring — `src/audioatlas/pipeline.py`

```python
# Top imports
from audioatlas.analysis.zcr import compute_zcr
from audioatlas.visualize.zcr import plot_zcr

# Inside analyze_file, after the existing analyses:
zcr = compute_zcr(audio.y, audio.sr, cfg)

# Inside the plot_paths block:
plot_paths.append(plot_zcr(zcr, out / "06_zcr.png"))

# Inside the summary dict:
"zcr": zcr.to_summary_dict(),
```

### Step 5. Report — `src/audioatlas/report.py`

Add a `## ZCR summary` block in `write_report_md`, mirroring the
`## RMS envelope summary` block. The plot will pick itself up because
the existing `## Plots` loop iterates `plot_files`.

### Step 6. Schema doc — `docs/SUMMARY_SCHEMA.md`

Add a `### zcr` section describing the keys returned by
`ZcrResult.to_summary_dict()`. No `schema_version` bump (additive change).

### Step 7. CHANGELOG — `docs/CHANGELOG.md`

Add a bullet under `## Unreleased` describing the addition.

That's the entire shape. Every real task in `docs/AGENT_TASKS.md` follows
this template.

---

## Anti-patterns to avoid

- **Cross-layer imports.** If `analysis/foo.py` imports matplotlib, that
  is wrong. Move the plot to `visualize/`.
- **Recomputing in the visualizer.** Visualization receives dataclass
  results. If you need a new derived quantity for a plot, add it to the
  analysis function's result.
- **Module-level constants for tunables.** Put them in `AnalysisConfig`.
- **`pytest_approx` and similar one-file helpers.** Just `import pytest`
  and use `pytest.approx`. Don't invent local re-exports.
- **Quietly normalizing audio.** Don't.
- **Naming things aspirationally.** A function called
  `loudness_timeline` that returns RMS dBFS is a lie. Either name it
  `rms_timeline` or actually compute K-weighted short-term LUFS.
- **Verdicts in the report.** No "your mix is muddy", no "well mastered",
  no "needs more compression". `tests/test_report.py` checks a sample of
  banned phrases; if you add legitimate output that the test trips on,
  argue for the addition explicitly rather than just expanding the allow
  list.
- **Bypassing tests.** A new analysis function without tests is not done.

---

## Good first task

Start with `T-002` in `docs/AGENT_TASKS.md` — stereo correlation timeline.
It is visible, useful for mixing/mastering inspection, and easy to verify
with synthetic fixtures: mono/dual-mono should be near +1, phase-inverted
stereo should be near -1, and unrelated channels should be lower.

Do **not** start with `T-001` unless explicitly assigned. True-peak
refinement is valuable but subtle DSP work, and it is a poor first agent
pass.

After that, work down `AGENT_TASKS.md` unless a later task is genuinely
unblocked first.
