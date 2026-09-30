# Internal evidence alignment v0.1

This is an internal adapter contract, not a finding, score, public timeline
schema, or new report view. Existing timestamps and numbers retain their meaning.

## Sample footprints and context

`TimelineSupport` records half-open nominal and clipped decoded-sample intervals,
anchor, padding, hop, frame size, and dependency context. Bounds enclose the
window; Hann endpoints may carry zero weight. They are not localization precision.
All coordinates refer to the analyzed slice. Add its recorded source start only
when displaying original-file coordinates; analysis/filtering starts at the slice.

| Family | Public anchor | Nominal integration footprint (sample index i) | Edge behavior |
|---|---|---|---|
| RMS / crest | centered sample iH | [iH-floor(N/2), iH-floor(N/2)+N) | zero padding |
| Spectral shape / band power / spectrogram | centered sample iH | same, N = n_fft | centered zero-padded STFT |
| Peaks | start iH | [iH, iH+N) | truncated last frame |
| Correlation / M/S | start iH | [iH, iH+N) | right-zero padding |
| L/R balance | (iH+N/2)/sr | [iH, iH+N) | complete frames only |
| Short-term LUFS | window end, clipped at duration | pyloudnorm integer block endpoints | rounded last block may truncate; denominator stays nominal |
| Smoothed onset | shifted flux label iH | union of lag-1 mel frames contributing to the moving mean | mel/STFT, leading flux, and smoothing zero padding |

Defaults: FFT/RMS frame 4096, hop 1024; short-term LUFS 3 seconds/0.1 second;
onset smoothing approximately 1 second (rounded and capped to available frames).
Odd frame sizes have unequal before/after sample extents. LUFS endpoints follow
the meter's multiplication order; a clipped last label cannot reconstruct the
start by subtracting the window duration.

Footprints are separate from broader dependencies: K-weighting is causal IIR
filtering and includes the earlier slice prefix. Band power and spectrogram
have whole-view references. Onset uses globally clipped log-mel values before
flux and smoothing. `dependency_intervals_seconds()` refuses a local bound for
an analysis-wide reference. Do not describe overlap as independence or causation.
Chroma has variable-frequency CQT kernels, resampling and tuning context. No
single fixed scalar support is asserted for it; neither chroma nor spectrogram
is flattened into a scalar evidence lane.

## References

`MeasurementReference` retains unit, reference identity, normalization, channel
basis, and interpretation boundary. Identities distinguish decoded full scale,
amplitude ratio, K-weighted loudness, dimensionless correlation, frequency,
within-analysis relative power, raw log-mel flux, and within-frame normalization.
Same unit text alone is insufficient for comparisons. In particular, relative
dB values from different analyzed views do not establish source-level change.
The existing per-view relative numbers are preserved; no absolute spectral-band
estimator or new revision-diff field is introduced here.

## Evidence lanes and grid

`AnalysisBundle.computed_results` provides a read-only snapshot of its cache;
`evidence_lanes` never calls `get`. Thus adapting Overview cannot restore skipped
families. Lanes copy existing scalar timelines, retain unit/reference/channel
basis, source identity, valid mask and reason codes, support and caveats.
RMS, sample peak, crest, short-term LUFS, correlation, M/S ratio, L/R balance,
centroid, each relative band-power series, and smoothed onset can be adapted.
Legacy finite floor values and mono conventions are retained and noted, not
reclassified as physical zero or accurate measurements below the floor.

`aligned_cells` yields sparse indices into original lanes whose integration
footprints intersect each half-open grid interval. It does not synthesize a
value, interpolate through a gap, count evidence, or rank cells. A 3-second
LUFS window can occur in several cells but remains the same original frame
with its 3-second support. Whole-view references and filter history remain
separate from the integration footprint. Memory is linear in lane frames plus
the current cell; callers who collect every cell pay for repeated indices.

The spectral warning floor is the existing numerical validity rule, not a new
dBFS gate: spectral shape uses mono frame RMS > `EPS`; band power uses summed
STFT frame power > `EPS` and also requires an available band/reference. These
are different tests with different units. The wording deliberately does not
infer anti-phase, cancellation, or physical source silence from either test.

Changing warning text in a measurement module changes its existing code
fingerprint. Old reports remain readable; strict cross-version revision
comparison may require the existing explicit comparability override. No code
hash is suppressed to claim automatic equivalence with older implementations.
