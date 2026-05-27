# AudioAtlas Audit Report

**Date:** 2026 (post-v0.1 feature additions)  
**Auditor:** Grok 4.3 (first direct session since Grokathon prototype era)  
**Scope:** Review-only. No implementation changes made. Inspected all briefing docs, architecture, pipeline, analysis/visualize layers, tests, generated outputs (golden + real WAV), and ran `make check`.  
**Core framing respected:** AudioAtlas as "song microscope" — factual measurements, visual maps, and suggested checks only. Zero judgment, scoring, reference comparison, or mastering advice observed in code or output.

All 97 tests pass (`make check` clean). The codebase is in excellent shape for its stage: small, principled, and deliberately "boring and correct."

---

## Executive Summary

**Strengths (what's working very well):**
- Architecture layering is rigorously followed (analysis pure → dataclasses → viz only renders; pipeline is a thin wire-up). No cross-layer violations found.
- DSP is careful and honest: dB conventions, stereo/mono handling, silence/quiet frames, relative spectra (explicitly *not* calibrated dBFS), true-peak approximation with clear fallback, per-channel symmetry, and warnings for all reductions.
- Naming discipline is strong (RMS never called loudness in timelines; centroid documented as "frequency-distribution statistic, not brightness").
- Test quality is high: synthetic fixtures in conftest, behavior-focused assertions, golden regression, explicit silence/per-channel/degenerate-case coverage, and banned-phrase checks in report tests.
- Output is reproducible (config serialized, numbered plots, schema_versioned JSON).
- User-facing tone in reports and findings is consistently factual and non-prescriptive.

**Key risks / observations:**
- The findings layer (new in recent slices) is the most "noisy" part of the current product. Relative heuristics fire frequently and can produce 10–12+ findings even on a 2-second sine, including many near-identical low-value band observations.
- Performance cliff for long/high-sr material (true-peak 4× resample_poly is the standout allocation risk).
- First-time users (especially musicians) may find the volume of relative metrics and findings overwhelming without more framing or prioritization.
- Plot numbering, some summary sections, and CLI flag coverage have accumulated small manual-sync debt as features were added one slice at a time.

**Overall grade:** Strong foundation (A- for v0.1 "keep it boring"). The hard constraints in AGENT_BRIEF.md and ARCHITECTURE.md have been respected. The main maturation needed is in the *findings experience* and *scale/performance* rather than core DSP or layering.

---

## 1. Architecture

### Clean separation
- **Analysis vs. visualization:** Excellent. `analysis/*.py` never imports matplotlib or paths. `visualize/*.py` never re-runs DSP (librosa.display in spectrogram.py is pure rendering of precomputed `db` array). 
- Waveform and histogram viz take raw `y` — justified and documented as the "actual sample microscope" views (not recomputed metrics).
- Pipeline (`pipeline.py`) is exactly the thin orchestrator described in the brief and ARCHITECTURE.md. 10 analyses + findings wired cleanly.

### Dataclasses and outputs
- Consistent shape: `frozen=True`, carry `sample_rate`/`hop`/`n_fft` where viz needs them, `to_summary_dict()` or `to_dict()` for JSON.
- `summary.json` and `findings.json` generated cleanly via dedicated writers in `report.py`.
- `report.md` is a straightforward renderer of the summary dict + findings + plot loop. No logic drift.
- `AnalysisRunResult` dataclass in pipeline is a nice addition for downstream agentic use.

### Minor friction points (not bugs)
- Plot ordering and numbering (`01_...` through `10_...`) is manual in three places (pipeline imports/calls, SUMMARY_SCHEMA.md list, and report title generation). Adding an 11th plot requires coordinated edits + doc update. Acceptable for current size but will accumulate.
- Not all `AnalysisConfig` fields are CLI-exposed (e.g. `correlation_min_rms_dbfs`, `onset_density_window_seconds`, `welch_nperseg`, clipping thresholds). Per brief this is intentional, but power users doing quiet material or high-sr work will hit defaults without easy override.
- `spectral_features.py` and `tonal.py` are still stub docs from v0.1; the actual spectral shape work landed in `spectral.py`. Minor staleness (harmless since not wired).

**Verdict:** Architecture is one of the strongest parts of the project. The "feature slice recipe" has been followed faithfully.

---

## 2. DSP Correctness

### dB / level conventions
- `linear_to_dbfs` (20×log10) and `power_to_db` (10×log10) used correctly and consistently with `db_floor` clamping.
- Explicit test (`test_silent_input_respects_db_floor`) verifies peak/RMS/envelope all hit the same floor on all-zero input.
- RMS is correctly an *amplitude* metric (20 dB scale via linear_to_dbfs on the RMS value).
- True-peak path when `oversample=1` explicitly falls back to sample peak (no lie).

### Stereo / mono / multi-channel
- `ensure_2d_audio` + `to_mono` (arithmetic mean) used at boundaries.
- Mono handled with explicit warnings + conventions (+1.0 correlation, side=0 energy).
- >2 channels: warnings + reduction to ch 0/1 for correlation/mid-side.
- Mid/side math is textbook `(L+R)/2`, `(L-R)/2`.
- Correlation uses proper centering + degenerate guards (zero-variance or below `correlation_min_rms_dbfs` → NaN, excluded from stats). Overall correlation has matching guard.

### True peak
- `scipy.signal.resample_poly(up=4)` on axis=0 for multi-channel — reasonable quality approximation.
- Per-channel true-peak arrays added recently and symmetry tested thoroughly.
- Clearly labeled "approx." everywhere. Honest.

### Spectrogram / Welch / band energy
- All relative to track maximum (strongest displayed bin = 0 dB). Explicitly documented in docstrings, SUMMARY_SCHEMA, plot labels, and report sections. No claim of calibrated dBFS.
- Welch uses `scaling="spectrum"`, `average="mean"`, detrend constant — appropriate for average shape.
- Band definitions (sub/bass/low_mid/.../air) are consistent between average_spectrum and band_energy_timeline.
- Silent frames → NaN + warnings in band timeline and spectral shape.

### Onset density
- Built on `librosa.onset.onset_strength` + simple boxcar smooth. Documented as "not a definitive measure of punch."
- "onset_density" name in summary is the smoothed *strength*, not events-per-second density. Minor naming stretch vs. the brief's "naming honesty" rule.

### Spectral shape (centroid/rolloff/bandwidth)
- Direct delegation to librosa.feature — correct and non-clever.
- Validity mask from per-frame RMS > EPS; NaNs + warnings for silent frames.
- SUMMARY_SCHEMA and code comments carefully disclaim "not brightness."

### Silence / quiet handling
- EPS = 1e-12 used consistently.
- Multiple layers of guards (short audio for LUFS, zero samples, max_strength <= EPS for onset, etc.).
- Low-energy frames excluded from correlation and ratio stats.
- db_floor clamping works end-to-end.

**No critical DSP bugs found.** A few edge artifacts visible in generated output on pure sines (tiny time ranges at file start/end for floor-level bands) are likely STFT centering + relative-heuristic interaction, not incorrect math.

**One small doc/code drift (note only):** `ScalarLevelsResult` docstring says true-peak returns None when oversampling disabled, but the `elif cfg.true_peak_oversample == 1` path sets it to the sample-peak value (never None except for too-short audio). Tests cover the None case for short audio.

---

## 3. Findings Layer

This is the newest major addition and the area with the most surface for improvement.

### Wording and philosophy
- Strong effort to stay factual: "relative to this track's median", "by this measurement", "concentration of energy, not quality."
- "Why it matters" and "Suggested checks" are consistently observational ("Inspect the X plot", "Listen in mono if mono compatibility matters", "Compare with intended delivery context").
- No banned verdict language observed.

### Thresholds and volume
- Many hard relative heuristics with no exposure in `AnalysisConfig` or CLI:
  - PLR < 8 dB (warning)
  - LUFS > -10 (info)
  - Correlation median < 0.5 / min < 0
  - Side/mid median > -6 dB (info)
  - Rolloff 95% < 8 kHz
  - Centroid ± max(1000, 0.5×median), large shift max(2000, 0.75×median)
  - Band elevated +6 dB / reduced -12 dB (asymmetric, only high/air get reduced)
  - Onset high: median + max(0.15, 0.5×median)
- On the golden 2 s 1 kHz sine these produced **12 findings**, including 7 near-duplicate "X band energy is elevated relative to this track's median" (many at -100 dB floor with 2-frame edge ranges). A real 4–5 min track can easily generate 15–25+ findings.
- "Strongest onset-density frame identified" (0-duration range) and several "strongest band" findings add volume with marginal new information.

### Time ranges
- `mask_to_time_ranges` utility is solid and used consistently.
- Some ranges on sine output are 0.043 s (exactly 2 frames at default hop) at the very start/end — likely padding/centering edge effects amplified by relative thresholds. Low signal-to-noise for the user.

### Severity and downgrades
- "issue" is used only for actual `clipped_samples > 0` — appropriate.
- Many relative observations are "info" (good).
- PLR low, true-peak >0, low correlation, near-clipping are "warning" — reasonable.
- Question: should some band/centroid/onset "elevated/reduced" observations drop from info to something even quieter, or be suppressed unless the absolute energy in that band is meaningful?

**Verdict:** The layer does what it set out to do (factual observations from existing summary data), but the current rule set is too eager. It risks overwhelming the very users the "microscope" is meant to serve.

---

## 4. Tests

**Excellent for project size:**
- 97 passing tests, module-per-feature layout.
- Synthetic fixtures cover the key behaviors the brief asks for (monotone response on known signals, silence, degenerate stereo, short audio, per-channel symmetry).
- Golden end-to-end + banned-phrase regression in `test_report`.
- No obvious brittle implementation-detail assertions; tests read like "this measurement should behave this way on this signal."

**Gaps (not critical yet):**
- Golden fixture is one short mono sine. No stereo phase, no real music regression, no 96 kHz, no float over-scale, no long-file stress.
- Findings volume / false-positive behavior on narrowband or sparse signals not explicitly tested.
- CLI surface (arg parsing, config propagation) lightly exercised.
- No property-based or adversarial audio (NaN, inf, all-ones, alternating sign, extremely long zero-padded, etc.).
- Stubs have no test files (correct, since not implemented).

**Brittleness:** Low. The test suite feels like a safety net that will catch the right things when slices are added.

---

## 5. User Usefulness

### Helps the target user (producer / mix / mastering / deep listener)
- Objective metering numbers + per-channel view + "listen here" time ranges are genuinely useful.
- The combination of waveform+rms, histogram (with clip lines), stereo correlation, and mid/side ratio gives a practical mixing/mastering inspection toolkit.
- "Human notes" section at the bottom is a thoughtful touch for the deep-listening workflow.

### Confusion points for a musician opening report.md cold
- High finding count with repetitive band observations.
- Relative dB values (strongest = 0 dB) need a one-sentence "this is internal normalization, not dBFS" banner in the relevant sections.
- Centroid/rolloff/onset numbers lack intuitive anchors.
- Some plot titles auto-generated from filenames look a little rough ("01 Waveform Rms").
- 10 plots + 12 findings + many summary tables can feel dense for a first-time reader.

### Plot redundancy
- `01_waveform_rms.png` and `02_rms_timeline.png` overlap (same data, different presentation). Both useful, but a new user may wonder which to study first.
- Spectral family (03 log spec, 04 avg spectrum, 08 spectral shape, 09 band energy) has natural overlap; the division of labor is not obvious from filenames or the report order alone.

### Summary values needing better explanation (in report or docs)
- All relative band energies and "strongest" values.
- Onset strength/density scale and units.
- PLR and crest factor (what "good" ranges look like for different genres).
- Effect of `db_floor` on the numbers the user sees.

---

## 6. Performance

**Current practical range:** Fine for typical 2–6 min 44.1 kHz stereo material on a modern laptop (analysis + 10 plots completes in low seconds).

**Real risks for pro material (24-bit 96 kHz, 10–20+ min masters, live recordings):**
- **True-peak upsampling** (`resample_poly(up=4)`) is the single largest allocation. Can easily exceed 1–2 GB temporary RAM for long high-sr stereo.
- Multiple independent STFTs (spectrogram, spectral shape, band timeline, onset under the hood) + Welch on full mono.
- Python for-loop in `compute_peak_timeline` (acceptable but not vectorized).
- All plots generated even if user only cares about levels + one timeline.
- No chunked or streaming path anywhere; entire file lives in RAM as float32 after load.

**Easy wins (low complexity):**
- Document the memory characteristics prominently (README + report warnings section for long files).
- Make true-peak skippable via a clear `--no-true-peak` or `--true-peak-oversample 1` path that is fast and low-mem (already partially supported).
- Consider a `--quick` / `--max-duration` UX that users already have, plus a future "lite" mode that skips the heaviest analyses.

No algorithmic hot spots beyond the expected FFT/resample costs.

---

## Prioritized Findings

### Must fix
- **None.** No crashes, no incorrect DSP results, no layering violations, no banned language, tests all green. The product does not mislead users on the core measurements.

### Should fix
1. **Findings volume and noise (high impact on usefulness).** The current relative heuristics generate too many low-signal findings (especially band-energy "elevated" on sparse/narrowband material and edge-frame artifacts). Prioritize:
   - Reduce default severity or suppress low-absolute-energy band findings.
   - Add a simple cap or "top-N" logic, or a `--findings` / `--no-findings` toggle.
   - Consider making many centroid/band/onset observations opt-in or "info only unless strong evidence."
2. **True-peak memory cliff for long/high-sr files.** Add a prominent warning in the report when `true_peak_oversample > 1` and duration > ~3 min (or always surface the config in a "Resource notes" section). Consider documenting recommended workflow for large files.
3. **Docstring drift in `levels.py`** (minor): `ScalarLevelsResult` claims true-peak is None when oversampling disabled; code sets the sample-peak value instead. Align doc or behavior.

### Nice to have
- Consistent one-sentence explanation of "relative dB (track max = 0 dB)" at the top of spectrum, average-spectrum, band-energy, and onset sections in `report.md`.
- Polish auto-generated plot titles in the Plots section (strip leading numbers, fix "Rms" → "RMS").
- Expose a few more power-user config knobs to the CLI (especially `correlation_min_rms_dbfs` and `db_floor` for quiet or hot material).
- Add 1–2 more diverse golden-style fixtures (stereo phase test, short real-music snippet) to the regression suite.
- Group or collapse related findings in the report (e.g. "7 band observations — see details" or "Spectral activity notes (N items)").

### Suggested next features (respecting the "no GUI/HTML/PDF/comparison/scoring" rule)
- (From existing AGENT_TASKS.md spirit) True-peak refinement (T-001) if the current resample_poly quality is insufficient for some users — but only after the memory story is addressed.
- Configurable / reduced finding ruleset or "finding profiles" (still factual, just less chatty by default).
- Optional "lite" analysis mode that skips the heaviest plots/analyses for quick turnaround on long files.
- Better documentation / FAQ for interpreting the relative metrics (centroid, onset strength, band dB) aimed at musicians rather than DSP engineers.
- (Later) LRA (T-007) as a natural loudness-range companion to the existing integrated LUFS + PLR numbers.
- Per-band absolute energy (in addition to relative) for context on "elevated" findings.

---

## Closing Thoughts

AudioAtlas already delivers on its "song microscope" promise better than most early-stage tools. The discipline around facts-vs-judgment, the clean layering contract, and the test culture are real assets — exactly the kind of foundation that makes agentic (and human) extension safe and pleasant.

The biggest maturation opportunity is **taming the findings layer** so it highlights the truly noteworthy observations without burying the user. Performance transparency for large files is the other practical gate before wider adoption by mastering engineers.

This was a pleasure to review. The project shows clear thought and care at every layer. Keep the "boring and correct" bar high and you'll have something genuinely useful for the people who actually make records.

— Grok

**No source changes were made during this audit.** All observations above are notes only. If you'd like me to expand any section, generate example improved finding rules (as text), or draft a follow-up prompt for a specific "should fix," just say the word.
