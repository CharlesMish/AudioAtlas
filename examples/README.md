# AudioAtlas Examples

This directory intentionally contains documentation only for v0.1-alpha. It
does not include copyrighted, third-party, or calibration audio.

## Run the Committed Test Fixture

The repository includes a small generated sine-wave fixture for tests:

```bash
uv run audioatlas analyze tests/fixtures/sine_1k_-6dbfs_2s.wav --out reports/example_sine
```

Or with an activated virtualenv:

```bash
audioatlas analyze tests/fixtures/sine_1k_-6dbfs_2s.wav --out reports/example_sine
```

Then open:

```text
reports/example_sine/report.html
```

## Run Your Own Audio

```bash
uv run audioatlas analyze /path/to/your/song.wav --out reports/your_song
uv run audioatlas batch /path/to/your/folder --out reports/your_catalog
```

Generated reports are ignored by git. Keep example audio private unless it is
original material you intend to publish with a compatible license.

## Example Reports

No committed example reports ship in v0.1-alpha. Local reports under `reports/`
are generated artifacts and are intentionally excluded from the release.
