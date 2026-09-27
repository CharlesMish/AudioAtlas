# Evidence Range Index v0.1 — inventory and contract

The index lists existing range objects; it does not detect, retime, merge, rank,
or score evidence. All current summary ranges use legacy anchor geometry:
start = first active frame label; end = last active label + median positive hop.
These are not complete integration footprints. Source-frame support is separate.
Selected-source-range coordinates remain relative to the analyzed slice.

| Source key (summary unless stated) | Family/type | Support / reference | Graph |
|---|---|---|---|
| `peak_timeline.near_clipping_time_ranges` | frames containing samples at/above the existing near-clipping threshold | start-labeled N samples, final frame truncated; all-channel sample amplitude/full scale | peak_timeline |
| `spectral_shape.centroid_elevated_time_ranges` | above existing within-view centroid threshold | centered N-frame; arithmetic mono, Hz | spectral_shape |
| `spectral_shape.centroid_reduced_time_ranges` | below existing within-view threshold | same | spectral_shape |
| `spectral_shape.centroid_large_shift_time_ranges` | existing adjacent-frame centroid-change threshold | both preceding and labeled centered frames; mono, Hz | spectral_shape |
| `band_power_timeline.bands.*.elevated_time_ranges` | above each band's existing threshold | centered STFT; mono, independently normalized within analyzed view, relative dB | band_energy_timeline |
| `band_power_timeline.bands.*.reduced_time_ranges` | below each band's existing threshold | same | band_energy_timeline |
| `stereo_correlation.correlation_below_0_time_ranges` | negative frame correlation | start-labeled, right-padded N frame; Pearson r, channels 0/1 | stereo_correlation |
| `stereo_correlation.correlation_below_0_3_time_ranges` | frame correlation below 0.3 | same | stereo_correlation |
| `mid_side_energy.side_to_mid_ratio_above_minus_6_time_ranges` | existing side/mid threshold | start-labeled, right-padded N frame; channel-0/1 RMS ratio dB | mid_side_energy |
| `onset_density.high_onset_density_time_ranges` | above existing raw smoothed-activity threshold | shifted lagged mel frames + approximately 1 s smoothing; mono raw log-mel flux, global clipping reference; generator may bridge a hop | onset_density |
| `findings.all_findings[].time_ranges` | previously generated review-prompt ranges | preserve labels; potentially mixed source support, no inferred single footprint | existing associated graphs / findings section |
| `findings.all_findings[].evidence_items[].time_ranges` | original finding evidence ranges | preserve labels and metric identity; constituent support explicitly unspecified; follow the associated measurement for its support | associated graphs / findings section |

The seven current bands are sub, bass, low_mid, mid, presence, high, air. Exact
support depends on sample rate and configuration. Reference interpretation
boundaries come from `MeasurementReference`. No correlation/M/S value is a
perceived-width verdict; no relative-band value is absolute band level; no
centroid range is note pitch or an EQ instruction; onset is not event count.

## Exclusions and compatibility

- `band_energy_timeline`: deprecated duplicate alias; use only if the canonical
  block is absent. Do not count both as independent evidence.
- `findings` / `findings_shown`: duplicate presentation subsets when
  `all_findings` exists; use a historical fallback only if it is absent.
- Scalar clipping counts: no clipping-only ranges are currently emitted; do not
  derive any from counts or sample arrays. Peak near-clipping ranges above remain.
- RMS, crest, short-term LUFS, L/R balance, average spectrum, chroma, spectrogram:
  no existing range objects to index. Do not synthesize any from their timelines.
- Unknown range sources are not automatically promoted into the index.
- Malformed/nonfinite/negative/reversed or zero-duration legacy ranges are
  excluded with reasons in the internal index audit. Zero-duration labels do not
  establish an interval; no guessed duration is assigned.

## Product placement and presentation

Initial placement is full computation + full graph profile (Detailed), including
legacy commands with that same pair. Overview and Standard remain unchanged.
The report-writer override is for local presentation evaluation, not a new CLI
flag. Counts remain 4 / 14 / 18; this is a navigation section, not a plot.

Rows sort by exact start, end, then stable source key. Only exactly equal start
and end coordinates share a display row; every original source object, index,
duration, and label is retained internally and every source is shown. Near-equal
ranges remain separate. No new combined range or score is created.

Fixed 10-second *start-time navigation groups* are collapsed by default. Their
headings say “Starts …”; they are not detected sections or merged evidence.
Opening a group lists all rows chronologically. Exact duplicates are grouped
only for presentation. Numeric precision remains available in HTML details and
source JSON; display times are not used for equality or overlap calculations.

Overlap counts refer only to positive overlap of the original label intervals,
not expanded supports or simultaneous source events. Broad frames/windows can
contribute. No all-to-all semantic inference or transitive range merger occurs.
Support context uses `TimelineSupport` over memoized results when available;
historical summary-only rendering falls back to explicit support descriptions,
not reconstructed fake frame data. Graph links appear only for included plots;
otherwise the row links to report technical details. All functionality works
without JavaScript and uses existing theme tokens.
