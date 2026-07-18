# AudioAtlas desktop app and legacy launchers

## Recommended: Apple Silicon Mac app

Download the signed/notarized DMG from the matching GitHub prerelease, drag
AudioAtlas into Applications, and open it normally. Drop or choose one audio
file. The app shows analysis progress, creates a themed report folder beside
the track, opens `report.html`, and can reveal the folder in Finder.

The app runs locally and does not need Python, Terminal, PATH setup, an account,
or a network connection after download. If the source folder is read-only, it
asks for another report location. The first beta supports macOS 14 or newer on
Apple Silicon.

## Advanced CLI installation

## Install and verify once

Install the published package:

```bash
python -m pip install audioatlas
audioatlas --version
```

An editable source checkout may use `python -m pip install -e .` instead.

## Legacy folder launcher

Create `input_audio/` at the project root and place supported audio there.

- Windows: double-click `scripts/run_audioatlas_windows.bat`
- macOS: double-click `scripts/run_audioatlas_mac.command`

The scripts write `output_reports/catalog.html` and try to open it.

## Single-track starter kit

Put one supported file in `starter_kit/PUT_AUDIO_HERE/`, then choose:

- `RUN_MINIMAL` — legacy filename for the compact four-plot view;
- `RUN_STANDARD` — normal report depth;
- `RUN_FULL` — every registered plot;
- `RUN_SECTIONS_PROMPTED` — manually enter source ranges.

All choices run the same complete analysis. They differ only in rendered plots.
Every finished HTML report can switch between Focus and Studio presentation.

## Legacy-launcher boundary

These older launchers depend on the installed `audioatlas` command being available on
`PATH`. Finder, Gatekeeper, Windows security prompts, spaces, and non-ASCII
filenames can behave differently across machines. Test the launchers on the
actual target computer before promising a one-click setup. Keep the terminal
window open during the first run; scientific libraries may need extra startup
time.
