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

Fixture success does not establish usefulness on music.

### Private authorized musical corpus

Maintain a noncommitted set of roughly 20–30 authorized tracks or stems spanning
sparse/dense, acoustic/electronic, bright/dark/bandwidth-limited, mono/wide,
clean/distorted, rough/final, lossless/lossy, and varied sample-rate material.

Do not commit copyrighted/private audio, generated private reports, source
filenames, or local paths. Version-control only anonymous coverage/outcome
records when appropriate.

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
non-claim boundaries, checks, metrics, thresholds, and graph fields. It does not
include filenames or report paths. The optional private map connects asset IDs
to basenames and relative report folders; keep it out of version control.

The script preflights both outputs and refuses to overwrite existing labels
unless `--force` is supplied.

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
reviewer/date, anonymous asset ID, report evidence hash, and finding-payload
hash.

## What this package does not claim

The repository includes the harness, public fixtures, runbook, and templates. It
does **not** claim that private musical calibration is complete. That requires
human listening, authorized material, a frozen record, and rule-level
adjudication.
