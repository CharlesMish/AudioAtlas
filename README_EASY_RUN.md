# AudioAtlas easy-run launchers

These scripts make an **already installed** AudioAtlas easier to use. They are
not a standalone installer or signed desktop application.

## Install and verify once

From this project folder:

```bash
python -m pip install .
audioatlas --version
```

## Folder launcher

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

## Honest setup boundary

The launchers depend on the installed `audioatlas` command being available on
`PATH`. Finder, Gatekeeper, Windows security prompts, spaces, and non-ASCII
filenames can behave differently across machines. Test the launchers on the
actual target computer before promising a one-click setup. Keep the terminal
window open during the first run; scientific libraries may need extra startup
time.
