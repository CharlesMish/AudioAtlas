# AudioAtlas Calibration Workflow

Unit tests establish deterministic behavior; they do not prove that a default
review prompt is useful across music. This folder defines the additional beta
calibration gate and provides share-safe record templates.

For the concrete end-to-end procedure, use
[`CALIBRATION_RUNBOOK.md`](CALIBRATION_RUNBOOK.md).

## Two evidence sets

### Public deterministic fixtures

Generate rights-safe fixtures:

```bash
uv run python scripts/generate_calibration_fixtures.py
```

The generated folder is ignored by Git. The synthetic fixtures contain no
third-party audio and are distributed under the repository MIT license. The
script covers silence, tones, impulses, clipping, over-nominal float audio,
short input, dual-mono, anti-phase, decorrelated stereo, and a corrupt header.
Tests may call the generator in a temporary directory.

Use fixtures to establish:

- exact positive and negative trigger behavior;
- numerical monotonicity and boundary handling;
- path safety, decoder failure behavior, and report stability;
- counterexamples that prevent unrelated musical claims.

The committed malformed-header fixtures under `tests/fixtures/malformed/` also
lock the user-facing error boundary for truncated WAV and FLAC-like inputs.
Fixture success does not establish usefulness on music.

### Private authorized musical corpus

Maintain a noncommitted set of roughly 20–30 authorized tracks or stems spanning
sparse/dense, acoustic/electronic, bright/dark/bandwidth-limited, mono/wide,
clean/distorted, rough/final, lossless/lossy, and varied sample-rate material.

Do not commit copyrighted/private audio, generated private reports, source
filenames, local paths, or the private asset map. Version-control only anonymous
coverage/outcome records when appropriate.

## Preparing the human review sheet

After generating reports, seed a worksheet with every triggered finding,
including items suppressed by the visible report cap:

```bash
uv run python scripts/prepare_calibration_review.py \
  private_calibration/reports \
  --out private_calibration/finding_review.csv \
  --private-map private_calibration/private_asset_map.csv
```

The main worksheet uses anonymous `asset-###` IDs and includes package, schema,
ruleset, report/finding hashes, trigger visibility, exact prompt wording,
non-claim boundaries, checks, metrics, thresholds, graph fields, and the report's
analysis-configuration and comparability signatures. It does not include
filenames or report paths. The optional private map connects asset IDs to
basenames and relative report folders; keep it out of version control.

The script preflights both outputs and refuses to overwrite existing labels
unless `--force` is supplied.

## Replaying a candidate ruleset

After the first human review has been frozen, run the candidate checkout's
finding logic against the saved summaries:

```bash
uv run python scripts/replay_calibration_rules.py \
  private_calibration/reports \
  --asset-map private_calibration/private_asset_map.csv \
  --review-ledger private_calibration/finding_review.csv \
  --out private_calibration/rule_replay.json \
  --csv private_calibration/rule_replay.csv
```

The replay tool:

- verifies each report's current `summary.json`, `findings.json`, and output
  manifest against the frozen `report_evidence_sha256` in the review ledger;
- refuses a changed or missing evidence set instead of silently comparing a new
  analysis with old human labels;
- reruns the current finding rules on the saved summary, without opening or
  copying audio;
- reports anonymous per-rule `appeared`, `disappeared`, `changed`, and
  `unchanged` outcomes, including payload hashes and changed fields;
- includes baseline/candidate finding-rule implementation hashes, the
  candidate ruleset, and report comparability signatures, but no source
  filenames or report paths in the public replay outputs.

Replay isolates **finding-rule churn**. It does not rerun DSP measurements, prove
that a changed prompt is useful, replace listening, or justify comparing reports
with incompatible analysis provenance. A change to measurement code or analysis
configuration requires fresh reports and a new human-review record.

## Prompt review labels

For each triggered rule, record exactly one:

- `helpful`
- `true_but_redundant`
- `context_dependent`
- `misleading`
- `factually_wrong`

Also record whether evidence was easy to trace, the listening check was
completed/useful, and the non-claim prevented overinterpretation.

## Retention gate

A default prompt remains active only when:

1. deterministic trigger and counterexample tests pass;
2. the report sentence follows from the metric;
3. common counterexamples are documented;
4. musical review shows useful signal clearly outweighing false-authority cost;
5. the prompt points to concrete evidence or a graph;
6. the same observation cannot be presented more safely as technical context.

Any `factually_wrong` result blocks beta until repaired. Repeated `misleading` or
`context_dependent` results require narrower eligibility/prose or removal from
default findings. A failed gate does not require deleting the measurement: keep
it in summaries/plots when technically useful.

## Included templates

- `musical_corpus_review_template.csv` — anonymous corpus coverage.
- `finding_review_template.csv` — per-trigger schema produced by the preparation
  script.
- `MANUAL_CALIBRATION_WORKSHEET.csv` — aggregate per-rule decision ledger.

Calibration records should identify package, schema, and ruleset versions,
reviewer/date, anonymous asset ID, report evidence hash, finding-payload hash,
and analysis provenance signatures.

## What this package does not claim

The repository includes the harness, public fixtures, invariant tests, runbook,
review preparation, and ruleset replay. It does **not** claim that private
musical calibration is complete. That requires human listening, authorized
material, a frozen record, and rule-level adjudication.
