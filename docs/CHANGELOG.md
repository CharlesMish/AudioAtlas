# Changelog

All notable changes to AudioAtlas are recorded here. Format roughly
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added
- Time-varying frequency band energy analysis with
  `band_energy_timeline` summary output, `09_band_energy_timeline.png`,
  and factual relative-to-track band findings.
- Spectral shape timeline analysis with centroid, 85%/95% rolloff, and
  bandwidth summaries, `08_spectral_shape.png`, and factual
  spectral-shape findings based on relative-to-track heuristics.
- Time-ranged findings for near-clipping, low stereo correlation, and
  high side-to-mid ratio observations.
- `peak_timeline` summary block with frame-wise clipping and
  near-clipping counts plus near-clipping time ranges.
- Named average-spectrum band energy summaries and strongest-band
  findings using factual suggested-check wording.
- First-pass `findings.json` and `## Findings` report section generated
  from existing summary metrics, using factual evidence and suggested
  checks rather than mix scores or advice.
- Stereo correlation timeline analysis with `stereo_correlation` summary
  output, a Markdown report section, and `06_stereo_correlation.png`.
  Undefined zero-variance frames remain `NaN` internally and are excluded
  from summary statistics.
- Mid/side RMS energy timeline analysis with `mid_side_energy` summary
  output, a Markdown report section, and `07_mid_side_energy.png`.
- `docs/AGENT_START_PROMPT.md` with a ready-to-paste first prompt for
  Codex/Grok Build, defaulting to the stereo-correlation feature slice.
- `true_peak_linear_per_channel` and `true_peak_dbtp_per_channel` fields
  on `ScalarLevelsResult` and in `summary.json`. Closes an asymmetry
  where the global true-peak was exposed but no per-channel breakdown
  existed (unlike `peak_dbfs_per_channel` and `rms_dbfs_per_channel`).
- Dedicated `## Per-channel breakdown` section in `report.md` listing all
  per-channel arrays as one column per channel.
- `PER_CHANNEL_METRIC_DISPLAY` registry in `report.py` so adding new
  per-channel metrics is a single-line change.
- Tests covering per-channel true-peak symmetry (asymmetric L/R stereo
  reflects channel amplitudes correctly; global equals max-of-channels;
  nullability tracks the global value) and the new report section.

### Changed
- Relabeled spectrogram and average-spectrum wording to avoid implying
  calibrated dBFS where the plotted STFT/Welch values are relative.
- Normalized spectrogram and average-spectrum dB displays to the track
  maximum so the strongest displayed bin is 0 dB.
- Stereo correlation now treats frames below `correlation_min_rms_dbfs`
  as undefined so low-energy fade-outs do not dominate plot or summary
  readings.
- Mid/side energy plot now includes a side-to-mid ratio panel.
- RMS timeline plot title now says "Frame RMS Timeline" to avoid implying
  a loudness model.
- Sample histogram x-axis now expands beyond ±1.0 for float WAV or other
  over-nominal-full-scale input.
- Reprioritized the agent backlog so stereo correlation is the recommended
  first feature slice; true-peak refinement is marked as advanced.
- Moved `dc_offset_per_channel` from the main `## Level metrics` table
  into the new `## Per-channel breakdown` section. The main table is now
  globals-only, which makes the per-channel block read consistently for
  every per-channel metric.

---

## 0.1.0 — initial framework

### Added
- Python package skeleton under `src/audioatlas/`.
- `audioatlas analyze` CLI with `--out`, `--max-duration`, `--n-fft`,
  `--hop-length`, `--rms-frame-length`, `--db-floor`,
  `--true-peak-oversample`.
- `python -m audioatlas ...` entry point.
- Audio loading via `soundfile` with internal shape
  `(n_samples, n_channels)`. No auto-normalization.
- `AnalysisConfig` frozen dataclass with `validate()`.
- `compute_scalar_levels` (sample peak, true-peak approximation, RMS,
  crest factor, integrated LUFS, PLR, clipping & near-clipping counts,
  per-channel breakdowns, DC offset, warnings).
- `compute_rms_envelope` (RMS dBFS timeline).
- `compute_log_spectrogram` (STFT magnitude in dB, log freq axis).
- `compute_average_spectrum` (Welch).
- Plots: `01_waveform_rms.png`, `02_rms_timeline.png`,
  `03_log_spectrogram.png`, `04_average_spectrum.png`,
  `05_sample_histogram.png`.
- `summary.json` (with `schema_version`) and `report.md`.
- 39 tests including a golden-fixture end-to-end snapshot.
- Documentation: `AGENT_BRIEF.md`, `docs/ARCHITECTURE.md`,
  `docs/SUMMARY_SCHEMA.md`, `docs/AGENT_TASKS.md`.
- Stub modules for v0.2 features:
  `analysis/stereo.py`, `analysis/spectral_features.py`,
  `analysis/tonal.py`.
- `Makefile` with `test`, `check`, `lint`, `demo`, `clean`.
- GitHub Actions CI workflow.

### Design decisions baked in
- All user-visible dB-style values clamp to `cfg.db_floor` (default
  `-100`).
- Spectral result dataclasses carry `sample_rate` so visualization
  functions don't need an extra `sr` argument.
- The v0.1 "timeline" plot is named `rms_timeline`, not
  `loudness_timeline`. A real short-term-LUFS timeline is deferred to
  `T-006` in `docs/AGENT_TASKS.md`.
- `lra_lu` is deliberately not present in v0.1 — added in `T-007`.
- Markdown report only; HTML report deferred to `T-008`.
