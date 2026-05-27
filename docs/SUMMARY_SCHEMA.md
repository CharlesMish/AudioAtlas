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
  "average_spectrum":{ ... AverageSpectrumResult.to_summary_dict() ... },
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
`welch_nperseg`, `max_plot_points`, `correlation_min_rms_dbfs`.

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
```

New plots from future feature slices append numbered prefixes (`08_*`,
`09_*`, ...) and are added to `plot_paths` in `pipeline.py`.

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
| `time_ranges` | list[object] | Optional time ranges. Empty for first-pass scalar rules. |
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
