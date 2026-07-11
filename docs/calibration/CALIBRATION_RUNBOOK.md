# AudioAtlas Musical Calibration Runbook

This runbook turns the private 20–30 item listening gate into a repeatable,
reviewable process. It is deliberately separate from unit testing: synthetic
fixtures establish calculation and trigger behavior; authorized musical
material establishes whether a default prompt helps more often than it creates
false authority.

## Guardrails

- Use only audio the reviewer is authorized to inspect.
- Keep audio, generated private reports, source filenames, and the private asset
  map out of version control and release bundles.
- Run one frozen package version, finding ruleset, configuration, and graph
  profile for the primary pass.
- Review every triggered item, including findings suppressed from the visible
  report cap.
- Do not add new rules or graphs during the run. Record candidate changes, then
  adjudicate after the corpus is complete.
- A measurement may remain in JSON/plots even when its default prompt is removed.

## Recommended private workspace

```text
private_calibration/
├── audio/                         # authorized source files; never commit
├── reports/                       # generated AudioAtlas reports; never commit
├── private_asset_map.csv          # asset ID ↔ filename/report folder; never commit
├── finding_review.csv             # per-trigger human judgments
├── corpus_manifest.csv            # anonymous coverage record
├── rule_decisions.csv             # aggregate decision ledger
└── session_notes.md               # methods, anomalies, and deviations
```

Add the workspace to a private/global ignore before beginning.

## Stage 1 — Freeze the run contract

Record in `session_notes.md`:

- AudioAtlas package version;
- summary/findings/catalog schema versions;
- finding ruleset version;
- operating system and Python version;
- graph profile and any graph overrides;
- analysis configuration overrides;
- reviewer identity or stable pseudonym;
- date and whether this is an initial review or a repeat/adjudication pass.

The primary pass should normally use the default analysis configuration and
`standard` graph profile. Deviations are allowed, but they must be recorded and
should not be mixed silently within one decision set.

## Stage 2 — Build a varied, authorized corpus

Aim for roughly 20–30 tracks or stems. The point is coverage, not a statistical
claim about all music. Include meaningful contrasts across:

- sparse/dense arrangement;
- acoustic/electronic material;
- bright/dark/broadband/intentionally bandwidth-limited sources;
- mono, dual-mono, narrow, wide, and phase-rich stereo;
- clean, clipped, intentionally distorted, rough, and final material;
- lossless/lossy formats, multiple sample rates, and short/long material.

Assign anonymous `asset-###` IDs in the private manifest. Do not encode quality
or expected findings into the ID.

## Stage 3 — Generate reports

For a folder corpus:

```bash
uv run audioatlas batch private_calibration/audio \
  --out private_calibration/reports \
  --graphs-profile standard
```

Inspect `catalog_summary.json` for skipped or failed files before reviewing any
findings. A skipped file is a coverage gap, not a negative result.

For material that should not be grouped in one batch, generate individual
reports under `private_calibration/reports/` with the same configuration.

## Stage 4 — Seed the review worksheet

Create an anonymous worksheet and an optional private map:

```bash
uv run python scripts/prepare_calibration_review.py \
  private_calibration/reports \
  --out private_calibration/finding_review.csv \
  --private-map private_calibration/private_asset_map.csv
```

The shareable review sheet contains anonymous asset IDs, package/schema/ruleset
versions, report and per-finding hashes, exact prompt/non-claim wording, all
triggered rules, and whether each item appeared inside the visible report cap.
It does **not** contain source filenames or report paths.

The optional private map contains basenames and relative report folders. Keep it
private. The script preflights both outputs and refuses to overwrite either
unless `--force` is supplied so completed human labels are not erased
accidentally.

## Stage 5 — Review each asset in two passes

### Pass A: listen before reading the prompt

Record brief observations without seeing the generated finding when practical.
This is not a formal blind trial; it is a simple anchoring control. Note passages
that independently draw attention and any known source intent that materially
affects interpretation.

### Pass B: inspect the prompt and evidence

For every triggered row:

1. read the supported claim and `does_not_mean` boundary;
2. inspect every associated graph and cited time range;
3. perform the suggested listening check where meaningful;
4. compare the prompt with the Pass A notes;
5. assign exactly one outcome;
6. record whether evidence was easy to trace, the listening check helped, and
   the non-claim prevented overinterpretation.

Review suppressed findings too. Suppression is presentation priority, not proof
that the rule is harmless.

## Outcome vocabulary

- `helpful` — correctly bounded and materially improves where/how to inspect.
- `true_but_redundant` — accurate, but adds little beyond nearby evidence or
  another prompt.
- `context_dependent` — factually bounded but useful only under context the rule
  cannot currently establish.
- `misleading` — invites a stronger or different conclusion than the evidence
  warrants, despite not being literally false.
- `factually_wrong` — the prompt or its explanatory claim is false for the
  measured case.

Do not use unlabeled synonyms; consistent vocabulary is necessary for aggregate
adjudication.

## Stage 6 — Adjudicate by rule

Use `MANUAL_CALIBRATION_WORKSHEET.csv` to aggregate outcomes for each rule.
Counts inform the decision but do not replace case review.

Hard gates:

- any `factually_wrong` result blocks a beta claim until repaired and retested;
- repeated `misleading` results require narrower eligibility/prose or removal
  from default prompts;
- repeated `context_dependent` results require an explicit decision: add a
  defensible eligibility discriminator, narrow the sentence, or move the item
  to technical context only;
- a rule with low trigger frequency is not automatically good or bad;
- a rule with many `helpful` labels can still fail if its harmful cases are
  severe and predictable.

For every keep/change/remove decision, record:

- exact evidence pattern;
- proposed eligibility and wording change;
- counterexample fixture/test required;
- schema/ruleset impact;
- preservation constraint.

## Stage 7 — Re-run changed rules

After a rule change:

1. update the rule ledger and ruleset version;
2. add or revise deterministic positive and counterexample tests;
3. regenerate affected reports from the same source audio/configuration;
4. create a fresh worksheet rather than editing hashes in place;
5. re-review affected cases and any new triggers;
6. preserve the old decision record as historical evidence.

Do not compare stale reports against new rule prose.

## Stage 8 — Freeze the gate record

A calibration release record should contain only share-safe material:

- anonymous corpus coverage table;
- per-trigger outcomes without filenames or local paths;
- aggregate rule decisions;
- package/schema/ruleset versions;
- report evidence hashes;
- methods and deviations;
- explicit residual limitations.

Do not publish the private asset map or audio. Do not describe a 20–30 item
purposeful corpus as representative of all genres, workflows, or listeners.

## Completion statement

A defensible completion statement is:

> Default AudioAtlas review prompts were examined on an authorized, varied
> calibration corpus under the recorded package/ruleset/configuration. Every
> trigger was labeled with the project outcome vocabulary, harmful cases were
> adjudicated, and the share-safe record preserves evidence hashes and residual
> limits.

It is not defensible to say the findings are “scientifically validated” or
universally accurate from this gate alone.
