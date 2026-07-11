# AudioAtlas Architecture

AudioAtlas is a deterministic local pipeline: one decoded audio array enters,
pure analysis functions produce frozen result dataclasses, selected graph
adapters render PNGs, and static writers serialize a portable report bundle.
There is no server, plugin system, hidden state, or cloud dependency.

## Layer map

```text
cli.py
  ├── pipeline.py ── one-track/section orchestration
  └── batch.py    ── folder orchestration
         ↓
io.py ── decoded audio + portable metadata
         ↓
analysis/*.py ── arrays → frozen result dataclasses
         ↓
graphs/registry.py + graphs/adapters.py
         ↓
visualize/*.py ── result dataclass → PNG
         ↓
report.py / html_report.py / catalog_report.py
         ↓
output.py ── staged publication + ownership manifest
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
| report writers | static presentation | new measurements or causal claims |
| `output.py` | staged publication and owned-artifact cleanup | analysis or interpretation |
| `cli.py` | arguments and friendly user errors | business logic |

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
Scores, automated mastering advice, classifiers, reference ranking, hosted
services, playback/DAW state, and a plugin platform are not incremental feature
slices; they would be product redesigns governed by `PROJECT_CHARTER.md`.
