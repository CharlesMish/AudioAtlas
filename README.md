# AudioAtlas

**AudioAtlas turns one audio file into a private, portable listening map:**
measured context, places worth inspecting, and clear limits on what each
measurement establishes.

It runs locally, preserves decoded input levels, and writes a self-contained
bundle of HTML, Markdown, JSON, PNG plots, and an ownership manifest. The report
helps you decide **where to listen more carefully**; it does not decide whether
the music is good.

## Status: `0.2.0a3` — calibration readiness and workflow polish

AudioAtlas is a public alpha. The report pipeline, graph registry, sections, and
catalog workflows are usable, but finding thresholds remain in calibration.
Treat findings as review prompts—not diagnoses, scores, or mastering decisions.
See [the project charter](PROJECT_CHARTER.md) for the product boundary and
[the finding-rule ledger](docs/FINDING_RULES.md) for exact trigger semantics.
This release keeps the `0.2.0a2` finding ruleset unchanged while improving
calibration, review, compatibility, launcher, and CLI workflows.

![AudioAtlas report overview](docs/assets/readme/report_overview.png)

## What it does

- Preserves original decoded levels; input is never auto-normalized.
- Measures scalar levels, approximate true peak, clipping/near-clipping, RMS,
  crest factor, short-term LUFS, stereo correlation, mid/side energy, spectral
  shape, relative mean band power, onset activity, and chroma pitch-class
  energy.
- Generates static local reports with no server, account, CDN, telemetry, or
  network dependency.
- Records bounded review prompts with stable rule IDs, typed evidence, and
  associated graph keys for audit and future linking.
- Supports user-defined time sections and descriptive folder catalogs.
- Excludes machine-local absolute paths from report data by default.
- Renders into a staging folder and rolls back a failed publication so an
  analysis, rendering, or individual file-update failure does not erase the
  last complete result; stale AudioAtlas plots are removed while unrelated
  files are preserved.
- Continues batch runs after an unreadable file by default and records the
  failure in the catalog.

## What it deliberately does not do

- No mix, loudness, mastering, or quality score.
- No automated EQ, compression, or mastering prescription.
- No reference-track ranking.
- No genre, instrument, source, key, or automatic section detection.
- No source separation, cloud dashboard, playback engine, or DAW integration.
- No claim that a threshold crossing is audible, bad, or musically wrong.

## Install from a source checkout

AudioAtlas supports Python 3.11 or newer. The tested support matrix is defined in
`.github/workflows/ci.yml`.

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync --extra dev
```

With a standard virtual environment:

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Analyze one track

From a source checkout with `uv`:

```bash
uv run audioatlas analyze /path/to/song.wav --out reports/song
```

From an environment where AudioAtlas is installed:

```bash
audioatlas analyze /path/to/song.wav --out reports/song
```

Open `reports/song/report.html` directly in a browser. The first analysis in
a fresh environment can take longer while scientific libraries initialize;
AudioAtlas prints a preparation message immediately, and lightweight commands
such as `--version`, `--help`, and `themes` avoid loading the analysis stack.

Common variants:

```bash
# Compact four-plot first read; complete analysis JSON is still generated
uv run audioatlas analyze song.wav --out reports/compact --graphs-profile minimal

# All 17 registered plots
uv run audioatlas analyze song.wav --out reports/full --graphs-profile full

# A manual source range
uv run audioatlas analyze song.wav --out reports/verse --start 30 --end 62

# A built-in presentation theme
uv run audioatlas analyze song.wav --out reports/dark --theme midnight_studio

# Explicitly include absolute local paths (off by default)
uv run audioatlas analyze song.wav --out reports/local --include-local-paths
```

### Graph profiles

Graph profiles control **rendered PNG depth only**. They do not skip DSP or
remove measurements from `summary.json`.

| CLI profile | Plots | Purpose |
|---|---:|---|
| `minimal` | 4 | Compact first read; name retained for CLI compatibility |
| `standard` | 14 | Default report |
| `full` | 17 | Adds distribution/detail plots |

You may add or remove graph keys without changing the analysis summary:

```bash
uv run audioatlas analyze song.wav --out reports/custom \
  --graphs-profile minimal \
  --enable chroma_cqt,stereo_correlation
```

Or use YAML:

```yaml
graphs:
  profile: minimal
  enable: [chroma_cqt, stereo_correlation]
  disable: []
```

```bash
uv run audioatlas analyze song.wav --out reports/custom --graphs-config graphs.yaml
```

List built-in themes:

```bash
uv run audioatlas themes
```

## Manual sections

AudioAtlas does not infer song structure. It applies the same report pipeline to
source ranges you provide:

```bash
uv run audioatlas sections song.wav --out reports/song_sections \
  --section intro:0:30 \
  --section verse:30:62 \
  --section ending:62:
```

Or save ranges in YAML:

```yaml
sections:
  - name: intro
    start: 0
    end: 30
  - name: verse
    start: 30
    end: 62
  - name: ending
    start: 62
```

```bash
uv run audioatlas sections song.wav --out reports/song_sections --config sections.yaml
```

The output includes `section_index.md` with a neutral comparison table.

![AudioAtlas section comparison table](docs/assets/readme/sections_comparison.png)

## Folder catalogs

```bash
uv run audioatlas batch /path/to/audio_folder --out reports/catalog
```

Batch discovery recognizes `.wav`, `.wave`, `.flac`, `.ogg`, `.aif`, `.aiff`,
and `.mp3`. Actual decoding depends on the local `libsndfile` build. Unreadable
files are listed in `catalog_summary.json`, `catalog.md`, and `catalog.html`
while valid tracks continue.

Use strict mode when partial success is not acceptable:

```bash
uv run audioatlas batch audio_folder --out reports/catalog --strict
```

By default, catalog and track JSON use folder/file labels rather than absolute
paths. `--include-local-paths` is an explicit sharing-sensitive opt-in.

## Output contract

A standard single-track folder contains:

```text
reports/song/
├── .audioatlas-output.json
├── summary.json
├── findings.json
├── report.md
├── report.html
├── waveform_rms.png
├── rms_timeline.png
├── crest_factor_timeline.png
├── log_spectrogram.png
├── average_spectrum.png
├── sample_histogram.png
├── stereo_correlation.png
├── mid_side_energy.png
├── spectral_shape.png
├── band_energy_timeline.png
├── onset_density.png
├── chroma_cqt.png
├── short_term_lufs.png
└── peak_timeline.png
```

The historical filename `band_energy_timeline.png` remains stable for existing
links and graph configurations. Its current title and schema define the actual
measurement: **relative mean spectral power per included FFT bin**, not total
energy integrated across differently sized bands.

![Representative AudioAtlas graph examples](docs/assets/readme/graph_examples.png)

## How to interpret the report

- Findings are threshold-backed prompts. They do not prove audibility, intent,
  quality, or a defect.
- Relative dB plots are normalized within an analysis view. They are not dBFS
  and should not be compared as absolute levels across songs.
- PLR is approximate true peak minus integrated loudness. Loudness
  normalization changes both by the same gain and therefore does not change
  PLR.
- Absolute rolloff, highest broad band, onset movement, centroid movement, and
  dominant chroma remain descriptive measurements; they do not create musical
  conclusions by default.
- Lossy files are measured after decoding. Peak/clipping observations do not
  establish what happened in the source master.
- Human note fields in the static HTML are temporary browser fields; they are
  not currently saved into the report bundle.

## Double-click launchers

`starter_kit/` and `scripts/` contain convenience launchers for an **already
installed** AudioAtlas environment. They are not installers and have not been
recast as a native desktop app. Read [README_EASY_RUN.md](README_EASY_RUN.md)
before handing them to a nontechnical user. Use the
[native launcher rehearsal](docs/LAUNCHER_REHEARSAL.md) and the included log
before making stronger ease-of-use claims.

## Development and verification

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
uv build
```

Generate the public deterministic calibration fixtures:

```bash
uv run python scripts/generate_calibration_fixtures.py
```

Seed an anonymous human-review worksheet from completed private reports:

```bash
uv run python scripts/prepare_calibration_review.py private_reports \
  --out finding_review.csv \
  --private-map private_asset_map.csv
```

The private musical-corpus gate is documented in
[`docs/calibration/README.md`](docs/calibration/README.md) and the concrete
[`calibration runbook`](docs/calibration/CALIBRATION_RUNBOOK.md). The repository
does not claim that human listening calibration is complete.

## Documentation

- [Project charter](PROJECT_CHARTER.md)
- [Finding rule ledger](docs/FINDING_RULES.md)
- [Alpha limitations](docs/ALPHA_LIMITATIONS.md)
- [Summary and findings schemas](docs/SUMMARY_SCHEMA.md)
- [Compatibility policy](docs/COMPATIBILITY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Calibration workflow](docs/calibration/README.md)
- [Musical calibration runbook](docs/calibration/CALIBRATION_RUNBOOK.md)
- [Native launcher rehearsal](docs/LAUNCHER_REHEARSAL.md)
- [Hopeful Skeptic Project Edition](docs/HOPEFUL_SKEPTIC_PROJECT_EDITION.md)
- [Changelog](docs/CHANGELOG.md)
- [Examples](examples/README.md)

## License

[MIT](LICENSE).
