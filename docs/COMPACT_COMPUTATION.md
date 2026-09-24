# Compact computation

`--analysis-mode full` remains the default for analyze, batch and sections.
`--analysis-mode compact` explicitly requests a narrower computation plan for
a normal human-facing report. It is not the proposed snapshot/instant API.

```sh
audioatlas analyze song.wav --out reports/compact --analysis-mode compact
audioatlas analyze song.wav --out reports/chroma --analysis-mode compact --enable chroma_cqt
audioatlas batch songs --out reports/catalog --analysis-mode compact
audioatlas sections song.wav --out reports/sections --section verse:30:62 --analysis-mode compact
```

Graph profiles (`compact`, its equivalent `minimal`, `standard`, `full`) still
select presentation. `--graphs-profile compact` alone performs full analysis.
Compact computation defaults to the four-plot `compact` profile only when no
explicit profile exists. CLI profile overrides YAML profile, which overrides
the mode's default. Enable/disable selections apply afterward.

| Family | Default compact | Contract |
|---|---|---|
| levels, rms, peaks | computed | Existing full-fidelity levels and frame measurements |
| stereo, mid_side | computed | Existing stereo metrics and localized finding inputs |
| spectral_shape | computed | Retained section/catalog spectral summaries |
| spectrogram | computed | Required by the default four-plot selection |
| crest, short_term, average_spectrum, band_power, onset, chroma, lr_balance | skipped | Restored by any selected graph requiring them |

All current finding rules retain their complete inputs (levels, peak ranges,
stereo and mid/side, plus unchanged metadata/configuration). Their content,
thresholds, severity, suppression and ordering are unchanged. Graph suggestions
can refer to optional graphs not rendered, just as with existing graph profiles.
There is no reduction in resolution, duration, channel fidelity or true-peak
oversampling, and no streaming/chunked DSP change.

The plan is measured through the existing memoizing `AnalysisBundle`; graph
adapters reuse the same objects. Standard graph selections restore the older
optional families but leave L/R balance skipped; full graph selections restore
all families. A skipped block is absent, never zero.
A computed but undefined measurement retains its existing null/warning semantics.

## Contracts reconciled from the older prototype

The prototype authority was `e3ad9a221cb4cb861a31a4475e14c728a131c946`.
This port starts at `879c57358e307b7da7696daecc57de1562acf97b`.
Its patch was inspected as a reference, not applied to the modern source.

- Full summaries use `0.4.0`, including L/R RMS balance and execution coverage.
- Compact summaries use `0.4.0`, including when all optional graphs are restored.
- L/R RMS balance is skipped by default in compact; explicitly enabling `lr_balance` restores it once.
- Findings stay `0.2.0`; compact findings add execution coverage, without changing rules.
- Catalogs stay `0.2.0` with additive per-track coverage and mixed-coverage counts.
- Canonical `band_power_timeline` and deprecated `band_energy_timeline` appear
  together only when that family is computed; mean-power semantics are retained.
- Full and compact share measurement/configuration/environment fingerprints
  within one implementation. The new family changes fingerprints from the prior
  implementation; exact old-family parity is established separately by tests. Compact
  provenance records the compact summary schema; execution coverage describes
  breadth. Revision deltas already leave absent operands/deltas null.
- Batch and sections propagate the mode without bypassing output transactions,
  source binding, cancellation or stale owned-artifact cleanup.
- Catalog patterns with optional spectrum inputs use defined measured tracks as
  their denominator, explicitly retaining the folder total. Onset statistics
  count only actual numeric values. Skipped values display as not computed.
- Public snapshot regeneration follows a clean content commit and is committed
  separately. No historical schema constants or launchers were copied verbatim.

## Native integration deferred

The current macOS app has one Choose Audio File/Analyze Another flow and no
Compact/Minimal action. `app_core.analyze_for_app` explicitly selects Standard
graphs and keeps default full computation. A later bounded UI change could add
an explicit computation choice, carry it through the controller request and
`app_core`, and select the four-plot profile for compact. Merely passing compact
mode alongside the app's current Standard profile restores the older optional
computations, while L/R balance stays skipped.
No native UI or default policy is changed here.

## Reproducible timing

```sh
uv run --locked --extra dev python scripts/benchmark_compact.py \
  examples/demo_audio/audioatlas_demo.wav --out /tmp/new-compact-benchmark
```

The script measures new-process totals (including imports), warm pipeline
totals, actual per-family compute time and plot-render time. It asserts exact
retained measurement/provenance/finding parity for every pair. Both modes use
the same source, default DSP settings and four graphs. Process-cold does not
mean a flushed disk, OS or Numba cache. The older Linux speedup is not a Mac
performance guarantee.
