# Changelog

All notable changes to AudioAtlas are recorded here. Format roughly
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## v0.2-alpha

### Added
- Added the first graph extension pack: `peak_timeline` in the `standard` and
  `full` profiles, plus `peak_vs_rms`, `rms_histogram`, and
  `stereo_correlation_histogram` in the `full` profile. The peak timeline
  summary now includes additive `frame_peak_linear` and `frame_peak_dbfs`
  arrays for per-frame sample peaks; existing summary fields are unchanged.

### Changed
- Introduced a behavior-preserving graph registry as the single source of
  truth for the existing 13 report plots and their report metadata. This keeps
  the same filenames, render order, and `summary["plots"]` output; graph
  selection, stable-key filenames, and new graphs remain future slices.
- Migrated plot output filenames from numbered names to stable graph-key names
  while preserving render order and the 13-plot set. `summary["plots"]` now
  lists stable filenames such as `waveform_rms.png` and
  `short_term_lufs.png`; graph selection and new graphs remain future slices.
- Added graph selection profiles and enable/disable controls for rendered plots
  only, available through CLI flags and a top-level YAML `graphs:` block.
  `summary["graphs"]` records the resolved selection while analysis blocks,
  findings, catalog data, and section comparisons remain complete.
- Kept `schema_version` at `0.1.0` because v0.2-alpha schema changes are
  additive: `summary["graphs"]` and per-frame sample-peak arrays under
  `peak_timeline`; no existing summary fields were removed or renamed.

## Unreleased

### Added
- Short-term LUFS timeline: new `short_term_lufs` summary block,
  `short_term_lufs.png` plot, and `compute_short_term_lufs` in
  `src/audioatlas/analysis/loudness.py`. Uses pyloudnorm blockwise
  processing with 3 s K-weighted windows (high overlap) to provide a
  perceptually-weighted time-varying loudness view. Distinct from RMS.
  Empty result + warning for files < 3 s. Integrated reference included.
- Chroma CQT pitch-class energy: `chroma_cqt` summary block and
  `chroma_cqt.png` plot (12-bin chromagram over time from
  `librosa.feature.chroma_cqt` on a mono downmix). Descriptive only — not key
  detection.
- Per-frame crest factor timeline: `crest_factor_timeline` summary block and
  `crest_factor_timeline.png` plot (`20 * log10(frame_sample_peak / frame_rms)`
  per frame, all channels).
- YAML section definitions: `audioatlas sections --config sections.yaml` loads
  a top-level `sections` list (`name`, `start`, optional `end`) and runs the same
  manual section pipeline as repeated `--section name:start:end` flags.
- Manual section scans: `audioatlas analyze --start/--end` can analyze a
  source time range, and `audioatlas sections --section name:start:end` writes
  one report folder per supplied section plus a `section_index.md`.
- Section reports now show their original source range in `report.md` and
  `report.html`, so sliced reports are not mistaken for whole-song analyses.
- Public alpha release documentation: clearer README framing,
  `docs/ALPHA_LIMITATIONS.md`, `examples/README.md`, and roadmap notes.
- Single-track reports now include generation timestamp, AudioAtlas version,
  git hash when available, and a public early-alpha release label.
- `report.html` includes a short workflow near the top explaining how to use
  Delivery & headroom context, Findings, plots, and listening checks together.
- Built-in static HTML theme support for single-track and catalog reports,
  including `--theme` on `analyze`/`batch` and `audioatlas themes` for
  listing the 25 local theme IDs. Theme choice affects presentation only.
- Catalog reports now include common folder patterns, MP3/decoded-audio
  delivery context when lossy files dominate a folder, neutral per-track
  trait tags, and distribution bars with median and per-track markers.
- Batch/catalog mode via `audioatlas batch FOLDER --out OUT_DIR`, which
  reuses the single-track pipeline for each supported audio file and
  writes `catalog_summary.json`, `catalog.md`, and `catalog.html` with
  neutral folder-level ranges, medians, and technical fingerprints.
- Static `report.html` output with embedded CSS, escaped dynamic content,
  key metric cards, findings, plot cards, glossary explanations,
  technical details, and blank human-note fields.
- Clickable plot images in `report.html` open a calm, dependency-free
  lightbox overlay (Esc / backdrop / arrows / buttons, real PNG srcs,
  title + filename + counter, wraps, aria basics, all offline file:// safe).
- Time-range summarization in `report.md` findings: long range lists now
  show counts, total duration, first/last range, longest range, and a
  capped preview while preserving full ranges in `findings.json`.
- Onset-strength based transient density analysis with `onset_density`
  summary output, `onset_density.png`, and factual relative-to-track
  dynamics findings with suggested checks.
- Finding prioritization and display capping with `findings_shown`,
  `all_findings`, and `findings_suppressed_count` in `findings.json`.
- Time-varying frequency band energy analysis with
  `band_energy_timeline` summary output, `band_energy_timeline.png`,
  and factual relative-to-track band findings.
- Spectral shape timeline analysis with centroid, 85%/95% rolloff, and
  bandwidth summaries, `spectral_shape.png`, and factual
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
  output, a Markdown report section, and `stereo_correlation.png`.
  Undefined zero-variance frames remain `NaN` internally and are excluded
  from summary statistics.
- Mid/side RMS energy timeline analysis with `mid_side_energy` summary
  output, a Markdown report section, and `mid_side_energy.png`.
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
- Findings hygiene: small rule tweak (rolloff 95% threshold lowered from 8 kHz
  to 7 kHz for fewer generic triggers on typical material) + reworded
  `why_it_matters` for PLR and rolloff findings so they describe practical
  audible or post-normalization delivery consequences rather than restating
  metric relations or heuristics. Updated focused tests. No new measurements,
  no verdicts.
- User-facing finding evidence avoids raw internal field names such as
  `true_peak_dbtp`, `near_clipping_samples`, and `plr_db`.
- Integrated loudness above -10 LUFS is kept in Delivery & headroom context
  rather than Findings.
- Catalog report dark themes now avoid hard-coded light-theme colors in common
  pattern, distribution, table, and glossary UI elements.
- Repo hygiene rules now ignore generated reports, archives, calibration audio,
  review packages, caches, and virtualenvs for public-alpha preparation.
- Locked the single-track report UX as the regression baseline with
  structural tests for friendly empty states, delivery/headroom context,
  grouped stereo findings, near-clipping grouping, glossary wording, and
  local relative plot links.
- Report language keeps generated observations under `Findings`, includes
  explicit `does_not_mean` caveats, maps internal severity values to
  friendlier prompt labels, and repeats relative-dB context near relative
  spectrum/band sections.
- Relative-to-track centroid, band-energy, and onset-density movement now
  stays in summaries and plots instead of producing default findings for
  normal within-song movement.
- Calibrated stereo and near-clipping finding severity from real-run
  reports: brief low-correlation events in otherwise high-correlation,
  mid-dominant tracks are downgraded or suppressed, while sustained
  low correlation, high side energy, true-peak overs, and actual clipping
  remain prominent.
- Level findings for lossy decoded files now refer to decoded samples or
  decoded audio instead of implying the original source master clipped.
- Technical report summary sections now show time-range counts instead
  of raw Python-style range lists.
- Non-severe time-ranged findings now filter tiny ranges by
  `finding_min_time_range_seconds`.
- Findings are less eager by default: floor-level and very short
  band-energy observations are suppressed, repeated band observations are
  grouped, and strongest-frame/strongest-band facts stay in summaries
  rather than default findings.
- Report plot headings now use curated display names instead of title
  casing filenames.
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
- Initial plot set covered waveform/RMS, RMS timeline, log spectrogram,
  average spectrum, and sample histogram. Current v0.2-alpha output uses
  stable graph-key filenames documented in `docs/SUMMARY_SCHEMA.md`.
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
