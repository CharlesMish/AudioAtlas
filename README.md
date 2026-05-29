# AudioAtlas

AudioAtlas is a local, single-track "song microscope" for music
production, mixing, mastering, and deep listening.

It analyzes one audio file and produces factual visual maps and
metering-style measurements. It does **not** try to be an automated
mastering engineer, and it deliberately avoids fake mix-health scores.

## Status

Pre-v0.1 framework, intentionally small. Designed to be extended one
"feature slice" at a time. Most extension work is meant to be done by
agentic coding tools (Codex / GrokBuild) following the brief at
`AGENT_BRIEF.md`.

## What ships today

- Python package skeleton under `src/audioatlas/`
- CLI: `audioatlas analyze song.wav --out reports/song`
- WAV/FLAC/OGG loading via `soundfile`, internal shape
  `(n_samples, n_channels)`, no auto-normalization
- Scalar level metrics (sample peak, true peak approx., RMS, crest
  factor, integrated LUFS, PLR, clipping & near-clipping counts,
  per-channel breakdowns, DC offset)
- RMS dBFS timeline
- Log-frequency STFT spectrogram
- Welch average power spectrum
- Sample histogram
- `summary.json`, `findings.json`, `report.md`, and static `report.html`
- 39 unit / integration / golden tests covering DSP assumptions,
  utilities, report rendering, and an end-to-end pipeline run

## Repo tour

```
audioatlas/
├── AGENT_BRIEF.md            ← read first if you're an agent
├── README.md
├── Makefile                  ← `make test`, `make check`, `make demo`
├── pyproject.toml
├── docs/
│   ├── ARCHITECTURE.md       ← layering rules, where code goes
│   ├── SUMMARY_SCHEMA.md     ← the summary.json contract
│   ├── AGENT_TASKS.md        ← prioritized backlog with acceptance criteria
│   ├── AGENT_START_PROMPT.md ← suggested first prompt for Codex/Grok Build
│   └── CHANGELOG.md
├── src/audioatlas/
│   ├── __init__.py
│   ├── __main__.py           ← supports `python -m audioatlas ...`
│   ├── cli.py                ← thin click entry point
│   ├── pipeline.py           ← thin orchestrator
│   ├── config.py             ← AnalysisConfig dataclass
│   ├── utils.py
│   ├── io.py                 ← audio loading + metadata
│   ├── report.py             ← Markdown + JSON writers
│   ├── analysis/
│   │   ├── levels.py
│   │   ├── spectral.py
│   │   ├── stereo.py            (v0.2 stub)
│   │   ├── spectral_features.py (v0.2 stub)
│   │   └── tonal.py             (v0.2 stub)
│   └── visualize/
│       ├── waveform.py
│       ├── spectrogram.py
│       ├── spectrum.py
│       └── histogram.py
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── _build_golden.py
    │   ├── sine_1k_-6dbfs_2s.wav
    │   └── sine_1k_-6dbfs_2s.expected.json
    ├── test_io.py
    ├── test_levels.py
    ├── test_spectral.py
    ├── test_utils.py
    ├── test_report.py
    ├── test_pipeline.py
    └── test_golden.py
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
audioatlas analyze /path/to/song.wav --out reports/song
audioatlas batch /path/to/folder --out reports/catalog
# or, from a source checkout without install:
python -m audioatlas analyze /path/to/song.wav --out reports/song
python -m audioatlas batch /path/to/folder --out reports/catalog
```

CLI flags:

| Flag | Default | Meaning |
|---|---|---|
| `--out PATH` | required | Output directory. |
| `--max-duration FLOAT` | none | Truncate input for quick dev runs. |
| `--n-fft INT` | 4096 | FFT size for spectrogram. |
| `--hop-length INT` | 1024 | Hop size for time-axis analyses. |
| `--rms-frame-length INT` | = `--n-fft` | RMS window length. |
| `--db-floor FLOAT` | -100 | Floor for all dBFS / dBTP / dB metrics. |
| `--true-peak-oversample INT` | 4 | Polyphase factor; 1 disables. |

## Output

```
reports/song/
├── summary.json
├── findings.json
├── report.md
├── report.html
├── 01_waveform_rms.png
├── 02_rms_timeline.png
├── 03_log_spectrogram.png
├── 04_average_spectrum.png
├── 05_sample_histogram.png
└── ...
```

`summary.json`'s schema is documented in `docs/SUMMARY_SCHEMA.md`.
`report.html` is a static local file with embedded CSS and relative links
to the PNG plots in the same output folder.

Batch mode analyzes supported audio files in a folder (`.wav` and `.mp3`
currently), writes the normal per-track report folders, and adds:

```
reports/catalog/
├── catalog_summary.json
├── catalog.md
├── catalog.html
├── track_a/
│   ├── report.html
│   └── ...
└── track_b/
    └── ...
```

The catalog report shows folder-level ranges, medians, and technical
fingerprints. It is descriptive and does not rank, score, or judge tracks.
When a trait appears across a substantial share of the folder, catalog
mode can show it once as a common pattern so repeated per-track findings
read as folder context instead of isolated verdicts. For lossy-heavy
folders such as MP3 collections, decoded clipping and true-peak context
describe decoded audio as delivered; they do not establish what happened
in the original master.

## Tests

```bash
make test           # pytest
make check          # pytest + ruff
make demo           # run the CLI on the golden fixture
```

Or directly:

```bash
pytest
ruff check .
audioatlas analyze tests/fixtures/sine_1k_-6dbfs_2s.wav --out /tmp/aa_demo
```

## Design principles

1. Preserve original levels. Do not normalize unless the user explicitly asks.
2. Use internal audio shape `(n_samples, n_channels)` everywhere.
3. Keep analysis and visualization separate.
4. Analysis functions are pure: arrays in, dataclasses out.
5. Visualization functions never re-run analysis.
6. Use measured facts and visualizations, not automated judgment.
7. Add features one slice at a time: dataclass → analysis fn → test →
   plot → summary entry → report entry → pipeline wiring.

See `docs/ARCHITECTURE.md` for the full layering contract.

## v0.1 intentionally does not include

- PDF output
- Reference-track comparison
- Mix-health score or any verdict
- AI mastering advice
- Section segmentation
- Streamlit / GUI / real-time playback cursor

Those can come later, in the order set out in `docs/AGENT_TASKS.md`,
after the core engine is trustworthy.

## License

MIT.
