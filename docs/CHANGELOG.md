# Changelog

AudioAtlas follows semantic versioning while in alpha. Schema versions are
tracked separately in `src/audioatlas/release.py`.

## Unreleased

No entries yet.

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
