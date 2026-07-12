# Changelog

AudioAtlas follows semantic versioning while in alpha. Schema versions are
tracked separately in `src/audioatlas/release.py`.

## Unreleased

No entries yet.

## `0.2.0a5` — 2026-07-11

### Friendly public distribution

- Rewrote the root README around the first user journey and moved detailed
  operation guidance into `docs/USER_GUIDE.md`.
- Added a deterministic public-tree exporter and documented a two-branch model:
  a user-facing `main` branch and a full `stewardship` branch containing review,
  calibration, and operating records without maintaining a second codebase.
- Removed stewardship-only material from the Python source distribution while
  keeping code, tests, user documentation, schemas, compatibility notes, and
  launchers available to public users.
- Kept the public Makefile focused on normal install, test, lint, demo, and
  golden-fixture tasks; stewardship export and calibration operations remain in
  their owner-side runbooks and scripts.
- Made `audioatlas analyze song.wav` useful without `--out`; it now chooses a
  predictable `audioatlas-report-<filename>` folder.

### Report experience profiles

- Added an accessible Focus/Studio switch to single-track, catalog, and
  revision-diff HTML reports. Focus preserves the restrained report; Studio
  adds richer static framing without filtering or changing plot pixels.
- Added `--presentation focus|studio` to choose the opening view. Reports remain
  local and dependency-free and remember the selection per report path when
  local storage is available.
- Added `compact` as the preferred public name for the four-plot graph profile.
  The legacy `minimal` name remains an equivalent compatibility alias.
- Kept one analysis engine rather than introducing a separate lite package;
  compact/full depth and Focus/Studio presentation are delivery choices only.
- Kept summary, findings, catalog, comparison, and finding-ruleset schemas
  unchanged because this pass does not alter measurement or interpretation
  semantics.

## `0.2.0a4` — 2026-07-11

### Comparable same-track revisions

- Added a guarded `audioatlas diff` workflow for two revisions of the same
  track. It emits static JSON, Markdown, and HTML containing descriptive
  `B - A` measurement deltas, broad-band median shifts, and finding-rule churn.
- Added optional `--track-id` support for single-track and manual-section
  reports. AudioAtlas stores only the token's SHA-256 digest; conflicting
  identities are a hard error, while missing identities require an explicit
  `--confirm-same-track` assertion.
- Added strict comparability checks. Exact-environment and compatible-analysis
  signatures are distinguished, materially different analysis signatures are
  refused by default, and an explicit override remains visibly caveated.
- Refused diff output paths that would overwrite either source report folder.
- Kept cross-track ranking, reference matching, preference language, and
  better/worse judgments outside the product contract.

### Provenance, calibration durability, and inspectability

- Added an `analysis_provenance` block to `summary.json`, including canonical
  analysis-configuration, measurement-code, dependency/decoder, compatible
  analysis, and exact-environment hashes. Summary schema is now `0.2.1`.
- Added a calibration ruleset replay tool that verifies a frozen anonymous
  review ledger against report evidence hashes, reruns the candidate finding
  rules on saved summaries, and reports appeared/disappeared/changed/unchanged
  prompt churn without opening or copying audio.
- Prevented replay output paths from replacing the frozen asset map or review
  ledger, even under `--force`.
- Extended calibration worksheets with provenance signatures so mixed analysis
  conditions cannot be merged silently.
- Added measured-value plot alt text to both HTML and Markdown reports and kept
  lightbox alternatives synchronized with the selected image.

### Regression and error-boundary hardening

- Added deterministic property-based invariants for gain/PLR behavior, channel
  swap symmetry, silence/sub-second degradation, and DC offset behavior.
- Added committed malformed WAV and FLAC fixtures plus CLI, loader, and mixed
  batch tests that assert path-safe domain errors at the decoder boundary.
- Added an explicit `numba>=0.65.1,<0.66` runtime compatibility band after
  a clean Python 3.13 installation selected Numba 0.66.0 / llvmlite 0.48.0
  and stalled inside LLVM code generation; the same wheel completed its report
  smoke after resolving Numba 0.65.1 / llvmlite 0.47.0.
- Extended output ownership to revision-diff artifacts while keeping unrelated
  human files protected during report-kind switches.
- Archived the independent Fable `0.2.0a3` review that motivated this bounded
  pass. The finding ruleset remains `0.2.0a2`; no default trigger semantics or
  interpretive thresholds changed.

## `0.2.0a3` — 2026-07-11

### Calibration and review readiness

- Added a project-specific Hopeful Skeptic edition for recurring AudioAtlas
  reviews, release gates, and implementation handoffs.
- Added a concrete private musical-calibration runbook, expanded anonymous
  corpus/rule-decision templates, and a privacy-conscious worksheet generator.
- The worksheet generator captures displayed and report-cap-suppressed findings,
  records package/schema/ruleset versions, report/per-finding hashes, exact
  prompt and non-claim wording, keeps filenames in an optional private map, and
  preflights both outputs before replacing human labels.
- Added a native macOS/Windows launcher rehearsal protocol and fillable log.
- Archived the independent `0.2.0a2` Hopeful Skeptic audit that motivated this
  bounded follow-up pass.

### Workflow polish and release truth

- Made `--version`, `--help`, and `themes` lightweight by deferring DSP, decoder,
  graph-registry, and plotting imports until an analysis command is selected.
- Added immediate preparation feedback before heavy single-track, batch, and
  section initialization.
- Formalized package/schema/ruleset/output-manifest version axes and the
  compatibility-alias lifecycle. JSON aliases remain through `0.2.x`; removal
  may occur no earlier than `0.3.0` with an explicit schema migration.
- Kept the finding ruleset at `0.2.0a2`: no trigger, priority, or interpretive
  rule semantics changed in this release.
- Removed stale active `v0.1` docstring/comment references without rewriting
  intentionally archived history.
- Added Makefile helpers for deterministic fixtures and calibration-sheet
  preparation.

## `0.2.0a2` — 2026-07-11

### Interpretation integrity

- Corrected the PLR explanation: normalization applies the same gain to peak and
  integrated loudness and does not change PLR.
- Narrowed low-PLR prompting to cases with independent high-level evidence.
- Removed the context-blind absolute low-rolloff finding.
- Renamed broad-band presentation to **relative mean band power per included FFT
  bin**; retained temporary compatibility aliases for earlier alpha JSON and the
  stable plot filename.
- Added stable finding rule IDs, per-rule versions, typed evidence items, graph
  associations, and a documented rule ledger.

### Failure handling, privacy, and output safety

- Added concise domain errors for unreadable audio instead of raw decoder
  tracebacks.
- Removed machine-local absolute paths from report and catalog metadata by
  default; added explicit `--include-local-paths` opt-in.
- Made batch mode continue after unreadable files by default and added `--strict`.
- Expanded batch discovery to WAV/WAVE, FLAC, OGG, AIFF/AIF, and MP3, subject to
  local decoder support.
- Added staged report/catalog publication, output ownership manifests,
  stale-plot cleanup, child-verified previous batch-track cleanup, collision
  prevalidation, rollback to the previous generated set after a publication
  failure, clean switching between single-report and catalog output modes, and
  preservation of unknown user files.
- Converted expected short-input CQT/tuning warnings into structured report
  caveats, adapted onset mel filters for tiny FFTs, and preserved unexpected
  library warnings.
- Added an explicit post-report collection boundary so renderer reference
  cycles do not accumulate across album-sized in-process batch runs.

### Release truth and calibration

- Added the actual MIT `LICENSE` file.
- Added `PROJECT_CHARTER.md`, `docs/FINDING_RULES.md`, and a deterministic
  calibration-fixture generator with review templates.
- Reconciled version/release labels, onboarding commands, launcher claims,
  architecture documentation, and schema documentation.
- Archived superseded reviews, design notes, task ledgers, and changelog source
  rather than presenting them as current operating instructions.
- Added broader Python/platform CI, package build checks, and clean-wheel smoke
  coverage.

## `0.2.0a1` — 2026-06-29

- Added a static local HTML report, graph registry and render profiles, expanded
  spectral/dynamics/stereo/tonal measurements, manual sections, batch catalogs,
  themes, launchers, and an extended test suite.
- Established the no-score/no-mastering-verdict product boundary.

## `0.1.0` — initial public framework

- Added local single-track loading, core level/RMS/spectrum measurements, PNG
  plots, JSON/Markdown reports, CLI, fixtures, and baseline tests.

Historical pre-reconciliation detail is preserved in
`docs/archive/CHANGELOG_PRE_0_2_0a2.md`.
