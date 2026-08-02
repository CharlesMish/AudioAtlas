# AudioAtlas installation routes and legacy launchers

## Recommended: Python package and CLI

AudioAtlas `0.2.0a8` supports Python 3.11 or newer. Install and verify the public
alpha package:

```bash
python -m pip install audioatlas==0.2.0a8
audioatlas --version
audioatlas analyze song.wav --graphs-profile compact
```

The report appears in `audioatlas-report-song/` unless `--out` selects another
folder. Open `report.html`. Use `--graphs-profile full` for every registered
plot.

An editable source checkout may use `python -m pip install -e .` instead.

## Optional: unsigned Apple Silicon technical preview

Any `0.2.0a8` native preview supplied with the owner-approved release must be
labeled **UNSIGNED APPLE SILICON TECHNICAL PREVIEW**. It requires Apple Silicon
and macOS 14 or newer. It is not signed, notarized, Gatekeeper-approved, or the
recommended installation path, and Apple cannot authenticate its developer.
It is intended only for experienced testers.

Verify its published SHA-256 before testing and launch it only through ordinary
macOS behavior. If macOS blocks it, stop and use the Python CLI. Do not bypass
Gatekeeper, remove quarantine metadata, or weaken security settings.

## Windows desktop status

No Windows desktop download is included in the `0.2.0a8` public alpha. A genuine
native Windows build and client acceptance remain pending. Windows users can
use the Python CLI.

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
