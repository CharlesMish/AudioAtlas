# Output JSON schema

`summary.json` is the machine-readable output of every analysis run. It
is the canonical record of "what AudioAtlas measured on this file".
`findings.json` is the rule-based companion output derived from
`summary.json`; it does not add new DSP measurements.

Current schema version: **`0.1.0`**.

## Top-level shape

```jsonc
{
  "schema_version": "0.1.0",
  "metadata":        { ... AudioMetadata ... },
  "analysis_config": { ... AnalysisConfig ... },
  "levels":          { ... ScalarLevelsResult ... },
  "rms_envelope":    { ... RmsEnvelopeResult.to_summary_dict() ... },
  "peak_timeline":   { ... PeakTimelineResult.to_summary_dict() ... },
  "average_spectrum":{ ... AverageSpectrumResult.to_summary_dict() ... },
  "spectral_shape":  { ... SpectralShapeResult.to_summary_dict() ... },
  "band_energy_timeline": { ... BandEnergyTimelineResult.to_summary_dict() ... },
  "onset_density":   { ... OnsetDensityResult.to_summary_dict() ... },
  "stereo_correlation": { ... StereoCorrelationResult.to_summary_dict() ... },
  "mid_side_energy": { ... MidSideEnergyResult.to_summary_dict() ... },
  "plots":           ["01_waveform_rms.png", ...]
}
```

## findings.json shape

```jsonc
{
  "count": 1,
  "findings": [
    {
      "severity": "warning",
      "category": "levels",
      "title": "Near-full-scale samples detected",
      "measured_value": 12,
      "threshold": 0,
      "unit": "samples",
      "evidence": "near_clipping_samples measured 12.",
      "why_it_matters": "...",
      "suggested_checks": ["Inspect the sample histogram."],
      "time_ranges": [],
      "confidence": "high"
    }
  ]
}
```

Findings are factual observations derived from existing summary fields.
They are not mix scores, verdicts, mastering advice, or reference-track
comparisons.

## Blocks

### `metadata` (from `audioatlas.io.AudioMetadata`)

| Field | Type | Notes |
|---|---|---|
| `path` | string | Absolute path to input audio. |
| `filename` | string | Basename. |
| `samplerate` | int | Hz. |
| `channels` | int | 1 or 2 (or more, mostly untested). |
| `frames` | int | Sample count per channel. |
| `duration_seconds` | float | `frames / samplerate`. |
| `format` | string | libsndfile format, e.g. `"WAV"`. |
| `subtype` | string | e.g. `"PCM_16"`, `"FLOAT"`. |
| `endian` | string \| null | If applicable. |

### `analysis_config` (from `audioatlas.config.AnalysisConfig`)

Frozen dataclass, serialized via `dataclasses.asdict`. Includes
`n_fft`, `hop_length`, `window`, `db_floor`, `rms_frame_length`,
`clipping_threshold`, `near_clipping_threshold`, `true_peak_oversample`,
`welch_nperseg`, `max_plot_points`, `correlation_min_rms_dbfs`,
`onset_density_window_seconds`.

### `levels` (from `audioatlas.analysis.levels.ScalarLevelsResult`)

All `*_dbfs` and `*_dbtp` fields are clamped to `analysis_config.db_floor` at the low end. They are not clamped at 0 dB: float WAV files or decoded material can contain values above nominal full scale.

| Field | Type | Unit / range |
|---|---|---|
| `duration_seconds` | float | s |
| `sample_rate` | int | Hz |
| `channels` | int | |
| `sample_peak_linear` | float | 0.0 - ~1.0+ |
| `sample_peak_dbfs` | float | dBFS. Usually ≤ 0 for integer PCM; may exceed 0 for float/over-full-scale input. |
| `true_peak_linear` | float \| null | Linear true peak after polyphase upsampling. |
| `true_peak_dbtp` | float \| null | dBTP. Usually ≤ 0 for integer PCM; may exceed 0 for float/over-full-scale input. |
| `rms_linear` | float | 0.0 - 1.0 |
| `rms_dbfs` | float | dBFS |
| `crest_factor_db` | float \| null | dB. `null` for true silence. |
| `integrated_lufs` | float \| null | LUFS. `null` if file < ~400 ms or pyloudnorm missing. |
| `plr_db` | float \| null | True peak - integrated LUFS, dB. |
| `clipped_samples` | int | Count of samples with `|x| >= clipping_threshold`. |
| `clipped_percent` | float | `100 * clipped_samples / total_values`. |
| `near_clipping_samples` | int | Count of samples with `|x| >= near_clipping_threshold`. |
| `near_clipping_percent` | float | |
| `dc_offset_per_channel` | list[float] | Mean per channel. |
| `peak_dbfs_per_channel` | list[float] | |
| `rms_dbfs_per_channel` | list[float] | |
| `true_peak_linear_per_channel` | list[float] \| null | Per-channel true-peak (linear). Follows the same null rule as `true_peak_linear`. |
| `true_peak_dbtp_per_channel` | list[float] \| null | Per-channel true-peak in dBTP, clamped to `db_floor`. Same null rule as `true_peak_dbtp`. |
| `warnings` | list[str] | Human-readable caveats; safe to ignore programmatically. |

### `rms_envelope` (from `RmsEnvelopeResult.to_summary_dict`)

| Field | Type | Notes |
|---|---|---|
| `frame_length` | int | Samples per RMS window. |
| `hop_length` | int | Hop between RMS windows. |
| `frames` | int | Number of RMS values produced. |
| `rms_dbfs_min` | float \| null | dBFS, floored to `db_floor`. |
| `rms_dbfs_max` | float \| null | dBFS. |
| `rms_dbfs_mean` | float \| null | dBFS. |

### `average_spectrum` (from `AverageSpectrumResult.to_summary_dict`)

| Field | Type | Notes |
|---|---|---|
| `nperseg` | int | Welch segment length used. |
| `bins` | int | Number of frequency bins. |
| `strongest_bin_hz` | float | Only present if any bin ≥ 20 Hz exists. |
| `strongest_bin_db` | float | Relative power in dB of the strongest displayed bin. This is `0.0` by definition for non-silent spectra because the spectrum is normalized to the strongest bin at or above 20 Hz. |
| `band_energies` | object | Named band energy summaries derived from the same relative Welch average spectrum. |
| `strongest_band` | string \| null | Band with highest relative band energy, if available. |

Band names:

| Band | Range |
|---|---|
| `sub` | 20-60 Hz |
| `bass` | 60-120 Hz |
| `low_mid` | 120-350 Hz |
| `mid` | 350-2000 Hz |
| `presence` | 2000-5000 Hz |
| `high` | 5000-10000 Hz |
| `air` | 10000-20000 Hz, capped by Nyquist |

Each `band_energies.<band>` object contains:

| Field | Type | Notes |
|---|---|---|
| `low_hz` | float | Band lower edge. |
| `high_hz` | float | Band upper edge, capped by Nyquist. |
| `energy_db` | float \| null | Mean relative Welch power in the band, in dB relative to the strongest displayed spectrum bin. |

### `peak_timeline` (from `PeakTimelineResult.to_summary_dict`)

Frame-wise clipping and near-clipping sample counts. This reuses
`analysis_config.n_fft`, `analysis_config.hop_length`,
`analysis_config.clipping_threshold`, and
`analysis_config.near_clipping_threshold`.

| Field | Type | Notes |
|---|---|---|
| `frame_length` | int | Samples per peak-count window. |
| `hop_length` | int | Hop between windows. |
| `frames` | int | Number of frames. |
| `clipping_threshold` | float | Absolute sample threshold for clipped counts. |
| `near_clipping_threshold` | float | Absolute sample threshold for near-clipping counts. |
| `times_seconds` | list[float] | Frame start times. |
| `clipped_counts` | list[int] | Frame-wise count of sample values at or above `clipping_threshold`. |
| `near_clipping_counts` | list[int] | Frame-wise count of sample values at or above `near_clipping_threshold`. |
| `clipped_samples_in_frames` | int | Sum of frame-wise clipped counts. Overlapping windows can count the same sample more than once. |
| `near_clipping_samples_in_frames` | int | Sum of frame-wise near-clipping counts. Overlapping windows can count the same sample more than once. |
| `frames_with_near_clipping` | int | Number of frames where `near_clipping_counts > 0`. |
| `near_clipping_time_ranges` | list[object] | Contiguous frame ranges where near-clipping counts are nonzero. |

### `spectral_shape` (from `SpectralShapeResult.to_summary_dict`)

Time-varying spectral centroid, rolloff, and bandwidth measurements from
a mono channel average. Spectral centroid is a frequency-distribution
statistic, not a definitive brightness measurement. Silent frames are
represented as undefined and excluded from summary statistics.

| Field | Type | Notes |
|---|---|---|
| `n_fft` | int | FFT size used. |
| `hop_length` | int | Hop between frames. |
| `frames` | int | Number of spectral-shape frames. |
| `valid_frames` | int | Non-silent frames included in summary statistics. |
| `undefined_frames` | int | Silent frames excluded from summary statistics. |
| `centroid_mean_hz` | float \| null | Mean spectral centroid over valid frames. |
| `centroid_median_hz` | float \| null | Median spectral centroid over valid frames. |
| `centroid_min_hz` | float \| null | Minimum spectral centroid over valid frames. |
| `centroid_max_hz` | float \| null | Maximum spectral centroid over valid frames. |
| `rolloff_85_median_hz` | float \| null | Median 85% spectral rolloff over valid frames. |
| `rolloff_95_median_hz` | float \| null | Median 95% spectral rolloff over valid frames. |
| `bandwidth_median_hz` | float \| null | Median spectral bandwidth over valid frames. |
| `centroid_elevated_threshold_hz` | float \| absent | Relative heuristic threshold: median + max(1000 Hz, 0.5 * median). |
| `centroid_reduced_threshold_hz` | float \| absent | Relative heuristic threshold: median - max(1000 Hz, 0.5 * median), floored at 0 Hz. |
| `centroid_large_shift_threshold_hz` | float \| absent | Relative heuristic threshold: max(2000 Hz, 0.75 * median). |
| `centroid_elevated_time_ranges` | list[object] | Ranges where centroid is above the elevated threshold. |
| `centroid_reduced_time_ranges` | list[object] | Ranges where centroid is below the reduced threshold. |
| `centroid_large_shift_time_ranges` | list[object] | Ranges where adjacent-frame centroid change exceeds the large-shift threshold. |
| `warnings` | list[str] | Human-readable caveats; safe to ignore programmatically. |

### `band_energy_timeline` (from `BandEnergyTimelineResult.to_summary_dict`)

Frame-wise relative energy in the same broad bands used by
`average_spectrum.band_energies`. Values are relative dB within this
timeline analysis and are not calibrated dBFS. Silent frames are
undefined and excluded from summary statistics.

| Field | Type | Notes |
|---|---|---|
| `n_fft` | int | FFT size used. |
| `hop_length` | int | Hop between frames. |
| `frames` | int | Number of band-energy frames. |
| `valid_frames` | int | Non-silent frames included in summary statistics. |
| `undefined_frames` | int | Silent frames excluded from summary statistics. |
| `band_names` | list[string] | Band order used in arrays/visualization. |
| `bands` | object | Per-band statistics and time ranges. |
| `strongest_band_by_median` | string \| null | Band with highest median relative frame energy. |
| `warnings` | list[str] | Human-readable caveats; safe to ignore programmatically. |

Each `bands.<band>` object contains:

| Field | Type | Notes |
|---|---|---|
| `median_db` | float \| null | Median relative band energy over valid frames. |
| `mean_db` | float \| null | Mean relative band energy over valid frames. |
| `max_db` | float \| null | Maximum relative band energy over valid frames. |
| `min_db` | float \| null | Minimum relative band energy over valid frames. |
| `elevated_threshold_db` | float \| null | Relative heuristic threshold: band median + 6 dB. |
| `reduced_threshold_db` | float \| null | Relative heuristic threshold: band median - 12 dB. |
| `elevated_time_ranges` | list[object] | Ranges where frame band energy is above `elevated_threshold_db`. |
| `reduced_time_ranges` | list[object] | Ranges where frame band energy is below `reduced_threshold_db`. |

### `onset_density` (from `OnsetDensityResult.to_summary_dict`)

Onset-strength based transient-density timeline from a mono channel
average. This is a measurement of onset-envelope activity, not a
definitive measure of punch, transient quality, or performance quality.
`normalized_onset_strength` is kept in the in-memory result for plotting;
summary density values use raw librosa onset-strength units.

| Field | Type | Notes |
|---|---|---|
| `hop_length` | int | Hop between onset frames. |
| `frames` | int | Number of onset-density frames. |
| `smoothing_window_seconds` | float | Requested smoothing window duration. |
| `smoothing_window_frames` | int | Smoothing window in frames after converting from seconds. |
| `onset_strength_mean` | float \| absent | Mean raw librosa onset strength. |
| `onset_strength_median` | float \| absent | Median raw librosa onset strength. |
| `onset_strength_max` | float \| absent | Maximum raw librosa onset strength. |
| `onset_density_mean` | float \| absent | Mean smoothed onset strength. |
| `onset_density_median` | float \| absent | Median smoothed onset strength. |
| `onset_density_max` | float \| absent | Maximum smoothed onset strength. |
| `high_onset_density_threshold` | float \| absent | Relative heuristic threshold: median + max(0.15, 0.5 * median). |
| `high_onset_density_time_ranges` | list[object] \| absent | Ranges where smoothed onset density is above the relative threshold. |
| `strongest_onset_density_time` | float \| absent | Time of the maximum smoothed onset-density frame. |
| `warnings` | list[str] | Human-readable caveats; safe to ignore programmatically. |

### `stereo_correlation` (from `StereoCorrelationResult.to_summary_dict`)

Per-frame Pearson correlation between input channels 0 and 1. Mono input
is reported as `+1.0` by convention with a warning. For stereo
zero-variance frames or frames below `analysis_config.correlation_min_rms_dbfs`,
the in-memory timeline uses `NaN`; summary statistics exclude those
undefined frames. For inputs with more than two channels, only channels 0
and 1 are used.

| Field | Type | Notes |
|---|---|---|
| `frame_length` | int | Samples per correlation window. |
| `hop_length` | int | Hop between correlation windows. |
| `frames` | int | Number of correlation values produced. |
| `defined_frames` | int | Frames included in summary statistics. |
| `undefined_frames` | int | Zero-variance or below-threshold frames excluded from summary statistics. |
| `correlation_min` | float \| null \| absent | Minimum Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `correlation_max` | float \| null \| absent | Maximum Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `correlation_mean` | float \| null \| absent | Mean Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `correlation_median` | float \| null \| absent | Median Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `overall_correlation` | float \| null \| absent | Pearson r over the full left/right channel arrays. `null` when the full-channel value is undefined; absent when `frames` is 0. |
| `warnings` | list[str] | Human-readable caveats; safe to ignore programmatically. |
| `correlation_below_0_time_ranges` | list[object] | Contiguous frame ranges where defined L/R correlation is below 0.0. |
| `correlation_below_0_3_time_ranges` | list[object] | Contiguous frame ranges where defined L/R correlation is below 0.3. |

### `mid_side_energy` (from `MidSideEnergyResult.to_summary_dict`)

Frame-wise RMS for mid and side signals. For stereo input, mid is
`(L + R) / 2` and side is `(L - R) / 2`. For mono input, mid is the
mono signal and side is zero by convention with a warning.

| Field | Type | Notes |
|---|---|---|
| `frame_length` | int | Samples per mid/side RMS window. |
| `hop_length` | int | Hop between mid/side RMS windows. |
| `frames` | int | Number of mid/side RMS values produced. |
| `mid_rms_dbfs_min` | float \| null | Minimum mid RMS in dBFS, floored to `db_floor`. |
| `mid_rms_dbfs_max` | float \| null | Maximum mid RMS in dBFS. |
| `mid_rms_dbfs_mean` | float \| null | Mean mid RMS in dBFS. |
| `side_rms_dbfs_min` | float \| null | Minimum side RMS in dBFS, floored to `db_floor`. |
| `side_rms_dbfs_max` | float \| null | Maximum side RMS in dBFS. |
| `side_rms_dbfs_mean` | float \| null | Mean side RMS in dBFS. |
| `side_to_mid_ratio_db_median` | float \| null | Median `20 * log10(side_rms / mid_rms)` over frames with nonzero mid energy. |
| `side_to_mid_ratio_db_mean` | float \| null | Mean side/mid ratio over frames with nonzero mid energy. |
| `undefined_ratio_frames` | int | Frames where side/mid ratio is undefined because mid RMS is zero. |
| `side_to_mid_ratio_above_minus_6_time_ranges` | list[object] | Contiguous frame ranges where side-to-mid ratio is above -6 dB. |
| `warnings` | list[str] | Human-readable caveats; safe to ignore programmatically. |

### `plots`

Ordered list of plot filenames written to the same output directory. The
order is fixed:

```
01_waveform_rms.png
02_rms_timeline.png
03_log_spectrogram.png
04_average_spectrum.png
05_sample_histogram.png
06_stereo_correlation.png
07_mid_side_energy.png
08_spectral_shape.png
09_band_energy_timeline.png
10_onset_density.png
```

New plots from future feature slices append numbered prefixes (`11_*`,
`12_*`, ...) and are added to `plot_paths` in `pipeline.py`.

## findings.json blocks

### `Finding`

| Field | Type | Notes |
|---|---|---|
| `severity` | `"info"` \| `"warning"` \| `"issue"` | Rule severity. Not a mix-quality score. |
| `category` | `"levels"` \| `"dynamics"` \| `"stereo"` \| `"spectrum"` \| `"metadata"` | Measurement area. |
| `title` | string | Short factual label. |
| `measured_value` | float \| int | Summary value that triggered the finding. |
| `threshold` | float \| int | Rule threshold. |
| `unit` | string | Unit for `measured_value` and/or threshold. |
| `evidence` | string | Summary field and value behind the finding. |
| `why_it_matters` | string | Factual context, not advice or a verdict. |
| `suggested_checks` | list[string] | Manual checks to consider. These are not fixes. |
| `time_ranges` | list[object] | Optional time ranges with `start`, `end`, and `duration` in seconds. |
| `confidence` | `"low"` \| `"medium"` \| `"high"` | Confidence in the rule based on available measured evidence. |

## Example

A full example from a synthetic 1 kHz / -6 dBFS sine appears as the
golden fixture in `tests/fixtures/sine_1k_-6dbfs_2s.wav`. Run:

```bash
audioatlas analyze tests/fixtures/sine_1k_-6dbfs_2s.wav --out /tmp/aa_demo
cat /tmp/aa_demo/summary.json
```

## Per-channel field convention

Any global scalar metric that has a meaningful per-channel breakdown is
exposed as a matching `*_per_channel` field whose value is a list in
input channel order. When the global value is `null` (e.g. true-peak on
audio shorter than the polyphase upsampler can handle), the matching
per-channel field is `null` too. Agents adding new metrics should follow
this convention rather than emitting only the global scalar — the
per-channel breakdown is often the most useful part of the measurement.

## Backward compatibility rules

- Adding a new top-level block is **not** a breaking change. Don't bump.
- Adding a new field inside an existing block is **not** breaking. Don't bump.
- Renaming, removing, or retyping any documented field **is** breaking.
  Bump `schema_version`, update this file, and update
  `docs/CHANGELOG.md` in the same commit.
