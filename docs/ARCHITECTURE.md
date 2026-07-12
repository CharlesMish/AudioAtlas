# AudioAtlas Architecture

AudioAtlas is a deterministic local pipeline: one decoded audio array enters,
pure analysis functions produce frozen result dataclasses, selected graph
adapters render PNGs, and static writers serialize a portable report bundle.
There is no server, plugin system, hidden state, or cloud dependency.

## Layer map

```text
cli.py
  ├── pipeline.py      ── one-track/section orchestration
  ├── batch.py         ── folder orchestration
  └── revision_diff.py ── guarded same-track report deltas
         ↓
io.py ── decoded audio + portable metadata
         ↓
analysis/*.py ── arrays → frozen result dataclasses
         ↓
graphs/registry.py + graphs/adapters.py
         ↓
visualize/*.py ── result dataclass → PNG
         ↓
provenance.py ── path-safe configuration/code/environment fingerprints
         ↓
report.py / html_report.py / catalog_report.py / alt_text.py
         ↓
output.py ── staged publication + ownership manifest

scripts/prepare_calibration_review.py
  └── scripts/replay_calibration_rules.py ── frozen-summary finding churn
```

## Layer rules

| Layer | Owns | Must not own |
|---|---|---|
| `io.py` | decoding, ranges, metadata privacy | DSP interpretation, plotting |
| `analysis/*` | pure measurements and JSON-safe summaries | paths, matplotlib, report prose |
| `graphs/*` | stable plot identity, profile membership, captions, adapters | DSP recomputation |
| `visualize/*` | rendering supplied results | decoding or analysis |
| `pipeline.py` | one coherent run and summary assembly | DSP math |
| `batch.py` | per-file isolation and catalog assembly | DSP math or ranking |
| `provenance.py` | canonical hashes, dependency/decoder/environment metadata, opaque identity digest | source paths, audio recognition, quality inference |
| `revision_diff.py` | same-track guard, comparability assessment, descriptive B-minus-A artifacts | audio analysis, cross-track ranking, preferred-version claims |
| `alt_text.py` | measured descriptions from existing summary values | analysis recomputation or musical inference |
| report writers | static presentation | new measurements or causal claims |
| `output.py` | staged publication and owned-artifact cleanup | analysis or interpretation |
| calibration scripts | anonymous review/replay evidence and hash verification | opening audio or replacing human listening |
| `cli.py` | arguments, lightweight discovery, and friendly user errors | business logic |

## CLI loading boundary

`audioatlas --version`, `--help`, and `themes` do not import the DSP, decoder,
or plotting stack. Analysis, batch, and section commands print a preparation
message and then import their heavy orchestration path. This improves startup
feedback and launcher checks without changing numerical behavior or replacing
the scientific dependencies. Graph-profile names live in the lightweight
`graph_profiles.py` module so command discovery does not initialize the graph
registry.

## Internal audio contract

`AudioData.y` always has shape `(n_samples, n_channels)` and dtype `float32`.
The loader never normalizes. User-supplied source ranges are represented in
metadata. Absolute local paths are excluded unless `include_local_paths=True`.

## Analysis bundle

`AnalysisBundle` lazily computes and memoizes named result blocks. Graph
selection affects rendering only; `pipeline.py` requests the full analysis set
before serialization. `band_energy` remains a deprecated request alias for
`band_power` during the alpha compatibility window.

## Graph registry

Each `GraphSpec` defines a stable key, display name, filename, render order,
required analysis blocks, profile membership, cost tier, caption, report note,
and summary link. The historical key/filename `band_energy_timeline` remains
stable, while its display language now states the actual relative mean-power
measurement.

## Safe publication

A run renders into a sibling temporary directory. Only after every writer and
plot succeeds does `output.py` publish the completed artifacts. It:

- replaces individual files with same-filesystem atomic operations;
- removes stale known AudioAtlas outputs absent from the new run, including
  obsolete root artifacts when a folder switches between single-report and
  catalog mode;
- preserves unrelated files;
- records owned files/directories in `.audioatlas-output.json`;
- removes prior batch-track directories only when both the parent catalog and
  child report carry recognized ownership evidence (or a narrow legacy catalog
  recovery rule applies);
- moves the previous generated set into a sibling recovery directory before
  publication and restores it if any individual file or directory update
  fails;
- leaves unrelated user files untouched throughout publication and rollback.

Each one-track analysis also runs inside a short lifecycle frame. After the
result or exception leaves that frame, `pipeline.py` explicitly collects
renderer/artist reference cycles. This prevents repeated in-process catalog
runs from retaining completed Matplotlib graphs and their analysis bundles.


## Scientific dependency boundary

Librosa uses Numba/llvmlite in analysis paths, so those transitive packages are
part of the executable measurement environment rather than incidental build
tools. AudioAtlas `0.2.0a5` promotes Numba into the direct dependency contract
and constrains it to `>=0.65.1,<0.66` after a clean Python 3.13 report stalled
and crashed with Numba 0.66.0 / llvmlite 0.48.0 but completed with Numba 0.65.1
/ llvmlite 0.47.0. Dependency versions are recorded in provenance; widening
this band requires a clean installed-wheel analysis smoke.

## Provenance and comparison boundary

Each one-track summary records a canonical analysis-config hash, measurement
code hash, finding-rule code hash, dependency/decoder versions, named method
details, and an environment block. `compatible_analysis_sha256` excludes the
platform block; `exact_environment_sha256` includes it. This lets comparison
code distinguish exact recorded environments from compatible measurement
implementations without claiming bit-identical numerics.

`--track-id` is normalized and hashed before serialization. The digest omits
plaintext but is not presented as a secret or an audio fingerprint. `revision_diff.py`
accepts matching non-null digests automatically, requires an explicit
`--confirm-same-track` assertion when identity is absent, and refuses conflicting
digests. It then refuses missing/different compatible provenance unless
`--allow-incomparable` is used. The resulting JSON, Markdown, and HTML preserve
that override and the reasons. Finding-rule code/ruleset identity is assessed
separately: scalar comparability may remain intact while prompt churn is labeled
as potentially caused by source and/or rule changes. No diff path opens audio or
produces a score.

## Calibration replay boundary

The human-review worksheet freezes a digest of `summary.json`, `findings.json`,
and the output manifest. Replay requires that ledger and the private anonymous
asset map, verifies every digest, and invokes the current finding rules on the
saved summary only. It records appeared/disappeared/changed/unchanged prompts.
Because measurements are not rerun, replay isolates finding-rule churn from DSP
or decoder changes; it does not validate the music or replace reviewer labels.

## Accessible plot descriptions

`alt_text.py` reads already-serialized summary values and emits bounded,
nonjudgmental plot descriptions such as a measured RMS or LUFS range. HTML and
Markdown use the same helper, and the HTML lightbox inherits the selected
image's alt text. The helper never imports analysis or plotting code.

## Adding a measurement slice

1. Add a frozen result dataclass and pure `compute_*` function.
2. Add synthetic positive, negative, silence/short-input, and counterexample
   tests.
3. Add a graph adapter/spec only when a visual map provides distinct value.
4. Add a summary field whose name matches the measurement.
5. Add report wording that states both supported and unsupported meaning.
6. Add or update schema documentation.
7. Add a default finding only when a stable rule ID, eligibility boundary,
   counterexamples, graph association, and calibration rationale exist.

## Serialized compatibility

Release, summary-schema, findings-schema, catalog-schema, and finding-ruleset
versions live in `src/audioatlas/release.py`. Precise new names are preferred;
temporary aliases are explicitly marked deprecated. Removing an alias or
changing a field type requires a schema decision and migration note.

## Product boundary

The architecture is intentionally optimized for static, inspectable reports.
Scores, automated mastering advice, classifiers, cross-track reference
ranking, hosted services, playback/DAW state, and a plugin platform are not
incremental feature slices; they would be product redesigns governed by
the public product boundary. Guarded descriptive comparison between user-asserted
revisions of one track is the narrow exception documented above.

## Public distribution and presentation

The stewardship checkout is the complete project record.
`scripts/export_public_tree.py` derives the friendly public tree by copying the
same tracked implementation while excluding internal review, private
calibration operations, and launcher-rehearsal records. This is a distribution
projection, not a fork.

Graph profiles remain rendering selection only. `compact` resolves to the same
four graph set as the legacy `minimal` name. Focus and Studio presentation are
implemented in `presentation.py` and injected into static HTML writers. They
change CSS and local interaction only; they do not enter the analysis
provenance signature or alter generated PNG pixels.
