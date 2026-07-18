# AudioAtlas user guide

AudioAtlas is a local report generator for one audio file at a time. It helps
you see measured structure and decide where to listen more carefully. It does
not grade the track or tell you what artistic choice to make.

## Installation

### Apple Silicon macOS app

For the lowest-setup path, download the signed/notarized
`AudioAtlas-<version>-macOS-arm64.dmg` from the matching GitHub prerelease. Drag
AudioAtlas into Applications and open it. Drop one supported audio file or use
**Choose Audio File**. The app uses the standard graph set and default Studio
theme, writes `AudioAtlas Report – <track>` beside the source, and opens the
finished report automatically. It does not need Python, Terminal, an account,
or a network connection after download.

If the source folder cannot be written, choose another report location when
prompted. The first app beta supports Apple Silicon and macOS 14 or newer.
Cancel, Quit, and closing the window request a safe stop; once publication has
started, AudioAtlas finishes the complete report before exiting. Existing
unowned folders are never adopted, and same-stem files receive distinct report
folders when needed.

### Python CLI

AudioAtlas supports Python 3.11 and newer. For a normal installation:

```bash
python -m pip install audioatlas
```

For an editable source checkout, create and activate an environment:

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Then install:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Verify the lightweight command path:

```bash
audioatlas --version
audioatlas themes
```

## One-track reports

The shortest useful command is:

```bash
audioatlas analyze song.wav
```

AudioAtlas creates `audioatlas-report-song/` in the current directory. Supply
`--out` when you want a different location:

```bash
audioatlas analyze song.wav --out reports/song
```

Open `report.html`. The Markdown and JSON files beside it are intended for
archiving, source inspection, or downstream scripts.

### Focus and Studio presentation

Every generated HTML report can switch between:

- **Studio** — the polished default with richer cards, framing, and hierarchy;
- **Focus** — a restrained, information-first shell.

The switch changes CSS only. It does not change the measurement summary,
findings, graph selection, or PNG pixels.

Use `--presentation focus` to make Focus the opening state:

```bash
audioatlas analyze song.wav --presentation focus
```

The report remembers the selected view locally for that report path when the
browser permits local storage. Both modes remain usable without JavaScript; the
opening mode is present in the HTML itself.

### Graph depth

Graph profiles control which PNGs are rendered. They do not skip the complete
analysis summary.

| Profile | Plots | Notes |
|---|---:|---|
| `compact` | 4 | Friendly compact view |
| `minimal` | 4 | Legacy alias kept for compatibility |
| `standard` | 14 | Default |
| `full` | 17 | Adds distribution/detail plots |

```bash
audioatlas analyze song.wav --graphs-profile compact
audioatlas analyze song.wav --graphs-profile full
```

Add or remove individual graphs:

```bash
audioatlas analyze song.wav \
  --graphs-profile compact \
  --enable chroma_cqt,stereo_correlation \
  --disable rms_timeline
```

A YAML graph configuration can also be used:

```yaml
graphs:
  profile: compact
  enable: [chroma_cqt, stereo_correlation]
  disable: []
```

```bash
audioatlas analyze song.wav --graphs-config graphs.yaml
```

Configuration keys are checked strictly so misspellings fail with a clear
error instead of silently selecting defaults. One YAML file may contain both
the documented `graphs` block and the documented `sections` block.

### Themes

Themes change the report and graph color system. They are separate from the
Focus/Studio presentation shell.

```bash
audioatlas themes
audioatlas analyze song.wav --theme midnight_studio
```

### Source ranges

```bash
audioatlas analyze song.wav --start 30 --end 62 --out reports/verse
```

This is a manual source range. AudioAtlas does not detect verse, chorus, or
other structure automatically.

## Reading the report

A useful order is:

1. Read the delivery and headroom context.
2. Check any review prompts.
3. Open the associated plots.
4. Listen to the named regions.
5. Record your own decision.

Important boundaries:

- Findings are threshold-backed prompts, not proof of audibility or a defect.
- Relative-dB plots describe shape within the current analysis view. They are
  not absolute dBFS values and should not be compared as meters across songs.
- PLR is approximate true peak minus integrated loudness. Constant loudness
  normalization changes both values by the same gain and does not change PLR.
- Lossy files are measured after decoding. Peak observations do not establish
  what happened in the original master.
- Human notes autosave in local browser storage for the report path. Copy and
  Export create user-controlled text copies; notes are not written into the
  report bundle or sent over a network.

### Keyboard and long-report navigation

- Use the skip link to move directly to report content.
- Tab to any plot and press Enter or Space to open it. Escape closes the viewer;
  Left/Right arrows move between plots; focus returns to the plot you opened.
- Metric labels link to their glossary definitions. Review prompts link to their
  associated plots, and plot cards link back to related prompts.
- Lower-priority observations remain collapsed until requested.

## Same-track revision deltas

Analyze two exports with the same high-entropy token:

```bash
audioatlas analyze mix-v3.wav --out reports/mix-v3 --track-id "unique-private-token"
audioatlas analyze mix-v4.wav --out reports/mix-v4 --track-id "unique-private-token"
audioatlas diff reports/mix-v3 reports/mix-v4 --out reports/mix-v3-to-v4
```

The raw token is not serialized. Reusing a token can still link reports, and a
short token can be guessed and hashed again, so use a unique random value. A
command-line token may also remain in shell history.

The diff refuses conflicting identity digests. Missing identity requires
`--confirm-same-track`. Materially different or missing analysis provenance is
refused unless `--allow-incomparable` is supplied, in which case the output
retains a prominent caveat.

## Song projects

A song project keeps successive exports and their adjacent descriptive diffs
inside one local static workspace:

```bash
audioatlas project init projects/my-song --name "My Song"
audioatlas project add projects/my-song mix-v1.wav --label "Mix 1"
audioatlas project add projects/my-song mix-v2.wav --label "Mix 2"
audioatlas project build projects/my-song
```

`project add` analyzes the new revision before changing the project. A failed
analysis leaves the configuration and all prior reports unchanged. The project
uses a random local identity token; only its SHA-256 digest enters generated
reports and indexes.

Mutating project commands are serialized across processes. If another
`project init`, `project add`, or `project build` operation is active for the
same workspace, AudioAtlas fails immediately with a friendly retry message
instead of risking a lost revision. Rebuilds also verify project identity,
ownership manifests, share-safe metadata, and non-symlinked artifact paths.

Reuse one manual section map across every revision:

```bash
audioatlas project init projects/my-song \
  --name "My Song" \
  --sections sections.yaml
```

The human-readable `audioatlas-project.yaml` is owner-side state and records
local source paths. Do not include it in a share bundle unless those paths are
intended for the recipient. AudioAtlas writes this file with owner-only
permissions on POSIX systems. `project.json`, `project.md`, `project.html`, and
the nested report/diff artifacts contain portable source filenames by default.

An adjacent diff is refused when analysis provenance changed. Use
`project add --allow-incomparable` only for a deliberately caveated forensic
comparison; the project never ranks revisions or recommends a winner.

## Manual sections

```bash
audioatlas sections song.wav --out reports/song-sections \
  --section intro:0:30 \
  --section verse:30:62 \
  --section ending:62:
```

You may instead use YAML:

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
audioatlas sections song.wav --out reports/song-sections --config sections.yaml
```

Section names must be single-line and 160 characters or fewer. Definitions
that would resolve to the same output-folder slug are rejected before analysis
so one section cannot silently replace another.

## Folder catalogs

```bash
audioatlas batch /path/to/audio-folder --out reports/catalog
```

Supported discovery extensions are WAV/WAVE, FLAC, OGG, AIFF/AIF, and MP3.
Actual decoding depends on the local `libsndfile` build. Unreadable files are
recorded while valid files continue. Use `--strict` when partial success is not
acceptable.

Catalogs use folder and file labels rather than absolute paths by default.

## Sharing and privacy

By default, report and catalog JSON contain basenames instead of resolved local
paths. `--include-local-paths` is an explicit sharing-sensitive opt-in.

AudioAtlas writes to a staging folder first and publishes only a complete
result. Its ownership manifest lets a later run remove stale AudioAtlas files
while preserving unrelated files in the destination.

## Output structure

A standard report normally includes:

```text
.audioatlas-output.json
summary.json
findings.json
report.md
report.html
waveform_rms.png
rms_timeline.png
crest_factor_timeline.png
log_spectrogram.png
average_spectrum.png
sample_histogram.png
stereo_correlation.png
mid_side_energy.png
spectral_shape.png
band_energy_timeline.png
onset_density.png
chroma_cqt.png
short_term_lufs.png
peak_timeline.png
```

The historical filename `band_energy_timeline.png` remains stable, but the
current measurement is relative mean spectral power per included FFT bin—not
total energy integrated across differently sized bands.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
python -m build
```

See the architecture, schema, compatibility, and finding-rule documents for the
more technical contracts, including the dedicated
[song-project schema](PROJECT_SCHEMA.md).
