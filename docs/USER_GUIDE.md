# AudioAtlas user guide

AudioAtlas is a local report generator for one audio file at a time. It helps
you see measured structure and decide where to listen more carefully. It does
not grade the track or tell you what artistic choice to make.

## Installation

### Python CLI — recommended

AudioAtlas supports Python 3.11 and newer on macOS, Windows, and Linux where its
scientific Python and audio-decoder dependencies are available. For the
recommended `0.2.0a8` public-alpha installation:

```bash
python -m pip install audioatlas==0.2.0a8
audioatlas --version
audioatlas themes
```

### Native application status

An optional `0.2.0a8` Apple Silicon application may be provided as an **unsigned
technical preview** for experienced testers. It requires macOS 14 or newer and
is not signed, notarized, Gatekeeper-approved, or the recommended route. Apple
cannot authenticate its developer. Do not weaken macOS security controls; use
the Python CLI if ordinary launch is blocked.

No Windows desktop download is included in this alpha. The genuine Windows
build and native client acceptance remain pending; Windows users can use the
Python CLI.

### Editable source checkout

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

### Measurement scope and scales

Measurements describe the analyzed audio: the whole file or the selected range.
For a selected range, plot and finding times start from that range, not the
original file. Add the displayed source start time to locate the same point in
the original file. No timestamp conversion is applied to the measurements.

- **RMS** measures amplitude, not energy or hearing-weighted loudness. Headline
  RMS pools all channel samples. The RMS timeline uses the arithmetic-average
  mono signal, so opposing channels can cancel. Headline and frame crest use
  all channels; the crest timeline is not derived from the mono RMS timeline.
- **Average spectrum** uses the mono signal and a reference within the analyzed
  view: its strongest averaged bin at or above 20 Hz is 0 relative dB for
  measurable audio. It does not report calibrated dBFS.
- **Spectral shape** uses spectral magnitude: centroid is the weighted mean
  frequency, rolloff contains 85% or 95% of summed magnitude, and bandwidth is
  the weighted root-mean-square spread around centroid. All are in Hz; they do
  not establish note pitch, a filter cutoff, or musical quality.
- **Onset density** retains raw smoothed onset-strength values in summaries;
  each displayed onset curve is independently normalized to a maximum of 1
  (zero for no activity). It is not a count of events per second.
- **Chroma** folds pitch-class energy across octaves and normalizes each nonzero
  frame to a maximum of 1. It is not exact note pitch (F0) or tuning accuracy.
- **Stereo correlation** is Pearson r: +1 means matching variation, not
  necessarily equal levels; negative values mean opposing variation. **Mid/side**
  uses `(L + R) / 2` and `(L - R) / 2`; positive side/mid dB means more side RMS,
  negative means more mid RMS. Undefined ratios are not zero. Neither metric
  directly measures perceived width.

HTML links key metrics to the glossary. Markdown places the same definitions
beside the relevant measurement summaries.

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

### Report depth

These presets are a local source prototype, not a published-package availability claim.

Choose a report depth for `analyze`, `batch`, or `sections`:

| Depth | Computation | Graph profile | Report contents |
|---|---|---|---|
| `overview` | Compact | Compact | Key current measurements, all current finding checks, 4 plots |
| `standard` | Full | Standard | All measurements, 14 plots; default |
| `detailed` | Full | Full | All measurements, 18 plots |

```bash
audioatlas analyze song.wav --report-depth overview
audioatlas batch recordings --out reports/catalog --report-depth standard
audioatlas sections song.wav --section verse:30:62 --out reports/sections --report-depth detailed
```

Compact computation reduces measurement breadth, not numerical fidelity. It
retains levels, RMS, peaks, spectral shape, stereo, mid/side, and spectrogram for
the default Overview plots. Every current finding rule has its required inputs;
this does not mean full analysis was run. Detailed adds plots to Standard, not
higher measurement fidelity. These presets make no runtime guarantee.

Before analysis, the CLI prints resolved depth, computation breadth, plot count
per report, and any optional analyses restored by graph selection. With no depth
or advanced flags, behavior remains Standard. Without a preset, combinations
matching a fixed pair display its depth; other combinations display `Custom`.

A preset promises a fixed computation/profile pair. Matching explicit settings
are accepted, including `minimal` as the Overview graph alias and graph changes
that leave the selected set unchanged. Accepted preset selections are stored as
the preset's canonical graph profile without redundant enable/disable entries.
Conflicting computation, profiles, or effective graph changes fail before report
output is created. This includes a conflicting YAML profile even if a CLI profile
would otherwise override it. Remove `--report-depth` to customize both axes.

Report depth is separate from Focus/Studio presentation, themes, source ranges,
and the future measurements-only snapshot operation. Projects currently persist
only graph profile and run full computation; report-depth persistence needs a
separate project compatibility/schema decision and is not added here.

### Advanced computation and graph controls

`--analysis-mode full` remains the default. `--analysis-mode compact` defaults to
four plots unless an explicit CLI or YAML graph profile selects another set.
Graph profiles select PNGs; they alone do not reduce computation. Graph additions
restore their required analyses once, including in compact computation. For
example, compact computation with standard graphs restores all current families.
The pre-run plan lists these restored families before computation begins.

Existing `--analysis-mode`, `--graphs-profile`, `--enable`, `--disable`, and YAML
commands remain available independently of report depth. Without a preset, CLI
profile still takes precedence over YAML profile and enable/disable lists merge.

| Profile | Plots | Notes |
|---|---:|---|
| `compact` | 4 | Friendly compact view |
| `minimal` | 4 | Legacy alias kept for compatibility |
| `standard` | 14 | Default |
| `full` | 18 | Adds distribution/detail plots |

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
- Approximate true peak is not a standards-grade true-peak measurement.
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

### L/R RMS balance

Full analysis measures signed channel RMS difference. Positive values mean the
left channel has higher RMS amplitude; negative values mean the right channel
does. Zero means equal RMS in that frame. It does not establish pan position,
perceived balance, or a mixing defect, and creates no finding.

Standard includes its summary; Detailed adds a full-width signed timeline
(18 plots total). Overview remains 4 plots and skips this measurement. Advanced
users can request the plot independently with `--enable lr_balance`; in compact
mode this restores just the required measurement once. Omit a fixed
`--report-depth` preset when customizing plots.

```bash
audioatlas analyze song.wav --analysis-mode compact --enable lr_balance
```

Only exactly two channels apply. Complete frames use 4096 samples and hop 1024
by default. Gaps mean at least one channel falls below the analysis floor
(default -80 dBFS RMS per channel), not equal channel RMS. The floor is not a
quality threshold. Summary JSON retains the per-frame operands and reasons;
plot times are frame centers relative to the analyzed file or selected range.
