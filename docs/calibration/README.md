# AudioAtlas Calibration Workflow

Unit tests establish deterministic behavior; they do not prove that a default
review prompt is useful across music. This folder defines the additional beta
calibration gate.

## Public deterministic corpus

Generate rights-safe fixtures:

```bash
uv run python scripts/generate_calibration_fixtures.py
```

The generated folder is intentionally ignored by Git. The generated synthetic
fixtures contain no third-party audio and are distributed under the repository's
MIT license. The script covers
silence, tones, impulses, clipping, over-nominal float audio, short input,
dual-mono, anti-phase, decorrelated stereo, and a corrupt header. Tests may call
the generator in a temporary directory.

For each fixture, verify both positive and negative behavior. A fixture designed
to exercise one rule should not accidentally create unsupported musical claims
from unrelated measurements.

## Private musical corpus

Maintain a noncommitted set of authorized tracks or stems spanning at least:

- sparse and dense arrangements;
- acoustic and electronic material;
- bright, dark, broadband, and intentionally bandwidth-limited sources;
- mono, dual-mono, narrow, wide, and phase-rich stereo;
- clean, clipped, intentionally distorted, rough, and final material;
- lossless and lossy delivery formats.

A practical first pass is 20–30 items. Do not commit copyrighted or private
audio. Record only authorized labels and review outcomes in a private copy of
`musical_corpus_review_template.csv`.

## Prompt adjudication

For every triggered finding, assign exactly one outcome:

- `helpful`
- `true_but_redundant`
- `context_dependent`
- `misleading`
- `factually_wrong`

Record the rule ID/version, triggering evidence, reviewer rationale, and any
wording or eligibility change. Use `finding_review_template.csv`.

A rule remains default only when its useful signal clearly exceeds its
false-authority cost. Any `factually_wrong` result blocks beta until repaired.
Repeated `misleading` or `context_dependent` outcomes require narrower
eligibility, narrower prose, or removal from default findings.

## What this package does not claim

The repository includes the harness and public fixtures. It does **not** claim
that the private musical calibration gate has been completed. That requires
human listening, authorized material, and a frozen review record.
