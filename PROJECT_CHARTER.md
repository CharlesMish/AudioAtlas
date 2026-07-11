# AudioAtlas Project Charter

**Current phase:** convergence and public-alpha hardening
**Current release line:** `0.2.0a3`
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
- one-track-first, with optional manual sections and descriptive catalogs;
- measurement-based and inspectable;
- static and portable rather than tied to a hosted dashboard;
- restrained about interpretation;
- reproducible enough that each report records its configuration and schema.

AudioAtlas should not become:

- a mix, mastering, or quality score;
- an automated mastering adviser;
- a genre, instrument, source, key, or section classifier;
- a reference-track ranking system;
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

## Evidence hierarchy

| Question | Strongest evidence | Insufficient by itself |
|---|---|---|
| What did AudioAtlas calculate? | Source code, tests, generated JSON | Report prose alone |
| What does a metric mean? | Implementation plus a metric-appropriate definition | Familiar-sounding label |
| Does a finding help? | Representative synthetic counterexamples and musical calibration review | One attractive example |
| Did a workflow run? | Executed command and inspected output | README claim or supplied log alone |
| Is a report portable? | Shared-folder inspection and path-leak test | Intention or UI copy |
| Is a launcher nontechnical? | Native platform rehearsal from a clean machine | Presence of a double-click script |

## Current release priorities

The `0.2.0a3` line prioritizes:

1. interpretation integrity and stable finding rules;
2. safe errors, path privacy, and partial batch success;
3. coherent output publication without stale artifacts;
4. release/documentation and compatibility truth;
5. a runnable musical-calibration handoff and cross-platform launcher evidence;
6. lightweight command discovery without weakening the analysis stack.

New generic metrics, themes, dashboards, and major interaction systems are below
those priorities.

## Release gate

A public beta should require more than a passing unit suite. At minimum:

- all tests, lint, source/wheel builds, and clean-wheel smoke checks pass;
- supported Python/platform claims are represented in CI or explicitly narrowed;
- deterministic counterexample fixtures cover the finding rules;
- a private, authorized musical corpus has been reviewed and the outcome logged;
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
