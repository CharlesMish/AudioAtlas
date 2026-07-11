# AudioAtlas Installed-Environment Launchers

These scripts make an **already installed** AudioAtlas easier to run. They are
not an installer, signed application, or proof of a fully nontechnical setup.
Install and verify AudioAtlas first; then the launchers can reduce routine use to
a double click.

## 1. Install and verify

From this project folder:

```bash
python -m pip install .
audioatlas --version
```

A source checkout with `uv` may instead use `uv sync`, but the double-click
scripts look for the installed `audioatlas` command on `PATH`. The first full
analysis in a fresh environment may pause while scientific libraries initialize;
the launcher should remain open and AudioAtlas prints a preparation message.

## 2. Batch launcher

Create `input_audio/` at the project root and place supported audio there.
Batch discovery recognizes WAV, WAVE, FLAC, OGG, AIFF/AIF, and MP3 files when
the local decoder supports them.

- Windows: double-click `scripts/run_audioatlas_windows.bat`
- macOS: double-click `scripts/run_audioatlas_mac.command`

The scripts write `output_reports/catalog.html` and try to open it. On macOS,
Gatekeeper may require right-clicking the script and choosing **Open** once.

## 3. Single-track starter kit

`starter_kit/` contains compact, standard, full, and prompted-section
launchers. Put one file in `starter_kit/PUT_AUDIO_HERE/` and run the matching
`.bat` or `.command` file. `RUN_MINIMAL` is the legacy filename for the compact
four-plot view; it still performs the complete analysis.

## Honest support boundary

The Python CLI and generated reports are tested automatically. Native double-
click behavior, PATH inheritance, Gatekeeper, and Windows security prompts must
still be rehearsed on the target machines before describing this as a
nontechnical installation path. Follow `docs/LAUNCHER_REHEARSAL.md` and copy
`starter_kit/LAUNCHER_REHEARSAL_LOG.md` for each native run.
