# AudioAtlas Architecture

This document explains the layering of AudioAtlas so an agent (or new
contributor) can place new code in the right place without rediscovering
the conventions from source.

## One-paragraph summary

AudioAtlas is a thin, deterministic pipeline that runs a fixed set of
**analysis** functions on one audio file, hands their dataclass results to
matching **visualization** functions and **report** writers, and emits a
directory containing PNGs, Markdown/HTML reports, and JSON summaries.
There is no statefulness, no plugin system, and no implicit configuration.

## The four layers

```
   ┌─────────────────────────────────────────────────────────────┐
   │ cli.py                  ──  argparse + Click only           │
   │   ↓                                                         │
   │ pipeline.py             ──  thin orchestrator               │
   │   ↓                          (no DSP, no plotting)          │
   │ analysis/*.py           ──  pure arrays → dataclasses       │
   │   (levels, spectral, ...)    no file paths, no matplotlib   │
   │   ↓                                                         │
   │ visualize/*.py          ──  dataclass → PNG                 │
   │   (waveform, ...)            no re-analysis allowed         │
   │   ↓                                                         │
   │ report.py/html_report.py ──  dict → report.md/html/json     │
   └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       reports/<name>/
                       ├── summary.json
                       ├── findings.json
                       ├── report.md
                       ├── report.html
                       └── 0N_*.png
```

### Layer rules (enforced by code review, not by tests)

| Layer | Allowed to import | Forbidden |
|---|---|---|
| `analysis/*` | numpy, scipy, librosa, pyloudnorm, `config`, `utils` | matplotlib, file paths, `io`, `pipeline` |
| `visualize/*` | matplotlib, the analysis dataclasses it plots | re-running analysis, soundfile, `io` |
| `pipeline.py` | all analysis + visualize + report + io | DSP math, matplotlib calls |
| `cli.py` | click + pipeline | DSP math, matplotlib, IO besides paths |
| `report.py` / `html_report.py` | stdlib only, plus `utils` | DSP math, matplotlib, plotting |
| `io.py` | soundfile + utils | DSP math, plotting |

If you find yourself wanting to break one of these (e.g. "I just need
matplotlib in `analysis/spectral.py` to debug"), the answer is: don't.
That code goes in `visualize/` or in a scratch notebook outside the package.

## The shape of a "feature slice"

Adding a new measurement (e.g. spectral centroid) is exactly seven steps:

1. **Dataclass.** Add a `frozen=True` result dataclass in
   `analysis/<topic>.py`. Include `sample_rate: int` if you have a time
   axis. Include `to_summary_dict()` returning a small JSON-safe dict.
2. **Pure function.** Implement `compute_<thing>(y, sr, config) -> Result`.
   - `y` has shape `(n_samples, n_channels)`. Use `to_mono` if you want
     a single-channel input.
   - Read all tunables from `config: AnalysisConfig`. Don't sneak in
     module-level constants.
   - Never normalize the input.
3. **Tests.** Add `tests/test_<topic>.py` using synthetic signals from
   `tests/conftest.py`. Cover at minimum: shape, monotone behavior on
   a known input, edge case of too-short or silent audio.
4. **Visualization** (if there's something to look at). Add
   `visualize/<topic>.py` with a function that takes the result
   dataclass and an `out_path`. Do not pass `sr` separately if the
   dataclass carries it.
5. **Summary entry.** Add a key in the summary dict in `pipeline.py`,
   sourced from `result.to_summary_dict()`.
6. **Report entry.** Update `report.py` so the Markdown report includes
   the new metric. If you added a plot, the existing `## Plots` loop
   will pick it up automatically as long as you appended its path to
   `plot_paths` in `pipeline.py`.
7. **Pipeline wiring.** In `pipeline.py`:
   - Import the compute function and the plot function.
   - Add one line that calls compute on `audio.y, audio.sr, cfg`.
   - Add one line appending the plot path to `plot_paths`.
   - Add one entry to the `summary` dict.

This is the *only* shape AudioAtlas supports. If your idea doesn't fit
this shape, propose a separate module rather than bending the layering.

## Things that are intentionally not here

- **No plugin system.** Stay declarative in `pipeline.py`. If a future
  v0.3 wants user-supplied analyses, that's a deliberate redesign, not
  an incremental extension.
- **No automated mastering advice / judgments / scores.** Hard rule from
  `AGENT_BRIEF.md`. The product is facts and visualizations.
- **No reference-track comparison.** Out of scope for v0.1 - v0.2.
- **No hosted report app.** Static `report.html` is generated locally;
  Streamlit, servers, PDF export, and playback UI remain out of scope.
- **No real-time / playback UI.**
- **No section segmentation** unless explicitly marked experimental and
  off by default.

## Configuration

`audioatlas.config.AnalysisConfig` is a frozen dataclass holding every
tunable used by the analysis layer. If you need a new knob:

- Add it to `AnalysisConfig` with a sensible default.
- Add a `validate()` check if the field has constraints.
- Expose it as a CLI flag in `cli.py` only if a user is realistically
  going to want to change it.

The config is serialized in `summary.json` via
`dataclasses.asdict(cfg)`, so every run is reproducible from its own
output.

## The dB-floor convention

All dBFS / dBTP / dB-power values shown to the user are clamped to
`config.db_floor` (default `-100`). Use `linear_to_dbfs(..., floor_db=cfg.db_floor)`
and `power_to_db(..., floor_db=cfg.db_floor)` for this. Internal math
that needs raw values can pass `floor_db=None`.

Relative dB plots, such as spectrogram, Welch average spectrum, and
frequency-band timelines, use the track or analysis-view maximum as
0 dB. They are shape/contrast views, not calibrated dBFS meters.

A silent input must produce identical floor values in `levels.rms_dbfs`,
`levels.sample_peak_dbfs`, and the entire `rms_envelope.rms_dbfs` series.
There's a test for this in `tests/test_levels.py`.

## Naming honesty

Names must reflect what the numbers actually measure. The historical case
in this repo: the v0.1 timeline plot is `02_rms_timeline.png` and not
`02_loudness_timeline.png`, because it's RMS dBFS, not K-weighted
short-term LUFS. If you add a real short-term-LUFS timeline later, give
it its own filename - don't repurpose `rms_timeline`.

## Summary schema and stability

`summary.json` carries a `schema_version` field. v0.1.x stays at
`"0.1.0"`. If you change the shape of the summary (rename or remove a
field, change a type), bump it and update `docs/SUMMARY_SCHEMA.md` in
the same commit.
