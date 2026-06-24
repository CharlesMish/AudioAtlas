# AudioAtlas Agent Tasks

This is the working backlog for agentic contributions. Tasks are sized to
be roughly one feature slice each (see "shape of a feature slice" in
`docs/ARCHITECTURE.md`). Pick tasks in roughly the order shown unless a
later task is unblocked first.

When you start a task:
1. Read `AGENT_BRIEF.md` (philosophy), then `docs/ARCHITECTURE.md` (where
   code goes), then this ticket.
2. Run `make test` to confirm baseline is green.
3. Do the slice. Land code + tests in the same change.
4. Run `make check` (tests + lint) before declaring done.
5. Update `docs/CHANGELOG.md` under the unreleased section.

**Recommended next task:** Start with a small findings-hygiene or docs
reconciliation pass unless a specific measurement slice is assigned. Do **not**
start with `T-001` unless explicitly assigned; true-peak refinement is subtle
DSP work and should not be a casual agent pass.

---

## T-001 — Improve true-peak approximation [v0.1.x, advanced]

**Status:** open, do not start unless explicitly assigned. **Layer:** analysis.

**What:** The current true-peak uses `scipy.signal.resample_poly(up=4, down=1)`.
That's a decent approximation but a 4× polyphase upsample has known
under-read on impulses. Improve in one of two ways:

- Switch to ITU-R BS.1770 style upsampling: 4× via an explicit FIR with
  a `K20` design, or
- Provide an `8×` mode behind `cfg.true_peak_oversample`, with a test
  showing the 8× number is ≥ the 4× number on a near-clipping
  impulse train.

**Acceptance criteria:**
- A test in `tests/test_levels.py` constructs an impulse near full scale
  that has a known inter-sample peak and asserts the true-peak measurement
  is within ±0.3 dBTP of the analytical answer.
- No regression in existing tests.
- Document the chosen approach in `compute_scalar_levels` docstring.

**Avoid:** Don't pull in a heavy external library (e.g. ffmpeg's loudnorm
filter) just for this.

---

## T-002 — Stereo correlation timeline [done]

**Status:** implemented. **Layer:** analysis + visualize + pipeline.

**What:** Implemented as `compute_stereo_correlation` in
`src/audioatlas/analysis/stereo.py`. Per-frame Pearson correlation of L and R
using `cfg.n_fft`-sized windows hopping by `cfg.hop_length`.

**Acceptance criteria:**
- Mono input → constant +1.0 series and a single non-fatal warning in
  `result.warnings` (define `to_summary_dict` accordingly).
- A `stereo_phase_inverted` test fixture (already in `conftest.py`)
  yields correlation ≤ -0.95 across all frames.
- A correlated stereo fixture (L == R, you'll need to add it) yields
  correlation ≥ 0.95.
- A new plot at `visualize/stereo.py::plot_stereo_correlation`.
- Wired into `pipeline.py` as `06_stereo_correlation.png`.
- `summary.json` gains a `stereo_correlation` block; schema doc updated.

---

## T-003 — Mid/Side energy [done]

**Status:** implemented. **Layer:** analysis + visualize + pipeline.

**What:** Implemented as `compute_mid_side_energy` in
`src/audioatlas/analysis/stereo.py`. Returns mid and side RMS over time plus a
side-to-mid ratio in dB.

**Acceptance criteria:**
- Mono input: side energy is exactly zero; M/S ratio in summary is
  reported as `null` with a warning.
- Phase-inverted fixture: side ≫ mid; ratio in dB is strongly negative.
- Plot at `visualize/stereo.py::plot_mid_side_energy` (two-line plot
  over time, in dBFS, sharing the timeline axis convention of
  `02_rms_timeline.png`).
- Wired into `pipeline.py` as `07_mid_side_energy.png`.

---

## T-004 — Spectral centroid + rolloff [done]

**Status:** implemented. **Layer:** analysis + visualize + pipeline.

**What:** Implemented as `compute_spectral_shape` in
`src/audioatlas/analysis/spectral.py`, with centroid, 85%/95% rolloff,
bandwidth summaries, a plot, summary schema docs, and findings integration.

The old `spectral_features.py` stub remains only as historical placeholder
context and should not be used for new spectral-shape work.

---

## T-005 — Chroma CQT [v0.2]

**Status:** done. **Layer:** analysis + visualize + pipeline.

**What:** Implement `compute_chroma_cqt` in
`src/audioatlas/analysis/tonal.py` using
`librosa.feature.chroma_cqt`.

**Acceptance criteria:**
- A 440 Hz (A4) sine produces clear maximum energy in the "A" bin.
- A C-major triad (C+E+G) produces three clear peaks.
- Plot at `visualize/chroma.py::plot_chroma_cqt` (12 rows, time on x-axis).
- Wired into `pipeline.py` as `12_chroma_cqt.png`.

**Hard rule:** Do NOT add key detection. The plot is the deliverable.

---

## T-006 — Short-term LUFS timeline [v0.2]

**Status:** done. **Layer:** analysis + visualize + pipeline.

**What:** Add a real K-weighted short-term LUFS timeline (3-second
rolling integration, BS.1770) using pyloudnorm. This is the metric the
old "loudness_timeline" name *should* have meant.

**Acceptance criteria:**
- Lives at `src/audioatlas/analysis/loudness.py` (new module).
- Returns a timeline + integrated reference value (already computed in
  `levels`).
- Files shorter than 3s produce an empty result with a warning - do not
  raise.
- Plot at `visualize/loudness.py::plot_short_term_lufs` as
  `13_short_term_lufs.png`.

---

## T-007 — LRA (Loudness Range) [v0.2]

**Status:** open. **Layer:** analysis.

**What:** Implement BS.1770 LRA (high-low percentile spread of
short-term LUFS values, gated). pyloudnorm does not expose LRA at the
basic level; either compute LRA on top of `T-006`'s short-term LUFS
output, or contribute it upstream.

**Acceptance criteria:**
- New field `lra_lu` added to `ScalarLevelsResult`. Schema doc updated
  and `schema_version` bumped to `0.2.0`.
- A pink-ish noise file (constant level) has LRA < 1.0 LU.
- A signal with -23 LUFS quiet section + -10 LUFS loud section has
  LRA close to 13 LU.

---

## T-008 — HTML report [done]

**Status:** implemented. **Layer:** report.

**What:** Add a static HTML report renderer alongside the Markdown one.
The implementation is dependency-light and uses embedded CSS.

**Acceptance criteria:**
- New module `src/audioatlas/html_report.py`.
- `report.html` is generated for every analysis run.
- Linked plots use relative paths. No external CDN, no JS frameworks.
- Tests cover key metric cards, findings, glossary copy, plot links,
  escaping, and pipeline output.

## T-009 — Manual section scans [done]

**Status:** implemented. **Layer:** IO + pipeline + CLI + report.

**What:** `audioatlas analyze --start/--end` analyzes one source time range,
and `audioatlas sections --section name:start:end` writes one report folder per
manual section plus a `section_index.md`.

**Notes:** This is not automatic section detection. Ranges are supplied by the
user, report timelines remain section-relative, and reports include source
range context.

---

## T-010 — YAML section definitions [done]

**Status:** implemented. **Layer:** CLI/config parsing.

**What:** `audioatlas sections --config sections.yaml` loads a top-level
`sections` list with `name`, `start`, and optional `end` fields. Repeated
`--section name:start:end` flags and `--config` both feed the same section
parser/validator. Omitting `end` means through EOF.

**Notes:** Manual section definitions only. No automatic section detection or
GUI behavior.

---

## Out of scope (do not add)

These are deliberate non-goals; do not start tickets for them without an
explicit go-ahead from the maintainer.

- Reference-track comparison.
- "Mix health" score, A/B grading, or any automated verdict.
- Real-time / playback / Streamlit UI.
- Automatic section / structure segmentation (verse/chorus detection).
- Vocal isolation, source separation, transcription.
- Genre classification.
- AI-generated mastering suggestions of any kind.

If a user asks for these, the answer is "later, deliberately."

---

## How to propose a new task

Open a discussion or note it at the bottom of this file under a
`## Proposed (pending review)` section. New tasks should:

- Fit the feature-slice shape from `docs/ARCHITECTURE.md`.
- Have clear acceptance criteria (input → expected output).
- Not introduce a verdict, score, or judgment.
