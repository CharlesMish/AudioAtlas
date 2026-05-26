# summary.json schema

`summary.json` is the machine-readable output of every analysis run. It
is the canonical record of "what AudioAtlas measured on this file".

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
  "plots":           ["01_waveform_rms.png", ...]
}
```

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
`welch_nperseg`, `max_plot_points`.

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
| `strongest_bin_db` | float | Power in dB of the strongest bin. |

### `stereo_correlation` (from `StereoCorrelationResult.to_summary_dict`)

Per-frame Pearson correlation between input channels 0 and 1. Mono input
is reported as `+1.0` by convention with a warning. For stereo
zero-variance frames, the in-memory timeline uses `NaN`; summary
statistics exclude those undefined frames. For inputs with more than two
channels, only channels 0 and 1 are used.

| Field | Type | Notes |
|---|---|---|
| `frame_length` | int | Samples per correlation window. |
| `hop_length` | int | Hop between correlation windows. |
| `frames` | int | Number of correlation values produced. |
| `defined_frames` | int | Frames included in summary statistics. |
| `undefined_frames` | int | Zero-variance frames excluded from summary statistics. |
| `correlation_min` | float \| null \| absent | Minimum Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `correlation_max` | float \| null \| absent | Maximum Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `correlation_mean` | float \| null \| absent | Mean Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `correlation_median` | float \| null \| absent | Median Pearson r over defined frames. `null` when no frames are defined; absent when `frames` is 0. |
| `overall_correlation` | float \| null \| absent | Pearson r over the full left/right channel arrays. `null` when the full-channel value is undefined; absent when `frames` is 0. |
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
```

New plots from future feature slices append numbered prefixes (`07_*`,
`08_*`, ...) and are added to `plot_paths` in `pipeline.py`.

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
