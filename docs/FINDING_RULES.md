# AudioAtlas Finding Rule Ledger

**Ruleset:** `0.2.0a2`
**Status:** calibrating
**Implementation:** `src/audioatlas/analysis/findings.py`

A finding is a bounded review prompt. It is not proof of audibility, intent,
quality, causation, or a mastering defect. Every default rule below must survive
both trigger fixtures and counterexamples before beta.

## `levels.true_peak_above_zero` — v1

**Eligibility:** approximate true peak is greater than `0 dBTP`.
**Supported claim:** reconstructed peaks may exceed nominal full scale during
playback, conversion, or encoding.
**Does not establish:** audible distortion, source-master clipping, or an
incorrect limiter decision. Lossy files describe decoded audio only.
**Evidence views:** sample-peak timeline and waveform/RMS.
**Counterexamples to retain:** clean oversampled signals with a true-peak over;
lossy decoding that creates an over without source-master clipping.

## `levels.near_full_scale_samples` — v1

**Eligibility:** a material near-clipping count after suppression of tiny,
redundant counts. Severity depends on count and independent peak context.
**Supported claim:** decoded samples occur close to the configured ceiling.
**Does not establish:** clipping, audibility, or an undesirable passage.
**Evidence views:** sample-peak timeline, waveform/RMS, sample histogram.
**Counterexamples to retain:** a handful of isolated samples; intentional
full-scale transients; lossy decode overs.

## `levels.sample_clipping` — v1

**Eligibility:** one or more decoded samples meet the clipping threshold.
**Supported claim:** the analyzed decoded signal contains samples at the
configured ceiling.
**Does not establish:** the cause, source-master state, audibility, or whether
the result was intentional.
**Evidence views:** sample-peak timeline, waveform/RMS, sample histogram.
**Counterexamples to retain:** intentionally clipped/distorted material; lossy
files whose decoded samples do not reveal the source-master history.

## `dynamics.low_plr_with_level_pressure` — v2

**Eligibility:** `PLR < 8 dB` **and** at least one independent high-level signal:
true peak above `0 dBTP`, at least 100 near-clipping samples, or clipped samples.
**Supported claim:** the highest reconstructed peak is relatively close to
integrated loudness, alongside a separate high-level footprint.
**Does not establish:** compression amount, transient quality, dynamic range,
audibility, or a delivery problem. Loudness normalization applies the same gain
to peak and integrated loudness and therefore does not change PLR.
**Evidence views:** crest-factor, RMS, peak, and waveform/RMS timelines.
**Counterexamples to retain:** a low-PLR sine or drone without level pressure;
intentionally dense/distorted music; normalized copies with unchanged PLR.

## `stereo.low_correlation_or_side_heavy` — v1

**Eligibility:** sustained low/negative correlation and/or median side/mid ratio
above `-6 dB`, with brief-event and healthy-context suppression.
**Supported claim:** mono playback may change tone, level, width, or center focus
in the measured regions.
**Does not establish:** an incorrect stereo image or phase defect.
**Evidence views:** stereo-correlation and mid/side timelines.
**Counterexamples to retain:** brief panned effects; intentionally phase-rich
ambience; dual-mono; anti-phase synthetic fixtures.

## Deliberately non-triggering measurements

The following remain in summaries and plots but do not create default findings
without additional content-aware evidence:

- absolute spectral rolloff;
- strongest/highest broad frequency band;
- relative spectral-centroid movement;
- relative band-power movement;
- onset-density movement;
- dominant chroma pitch class.

AudioAtlas does not know whether a file contains vocals, cymbals, a full mix, a
stem, noise, a sine wave, or intentionally bandwidth-limited material. Those
measurements can guide inspection without licensing a musical story.

## Calibration record format

For each triggered rule on representative material, record one of:

- helpful;
- true but redundant;
- context-dependent;
- misleading;
- factually wrong.

A rule stays default only when its useful signal clearly exceeds its
false-authority cost. The owner-side calibration workflow is maintained in the stewardship branch.
