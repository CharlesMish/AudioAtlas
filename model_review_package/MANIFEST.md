# AudioAtlas Model Review Package Manifest

**Generated:** 2026-05-27 07:53:55 UTC

**Git:** branch `master`, commit `e059ed8`

**make check result (practical run):**  
97 tests passed (pytest -q)  
ruff check . → All checks passed!

## Package purpose
This zip is intended for product/UX/report-language/spec review by multiple LLMs (and humans). It is deliberately model-neutral and contains no raw audio media.

## Top-level contents of model_review_package/
- AGENT_BRIEF.md
- README.md
- AUDIT.md
- calibration_context.md (new for this package)
- REVIEW_PROMPT.md (new for this package)
- MANIFEST.md (this file)
- design/
  - report_mockup.html
  - README.md
- docs/
  - ARCHITECTURE.md
  - SUMMARY_SCHEMA.md
  - CHANGELOG.md
- calibration_reports/
  - calibration/          (12 tracks from reports/calibration/)
  - aster_after_findings_cleanup/
  - dittoguitar_after_findings_cleanup/

## Calibration reports included
**Total report folders:** 14

All folders contain only:
- summary.json
- findings.json
- report.md
- 01_waveform_rms.png through 10_onset_density.png

No report.html files were present in the source outputs.

Tracks included (full PNG sets):
- aster, birdcansing, bunnyparty, DC_kMM_Censored, dittoguitar, hurt3, jarmedley,
  Malone_Doja_BOL4_iKon_medley, Prompt_Architect__Toking_On_Tokens, rept, sufjandry, sufjanm
- Plus the two recent after-findings-cleanup variants for aster and dittoguitar

## Explicit exclusions
- **Raw audio media of any kind** — No .wav, .mp3, .flac, .aiff, .m4a, .ogg, or any other audio files from calibration_audio/, root, or anywhere else.
- .venv, __pycache__, .pytest_cache, .ruff_cache, .git, build artifacts
- generated zip files
- calibration_audio/ directory and all source audio
- Any files not explicitly listed above

## Approximate sizes (pre-zip)
- calibration_reports/: 51 MB (182 files)
- design/ + docs/ + root md files: < 1 MB
- Total source material for zip: ~52 MB

## Notes for reviewers
- All data comes from real AudioAtlas runs on the listed tracks.
- The design/report_mockup.html is a refined static HTML prototype (real <img> tags + fallback captions, vertical findings list, full-width wide plots, top nav, “How to read this report” callout, neutral notes areas).
- The AUDIT.md is the prior independent review of the tool (included for context).
- The calibration_context.md and REVIEW_PROMPT.md were created specifically for this review package.

This package was assembled without modifying any source code, schemas, pipeline, or report generation logic. It is purely a documentation + selection + packaging exercise.

Raw audio was intentionally and completely excluded.