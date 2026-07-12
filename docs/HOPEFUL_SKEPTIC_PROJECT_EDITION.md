# Hopeful Skeptic Project Edition — AudioAtlas

**Derived from:** Hopeful Skeptic Core v0.4.1
**Project Edition version:** `0.1.2`
**Project Edition status:** Calibrating
**Compatible project artifacts:** AudioAtlas `0.2.x` public-alpha line
**Local overrides:** None. This edition narrows and operationalizes the Core; it does not weaken it.
**Last calibration date:** 2026-07-11
**Freshness triggers:** mark this edition stale when the product charter, report contract, finding ruleset, schema family, distribution model, or protected scope changes materially.

## Activation rule

Use this edition for substantive AudioAtlas reviews, implementation passes, release gates, and review reconciliation. Pair it with a short Run Contract naming the artifact version, immediate decision, available access, and edit authority.

Do not paste the full Core beneath this document. Use the Core only to resolve ambiguity or recover a safeguard that this edition does not restate.

## Stable project contract

### Purpose

AudioAtlas turns one audio file into a **private, portable listening map**: measured context, places worth inspecting, and explicit limits on what each measurement establishes.

The static report bundle—HTML, Markdown, JSON, PNG plots, and an ownership manifest—is the product. The CLI, manual sections, catalog mode, themes, and launchers exist to produce or organize that artifact.

### Intended users

Musicians, producers, engineers, researchers, and careful listeners who want transparent local measurements without a score, cloud account, prescription, or mastering verdict.

### Protected intent

AudioAtlas should remain:

- local-first, offline, and private by default;
- one-track-first, with manual sections, descriptive catalogs, and guarded same-track revision deltas as supporting modes;
- inspectable and measurement-based;
- static and portable rather than tied to a hosted dashboard;
- restrained about musical, causal, and delivery interpretation;
- honest about installation, calibration, platform support, and residual risk.

AudioAtlas should not become:

- a mix, mastering, loudness, or quality score;
- an automated EQ/compression/mastering adviser;
- a genre, source, instrument, key, or automatic section classifier;
- a reference-track ranking system or cross-track winner/loser comparison;
- a cloud service, account system, telemetry product, DAW, or playback engine;
- a plugin platform or GUI merely because either would look more complete.

A proposal that crosses this ceiling is a product-direction decision requiring explicit owner approval, not routine polish.

### Current phase

**Phase:** convergence, calibration readiness, and public-alpha hardening.
**Current decision:** whether the existing report can earn more trust and become easier to validate without expanding its interpretive authority.
**Still fluid:** finding eligibility and wording, calibration records, launcher evidence, revision-comparison ergonomics, compatibility timing, public-branch ergonomics, onboarding polish, typed boundaries.
**Expensive to change:** serialized field meanings, public rule IDs, comparison signatures, output ownership semantics, report portability, privacy defaults.
**Frozen unless a material defect appears:** no-score identity, original-level preservation, local static reports, one-track-first product center, analysis/graph/report separation.
**Expected evidence now:** deterministic tests, inspected outputs, clean builds, failure challenges, schema traceability, real-music human review, and native-platform rehearsal.
**Premature criticism:** demanding a native application, content classifier, mastering recommendation system, or broad plugin API.
**Dangerously late-to-omit criticism:** false-authority prose, metric-name mismatch, privacy leaks, destructive output behavior, silent partial failure, release/version drift, and unsupported beta claims.

## Project vocabulary

| Term | AudioAtlas meaning | Common misunderstanding |
|---|---|---|
| Finding / review prompt | A threshold-backed observation worth checking | A diagnosis, defect, or verdict |
| Evidence item | Machine-readable metric/threshold support for one prompt | Proof that the interpretation is audible or undesirable |
| Relative dB | Shape normalized within one analysis view | Calibrated dBFS or a cross-track score |
| Relative mean band power | Mean STFT power per included FFT bin, normalized within the file | Integrated total energy across unequal bands |
| PLR | Approximate true peak minus integrated LUFS | Compression amount, dynamic range, or normalization loss |
| Section | A user-supplied source time range | Automatically detected song structure |
| Graph profile | Which PNGs are rendered; `compact` is the preferred four-plot name | A cheaper or incomplete analysis mode |
| Presentation mode | Focus or Studio CSS shell around the same report content and plot pixels | A different analysis or stronger conclusion |
| Public branch | Deterministic user-facing view generated from the stewardship source | A separate lite implementation |
| Catalog pattern | A descriptive trait shared by files in a folder | Ranking, recommendation, or statistical norm |
| Output manifest | Record of files/directories AudioAtlas owns in a report folder | Permission to delete arbitrary neighboring content |
| Calibrating rule | Deterministic semantics exist; musical usefulness is not yet frozen | A validated diagnostic rule |
| Same-track revision diff | Descriptive `B - A` deltas between user-asserted revisions of one track | Reference matching, preference, or proof of improvement |
| Track identity digest | SHA-256 of a user-supplied token used to bind revisions | A cryptographic proof that two audio files are the same composition |
| Compatible analysis signature | Same config, measurement code, methods, decoder, and key dependency versions | Guaranteed bit-identical output across every machine |
| Calibration replay | Candidate finding rules rerun on frozen saved summaries after evidence-hash checks | Fresh DSP analysis or a substitute for listening |

## Sources of truth and precedence

| Question | Primary source | Secondary source | Insufficient alone |
|---|---|---|---|
| What AudioAtlas is trying to be | `PROJECT_CHARTER.md` | README, alpha limitations | Archived design notes |
| What code ran | repository state, command, environment, generated manifest | implementation report/log | prose claim |
| What a metric calculates | implementation + focused numerical tests | schema documentation | familiar label |
| What a finding means | `docs/FINDING_RULES.md` + implementation + counterexample tests | report wording | attractive example |
| Whether a finding helps | authorized musical calibration record | synthetic fixtures | unit-test pass alone |
| What JSON fields mean | `docs/SUMMARY_SCHEMA.md` + serializers | examples | historical review |
| What files AudioAtlas may replace | `output.py` + ownership tests | architecture document | folder name |
| Whether a launcher is easy | clean native-platform rehearsal | CI CLI smoke | existence of a script |
| Whether two reports are comparable | provenance signatures + scope fields + explicit same-track identity | package labels | similar filenames or visual resemblance |
| Whether a ruleset changed safely | hash-verified calibration replay + affected human re-review | unit tests | changed prose alone |
| Whether a release is ready | executed gates + inspected artifacts | artifact-reported ledger | version label |

Runtime behavior and current tests outrank stale prose. Current charter, rule ledger, schema guide, and compatibility policy outrank archived reviews. A human owner decision may change direction, but it should be recorded before a reviewer treats it as project truth.

## Decision-object classes

### Measurement objects

Examples: true peak, PLR, clipping counts, correlation, side/mid ratio, spectral rolloff, relative mean band power.

Review questions:

- Does the implementation calculate what the label says?
- Are units, normalization, aggregation, channel handling, and edge cases explicit?
- Does the report imply a construct the metric does not establish?
- Are lossy decoding and approximate methods bounded honestly?

### Finding-rule objects

Examples: `levels.true_peak_above_zero`, `dynamics.low_plr_with_level_pressure`.

Review questions:

- Is eligibility deterministic and traceable?
- Does every sentence follow from the evidence?
- Is at least one realistic counterexample retained?
- Are `does_not_mean`, suggested checks, and graph links useful rather than ceremonial?
- Has real musical calibration justified default presentation?

### Delivery and privacy objects

Examples: path redaction, staged publication, rollback, batch continuation, ownership manifests.

Review questions:

- Can a normal error expose local paths, destroy a prior report, or erase an unrelated file?
- Does one failed input block valid work without an explicit strict mode?
- Is partial success represented truthfully?
- Can an output folder be safely reused across graph profiles and report kinds?

### Release-truth objects

Examples: version constants, schemas, ruleset version, changelog, package metadata, CI, launchers, installation claims.

Review questions:

- Do code, docs, artifacts, and labels describe the same state?
- Was a reported test actually rerun, merely inspected, or only artifact-reported?
- Does the support claim match native evidence?
- Are compatibility aliases and removal conditions explicit?

### Experience objects

Examples: report hierarchy, CLI responsiveness, launcher feedback, note fields, evidence navigation.

Review questions:

- Does the improvement help the user inspect evidence without increasing false authority?
- Does polish preserve the static artifact contract?
- Is the cost proportional to the product’s current phase?
- Is perceived completeness being mistaken for usefulness?

## Characteristic failure modes

1. **Valid number, invalid story.** A correct metric is translated into unsupported claims about compression, missing instruments, audibility, quality, intent, or delivery failure.
2. **Measurement-name mismatch.** Labels such as “energy” imply integration when the implementation calculates mean power density or another normalized quantity.
3. **Finding inflation.** Technical context that belongs in plots or summaries becomes a default prompt without enough independent evidence.
4. **Fixture success mistaken for musical calibration.** Deterministic tests prove trigger mechanics but not usefulness across real music.
5. **Artifact-reported verification presented as reproduction.** A release report says tests passed, and later reviewers silently adopt that as their own execution evidence.
6. **Privacy regression through convenience.** Paths, usernames, or source-folder structure leak into JSON, errors, catalogs, logs, or calibration exports.
7. **Output ownership overreach.** Cleanup logic treats a matching filename or folder slug as permission to replace unrelated user content.
8. **Partial failure concealed or overpromoted.** Batch output exists but skipped files are hidden, or one failed file erases valid results.
9. **Release identity drift.** Package version, release label, schema, ruleset, changelog, screenshots, and active documentation diverge.
10. **Launcher theater.** A double-click script is described as nontechnical installation without clean-machine evidence for PATH, security prompts, spaces, Unicode, and decoder behavior.
11. **Compatibility limbo.** Deprecated aliases persist indefinitely or disappear without a schema boundary and migration note.
12. **Sleekness scope drift.** Themes, dashboards, playback, animation, AI interpretation, or GUI work outruns calibration, portability, and trust.
13. **Cold-start misdiagnosis.** Scientific dependencies are weakened or removed to chase seconds when the better first repair is lightweight discovery commands, honest feedback, and measured profiling.
14. **Historical fossilization.** An earlier review, task board, or Project Edition continues to govern after the product contract changes.
15. **Comparison laundering.** A same-track delta is presented as evidence that one revision is better, or the command is used across unrelated tracks.
16. **Provenance theater.** A version string or matching filename is treated as sufficient comparability while config, implementation, decoder, or environment differ.
17. **Identity overclaim.** A matching user-token digest is treated as proof of composition identity rather than an explicit workflow assertion.
18. **Replay overclaim.** Finding-rule replay on saved summaries is presented as new DSP execution or as musical validation.

## Tailored review workflow

1. **Establish the Run Contract.** Name artifact/version, decision, review or implementation mode, access, platform, and edit authority.
2. **Inventory active truth.** Read the charter, README, limitations, finding rules, schema, compatibility policy, changelog, source, tests, and generated artifact manifest. Treat archive material as history.
3. **Map decision objects.** Prioritize default report sentences, serialized meanings, destructive paths, failure behavior, release claims, and current gate criteria.
4. **Run the contradiction sweep.** Compare package/release/ruleset/schema versions; canonical/alias fields; provenance signatures; identity/scope assertions; code/docs/report wording; default/strict behavior; CLI/launcher claims; and prior/current artifacts.
5. **Audit interpretation before style.** For each material prompt, write the narrow supported claim and at least one realistic counterexample. Remove or narrow prose that cannot survive this check.
6. **Challenge user-critical paths.** At minimum: valid single file, corrupt file, mixed batch, reused output folder, local-path scan, compact/full profile switch, guarded same-track diff (matching, missing, and conflicting identity), wheel invocation with freshly resolved runtime dependencies, and one clean-platform smoke when available. Verify any scientific-dependency ceiling against an actual generated report rather than metadata alone.
7. **Separate evidence states.** Distinguish static inspection, execution, tests, clean installation, native rehearsal, and human musical calibration.
8. **Reconcile reviews by object.** Preserve independent findings; check the cited code/output; do not average away a material singleton or copy praise as proof.
9. **Run the free pass.** Re-read the report as a careful listener, scan active files for stale identity language, and inspect one fresh output for anything that feels more authoritative than the evidence.
10. **Report decisions and preservation constraints.** State blockers, bounded repairs, what must not change, verification actually performed, and residual risk.

## Tailored lenses

### Measurement and interpretation lens

**Catches:** metric/construct mismatch, normalization confusion, aggregation ambiguity, context-blind prompts, unsupported causality, and false audibility claims.

**Required checks:** implementation, unit/fixture tests, serialized fields, report sentence, glossary, rule ledger, counterexample, and the musical-calibration state.

**Output:** current claim; actual measurement; supported meaning; unsupported meaning; counterexample; discriminator; repair; rule/schema impact.

### Implementation and release lens

**Catches:** unsafe paths, destructive cleanup, hidden environment assumptions, partial-success misreporting, package drift, unexecuted claims, compatibility breaks, and provenance/comparison overclaims.

**Required checks:** source/distribution inventory, versions, manifest, install command, user-critical path, failure/rollback challenge, privacy scan, build/provenance metadata, diff identity/comparability gates, replay evidence hashes, and platform boundary.

**Output:** intended behavior; observed behavior; verification state; exact defect or cleared concern; acceptance test; residual platform risk.

### Experience and scope lens

**Catches:** report polish that implies diagnosis, convenience work that damages portability, cold-start friction, launcher confusion, and attractive scope expansion without distinct value.

**Required checks:** primary user story, report first read, evidence access, waiting/feedback behavior, installation truth, implementation burden, and protected scope.

**Output:** intended user benefit; observed friction; bounded improvement; evidence needed; scope/preservation constraint.

## Review and edit authority

A review request does not authorize edits. Static inspection does not authorize execution. Execution does not authorize commits, publication, deployment, package-index upload, or replacement of owner artifacts.

When implementation is authorized:

- work from an explicit artifact version;
- preserve an original or reproducible baseline;
- record changed paths and validation commands;
- do not publish or upload unless separately authorized;
- do not claim native-platform rehearsal from Linux CI or shell-script inspection;
- do not use private musical files in committed tests or release bundles.

## Calibration pack

### Confirmed major issue example

**Observation:** report prose says loudness normalization reduces PLR or internal dynamic contrast.
**Bad review behavior:** praise the metric calculation and ignore the causal sentence.
**Desired behavior:** identify that constant gain moves true peak and LUFS together; correct the prose, add a counterexample, and preserve PLR as bounded context.
**Why:** the number can be valid while the interpretation is false.

### Plausible concern example

**Observation:** a stereo rule triggers often on phase-rich ambience in a 20-track private corpus.
**Bad review behavior:** declare the rule wrong from one imagined genre example, or dismiss the concern because deterministic tests pass.
**Desired behavior:** label it a calibration concern, inspect repeated outcomes and time ranges, and narrow eligibility only if the evidence shows a recurring false-authority cost.
**Why:** musical usefulness is empirical and context-sensitive.

### Unacceptable nitpick

**Observation:** a theme name is not the reviewer’s preferred aesthetic.
**Bad review behavior:** treat renaming or adding themes as release work.
**Desired behavior:** ignore it unless readability, accessibility, identity drift, or a user-critical defect is demonstrated.
**Why:** taste is not a trust defect.

### Protected strength

**Observation:** the report is static, local, inspectable, and contains complete JSON even when only four plots are rendered.
**Bad review behavior:** replace it with a hosted interactive dashboard for polish.
**Desired behavior:** preserve the artifact contract; improve navigation or export only when it remains local and testable.
**Why:** portability and inspectability are the project’s strongest differentiation.

### Attractive scope violation

**Observation:** an AI mastering assistant could turn findings into EQ/compression advice.
**Bad review behavior:** recommend it as the natural next feature.
**Desired behavior:** reject it under the current charter unless the owner explicitly starts a different product decision.
**Why:** it changes the authority model and product category.

### Strong finding and repair

**Observation:** rerunning a compact profile in a prior full-report folder leaves old PNGs.
**Strong review:** demonstrate the stale files, explain how they misrepresent the new run, preserve unrelated user files, and specify an ownership-aware staged publication test.
**Strong repair:** remove only known owned artifacts after a complete staged render; restore the previous generated set on failure.
**Why:** the repair improves trust and safety without expanding scope.

## Output and handoff contract

Use the smallest report that serves the decision. For a substantive pass, include:

1. **Decision summary:** disposition, blockers, highest-leverage repairs, preserved strengths, and residual risk.
2. **Atomic ledger:** decision object, severity, confidence, evidence/verification state, concern, evidence, interpretation boundary, priority, disposition, repair, and preservation constraint.
3. **Implementation handoff when authorized:** changed paths, compatibility/schema impact, commands run, observed results, unexecuted checks, and deliverable hashes.
4. **Decision and preservation map:** what blocks beta, what stays default, what needs human calibration, what remains deliberately out of scope, and what would make this edition stale.

Do not pad a clean review with invented issues. A positive verdict is acceptable when the contradiction sweep, critical paths, and free pass are visible.

## Run Contract template

```md
Artifact(s) and version(s):
Immediate decision:
Role: auditor / measurement critic / release gate / patch planner / implementer
Mode: review / static inspection / execution / implementation / reconciliation
Coverage: full / risk-prioritized / sampled
Available access and platform:
Permitted actions:
Current phase:
Fluid objects:
Frozen/protected objects:
Required deliverable:
New constraints or prior reviews to reconcile:
```

## Tailoring audit result

This edition was checked against the active `0.2.x` charter, rule ledger, schema, limitations, architecture, release workflow, calibration scaffolding, the independent `0.2.0a2` Hopeful Skeptic review, and the independent `0.2.0a3` Fable review. Version `0.1.1` adds same-track comparison, provenance, replay, and accessibility safeguards while retaining its Calibrating status. It deliberately emphasizes interpretation integrity, privacy, output ownership, release truth, calibration, launcher honesty, and scope discipline.

Known limitations of this edition:

- it is not a DSP standards document;
- it cannot substitute for human musical calibration or native platform evidence;
- it may overfit if future releases shift from a static report product;
- it should be marked stale rather than patched informally when a freshness trigger occurs.

No Core invariant is intentionally weakened.
