# Independent Fable review of AudioAtlas 0.2.0a3

> Archived as external review input for the bounded 0.2.0a4 follow-up. It is evidence about the reviewer's executed environment, not an AudioAtlas project claim.

This is a well-put-together bundle, and I had enough here to do a real pass rather than an armchair one — I extracted the source snapshot, installed it, and executed checks rather than relying on the reports. Here's what I actually verified, a couple of small observations, and then the part you asked for: directions that aren't in the Grok review, the follow-up report, or the Project Edition's existing roadmap.

**What I executed and confirmed in this Linux sandbox (Python 3.12):**

- All nine SHA256 checksums verified OK.
- **Full test suite: 252 passed in a single uninterrupted run (106s).** Worth noting because your follow-up report honestly declined to claim this — its wrapper timed out on the monolithic run. You can now treat "252/252 in one cold invocation" as independently reproduced, which closes that small residual.
- Lightweight CLI claim holds: `--version` in 0.091s, `themes` in 0.095s, and importing `audioatlas.cli` pulled in none of librosa/scipy/matplotlib/soundfile/pyloudnorm.
- Generated a real report from a synthetic stereo WAV placed in a directory with spaces and parentheses. The report folder contained no trace of the local path — basename-only throughout, empty stderr, all expected artifacts present.
- Rule-behavior spot check: my file had PLR 4.785 dB (below the 8 dB eligibility) but no independent high-level signal, and correctly produced **zero findings** — the v2 `low_plr_with_level_pressure` gating behaves exactly as `FINDING_RULES.md` documents. That's a nice live confirmation that the false-authority fix survived the release.

Not verified here, consistent with your own residual list: native launcher behavior, mypy count, the bundled wheel specifically (I installed from source), and anything about musical calibration — that gate remains yours.

**Unique directions.** These are chosen to fit the protected scope (local, static, no scores, no classifiers, one-track-first) and to be feasible at this phase. Roughly in order of leverage:

1. **Same-track revision diff.** Your primary users iterate: mix v3 vs mix v4 of the *same* track. An `audioatlas diff <reportA> <reportB>` that emits purely descriptive deltas — true peak, LUFS, PLR, correlation, band-power shifts, and which findings appeared/disappeared — is arguably the single most useful thing missing, and it's one-track-first by construction. Guardrails matter: refuse or loudly label cross-track comparisons, deltas only, no "better/worse" language ever. This is a new command surface, so per your own Project Edition it's an owner product-direction call, not routine polish — but it's the first thing I'd bring to that decision. It also depends on #2.

2. **Comparability/provenance block in `summary.json`.** Record an analysis-config hash plus the decoder backend and key library versions (soundfile/libsndfile, librosa, pyloudnorm) at generation time. Right now two reports from different machines or releases can't be trusted as comparable, which quietly undermines the calibration record, any future diff feature, and the honesty of "approximate true peak" (whose approximation depends on the resampling path). Cheap, schema-additive, and it strengthens claims you already make.

3. **Calibration corpus replay.** `prepare_calibration_review.py` already exports hashed, anonymous rows. The natural companion is a replay tool: given the frozen corpus manifest, re-run a *candidate* ruleset and report prompt-level churn — which findings appear, vanish, or reword per corpus item. When the 0.3.0 alias/ruleset boundary arrives, every rule change becomes an evidence-backed diff against the calibration record instead of a judgment call. This turns your one-time listening gate into a durable regression asset.

4. **Property-based invariant tests.** Your fixtures are deterministic and your golden tests pin values, but nothing appears to pin *invariants*: PLR unchanged under constant gain (your own calibration-pack example!), stereo metrics symmetric under channel swap, silence and sub-second inputs degrading gracefully, DC-offset behavior. A small `hypothesis` suite with fixed seeds directly targets failure mode #1 ("valid number, invalid story") at the mechanism level and costs an afternoon.

5. **Malformed-file fixtures at the error boundary.** Error paths are where paths leak. A handful of committed truncated/corrupted WAV and FLAC headers, with tests asserting `AudioLoadError` output stays redacted and batch mode records the skip, converts your privacy guarantees from "tested on the happy path" to "tested where regressions actually happen."

6. **Measured-value alt text.** Each PNG in the HTML/Markdown reports could carry alt text stating what it shows and its actual range ("Short-term LUFS timeline, −14.2 to −8.1 LUFS"). It's accessibility, it deepens the inspectability you already claim as the differentiator, and it's zero scope risk.

One boundary note for honesty: #1 flirts with the scope ceiling if it ever drifts toward reference comparison, and #3 only pays off after the human listening gate you've correctly refused to fabricate. Nothing above should jump the queue ahead of that gate and the launcher rehearsal — these are directions to build *alongside or after* it, not substitutes for it.

If you'd like, I can sketch the schema shape for the provenance block or a starter set of hypothesis invariants against the actual implementation — those two are small enough to prototype right in this repo.