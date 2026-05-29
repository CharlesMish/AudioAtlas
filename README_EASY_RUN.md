# AudioAtlas Easy Run

This is the simplest local batch workflow.

## Install Requirements

Install Python 3.11 or newer, then install AudioAtlas from this folder:

```bash
python -m pip install -e .
```

If you want the test tools too:

```bash
python -m pip install -e ".[dev]"
```

## Add Audio Files

Create or use the `input_audio/` folder in this project folder. Put audio
files there. Batch mode currently supports `.wav` and `.mp3`.

## Run

Windows:

Double-click:

```text
scripts/run_audioatlas_windows.bat
```

macOS:

Double-click:

```text
scripts/run_audioatlas_mac.command
```

If macOS blocks the script, right-click it, choose Open, and confirm.

## Open The Catalog

The scripts write reports to:

```text
output_reports/
```

They try to open:

```text
output_reports/catalog.html
```

If it does not open automatically, open that file in your browser.

The catalog shows folder-level technical fingerprints, ranges, and
medians. It does not score, rank, or judge tracks.
