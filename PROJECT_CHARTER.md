# AudioAtlas Project Charter

**Current phase:** convergence and public-alpha hardening
**Current release line:** `0.2.0a6`
**Authoritative for:** product identity, scope, interpretation rules, and release direction

## North star

AudioAtlas turns one audio file into a **private, portable listening map**:
measured context, places worth inspecting, and explicit limits on what each
measurement establishes.

The primary user story is simple:

> Give AudioAtlas one track. Receive a local report that helps decide where to
> listen more carefully without pretending to decide whether the music is good.

The static report bundle—HTML, Markdown, JSON, and PNGs—is the product. The CLI,
sections workflow, and catalog mode exist to produce or organize that artifact.

## Intended users

AudioAtlas is for musicians, producers, engineers, researchers, and careful
listeners who want transparent measurements without a score, prescription, or
cloud service. It should remain useful to both technical and nontechnical users,
while staying honest about installation and platform requirements.

## Protected intent

AudioAtlas should remain:

- local-first, offline, and private by default;
- one-track-first, with optional manual sections, descriptive catalogs, and
  guarded deltas between user-asserted revisions of that same track;
- measurement-based and inspectable;
- static and portable rather than tied to a hosted dashboard;
- restrained about interpretation;
- reproducible enough that each report records its configuration and schema.

AudioAtlas should not become:

- a mix, mastering, or quality score;
- an automated mastering adviser;
- a genre, instrument, source, key, or section classifier;
- a reference-track ranking system or cross-track winner comparison;
- a cloud account, telemetry product, DAW, or real-time playback engine;
- a plugin platform before a concrete need justifies that complexity.

A feature that violates this boundary requires explicit owner approval and a
new product decision, not an incidental pull request.

## Product contract

1. **Measurements and claims must match.** A valid number does not justify a
   broader musical or causal story.
2. **No normalization on load.** Original decoded levels are preserved.
3. **No local path disclosure by default.** Portable labels are the default;
   absolute paths require explicit opt-in.
4. **One bad file must not erase good work.** Existing complete reports survive
   failed reruns, and batch mode records per-file failures unless strict mode is
   requested.
5. **Rendered depth is not analytical depth.** Graph profiles select PNGs only;
   the complete analysis summary remains available.
6. **Compatibility should be deliberate.** When a misleading name is repaired,
   prefer a precise new field plus a documented temporary alias rather than a
   silent semantic change.
7. **Comparison requires provenance.** Revision deltas state whether analysis
   configuration, measurement code, dependencies, decoder, and environment
   fingerprints match; finding-rule identity is assessed separately, and
   incompatible measurement reports are refused by default.
8. **A revision token is an assertion, not recognition.** Matching hashed tokens
   mean the user supplied the same identity token. They do not prove that the
   underlying files contain the same composition. Conflicting tokens cannot be
   overridden.
9. **Deltas remain descriptive.** Same-track revision comparison may report
   B-minus-A measurements and prompt churn, never a winner, score, or preferred
   version.

## Project vocabulary

| Term | Meaning in AudioAtlas | Common misunderstanding |
|---|---|---|
| Finding / review prompt | A threshold-backed observation worth checking | A diagnosis or verdict |
| Relative dB | Shape normalized within this analysis view | Calibrated dBFS or a cross-song score |
| Relative mean band power | Mean STFT power per included FFT bin, normalized within the file | Total energy integrated over each differently sized band |
| PLR | Approximate true peak minus integrated LUFS | Dynamic range, compression amount, or normalization loss |
| Section | A user-supplied source time range | Automatically detected song structure |
| Graph profile | A rendered-plot selection | A cheaper or incomplete analysis mode |
| Catalog pattern | A trait shared by many files in a folder | A ranking or recommendation |
| Revision identity | SHA-256 of a user-supplied token shared by exports of one track | Automatic audio recognition |
| Revision delta | B-minus-A measurements for two asserted revisions of one track | A reference-track verdict or preference |
| Compatible analysis signature | Hash of configuration, measurement code, methods, and dependency/decoder versions | Proof of bit-identical results on every machine |

## Evidence hierarchy

| Question | Strongest evidence | Insufficient by itself |
|---|---|---|
| What did AudioAtlas calculate? | Source code, tests, generated JSON | Report prose alone |
| What does a metric mean? | Implementation plus a metric-appropriate definition | Familiar-sounding label |
| Does a finding help? | Representative synthetic counterexamples and musical calibration review | One attractive example |
| Did a workflow run? | Executed command and inspected output | README claim or supplied log alone |
| Is a report portable? | Shared-folder inspection and path-leak test | Intention or UI copy |
| Are two reports comparable? | Matching recorded provenance signatures plus explicit scope checks | Similar filenames or matching package labels alone |
| Is a launcher nontechnical? | Native platform rehearsal from a clean machine | Presence of a double-click script |

## Current release priorities

The `0.2.0a6` line prioritizes:

1. interpretation integrity and stable finding rules;
2. safe errors, path privacy, and partial batch success;
3. coherent output publication without stale artifacts;
4. release/documentation and compatibility truth;
5. a frozen-evidence calibration replay workflow and cross-platform launcher evidence;
6. guarded same-track revision deltas backed by explicit provenance;
7. accessible, keyboard-complete static reports with measured-value plot descriptions;
8. private local notes and direct navigation between prompts, plots, and definitions;
9. mechanism-level invariant and malformed-input regression coverage.

New generic metrics, themes, dashboards, and major interaction systems are below
those priorities.

## Release gate

A public beta should require more than a passing unit suite. At minimum:

- all tests, lint, source/wheel builds, and clean-wheel smoke checks pass;
- supported Python/platform claims are represented in CI or explicitly narrowed;
- deterministic counterexample fixtures cover the finding rules;
- a private, authorized musical corpus has been reviewed and the outcome logged;
- candidate finding-rule changes have been replayed against the frozen reviewed
  summaries and any prompt churn adjudicated;
- no known default finding makes a factual or context-blind musical claim;
- default reports and catalogs contain no machine-local absolute paths;
- native launcher wording matches what has actually been rehearsed.

## Source precedence

Runtime behavior and tests outrank stale prose. This charter outranks archived
design/review notes. `docs/FINDING_RULES.md` is authoritative for default finding
semantics. `docs/SUMMARY_SCHEMA.md` is authoritative for serialized fields.
`docs/COMPATIBILITY.md` is authoritative for alias retention and removal.
`docs/HOPEFUL_SKEPTIC_PROJECT_EDITION.md` governs recurring review behavior
until a named freshness trigger makes it stale.
