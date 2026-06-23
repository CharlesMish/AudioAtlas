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
uv run audioatlas analyze /path/to/your/song.wav --out reports/your_verse --start 30 --end 62
uv run audioatlas sections /path/to/your/song.wav --out reports/your_sections \
  --section intro:0:30 \
  --section verse:30:62 \
  --section ending:62:
uv run audioatlas sections /path/to/your/song.wav --out reports/your_sections \
  --config sections.yaml
uv run audioatlas batch /path/to/your/folder --out reports/your_catalog
```

Section scans are manually defined. Use them when one song has distinct parts
and the whole-song averages are less useful for a specific listening question.

Example `sections.yaml`:

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

Omit `end` on a section to analyze through EOF. `--config` and repeated
`--section` flags can be combined; both feed the same section parser.

Generated reports are ignored by git. Keep example audio private unless it is
original material you intend to publish with a compatible license.

## Example Reports

No committed example reports ship in v0.1-alpha. Local reports under `reports/`
are generated artifacts and are intentionally excluded from the release.
