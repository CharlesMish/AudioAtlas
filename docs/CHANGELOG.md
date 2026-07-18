# Changelog

AudioAtlas follows semantic versioning while in alpha. Schema versions are
tracked separately in `src/audioatlas/release.py`.

## Unreleased

### Lower activation cost

- Added a native Apple Silicon macOS app that accepts one dropped or chosen
  track, displays coarse analysis progress, writes a standard themed report
  beside the source, opens it automatically, and reveals it in Finder without
  requiring Python or Terminal.
- Added presentation-neutral progress events to the shared analysis pipeline;
  listener failures cannot change report generation or artifact semantics.
- Added a reproducible PyInstaller app bundle, frozen librosa/Numba runtime
  adaptation, persistent scientific caches, size gates, a headless frozen smoke,
  and ad-hoc beta artifacts.
- Added Developer ID signing, hardened-runtime entitlements, notarized/stapled
  DMG publication, and GitHub prerelease attachment to the release workflow.
- Split onboarding into the friend-facing Mac app and the advanced PyPI CLI,
  while retaining older PATH-dependent launchers as explicit legacy helpers.
- Hardened report publication with destination ownership checks, cross-process
  locks, source-mutation detection, collision-safe app folder selection, and
  cooperative Cancel/Quit behavior that never interrupts publication.
- Raised the honest desktop floor to Apple Silicon macOS 14, removed the unused
  OpenMP runtime path, added Mach-O closure audits, and tightened signing,
  notarization-log, clean-Mac approval, and credential-cleanup gates.
- Added a non-publishing notarized friend-demo workflow and self-contained demo
  kit, shared DMG packaging audits, background input inspection, explicit cold
  engine startup feedback, and a fillable separate-Mac acceptance record.

### Live demo

- Restored the full 70.98-second AudioAtlas trailer/demo track as a documented
  public demo input with distinct AI-assisted provenance and demo-only reuse
  terms, while retaining the existing CC BY terms for the two human-made demos.
- Switched the GitHub Pages example to a standard-profile Midnight Studio
  report generated from that track, with the source audio excluded from the
  deployed static site.

## `0.2.0a7` — 2026-07-15

### Easier adoption and local song workspaces

- Added protected GitHub Pages, GitHub prerelease, TestPyPI, and PyPI workflows
  so users can inspect a live static report and install without cloning source.
- Added `audioatlas project init`, `project add`, and `project build` for keeping
  same-track revisions, reusable manual sections, guarded adjacent diffs, and
  portable static indexes in one private local workspace.
- Added a dedicated `0.1.0` song-project schema, hashed generated project
  identity, owner-side YAML state, atomic revision addition, and a guard against
  publishing ordinary reports into a project root.
- Kept private source paths only in the explicit owner-side project YAML;
  generated project JSON, Markdown, and HTML retain portable filenames.

### Reliability and release integrity

- Serialized song-project mutations across processes, converted filesystem
  races into friendly retry errors, and retained rollback of prior revisions.
- Restricted private project YAML permissions on POSIX and made project rebuilds
  reject symlinks, noncanonical paths, incomplete ownership manifests,
  mismatched identities, and non-share-safe summaries.
- Pinned workflow actions to immutable commits, isolated OIDC publication jobs,
  made TestPyPI/PyPI reruns digest-aware, and required indexed clean-install
  smokes before finalizing the GitHub prerelease.
- Added locked dependency auditing, automated dependency updates, a security
  policy, fixed Pillow/msgpack floors, a non-yanked build-tool lock, and PyPI
  provenance and distribution-hash verification.
- Added early finite/domain validation for CLI and Python analysis inputs so
  invalid ranges and configuration values fail cleanly before analysis.
- Made YAML keys explicit, prevented colliding manual-section output slugs,
  and escaped user-controlled labels in generated Markdown.
- Guarded public export against tracked public files that differ from the
  recorded stewardship commit.
- Hardened deterministic public-snapshot generation and CI verification,
  including file-set, per-file hash, count, aggregate-tree hash, and metadata
  checks.
- Made the demo-free source distribution's included tests coherent while
  retaining repository-only verification of the published demo WAVs.
- Aligned schema documentation and CI smokes on the preferred `compact` graph
  profile while retaining deliberate `minimal` compatibility coverage.
- Removed the unused mypy development dependency after an initial check showed
  that meaningful enforcement requires a separate typing project, and hardened
  the root macOS launcher so failures remain visible and actionable.
- Published two rights-cleared real musical demo recordings for full report and
  two-track catalog walkthroughs, with audio-specific CC BY 4.0 attribution and
  a visible exception for embedded Native Instruments/Kontakt and possible
  Splice content. Package builds continue to exclude the WAV files.

## `0.2.0a6` — 2026-07-11

### Accessible interactive reports

- Made Studio the default opening presentation across single-track, catalog,
  section, and revision-diff HTML while preserving explicit Focus selection.
- Added skip links, report landmarks, consistent keyboard focus treatment,
  responsive table regions, reduced-motion behavior, and print cleanup across
  all static report types.
- Made plot enlargement keyboard-operable and completed dialog focus trapping,
  counter announcements, Escape/arrow controls, and focus restoration.
- Linked metrics to glossary definitions and used existing finding graph keys
  for reciprocal prompt/plot navigation; lower-priority observations now expand
  inline instead of requiring JSON inspection.
- Added private per-report Human note autosave with accessible status, copy,
  text export, and clear controls. Notes remain local and outside report files.
- Audited normal-size semantic text pairs across all 25 built-in themes and
  repaired combinations below the WCAG AA contrast ratio.
- Added project URLs and package keywords for distribution-page discoverability.
- Kept all measurement, finding, graph, provenance, and JSON schema behavior
  unchanged.

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
