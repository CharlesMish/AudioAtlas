# AudioAtlas examples

This directory contains workflow documentation only. The repository includes a
small generated sine-wave fixture under `tests/fixtures/`; it does not include
third-party or copyrighted calibration music.

## Generate a compact example report

```bash
uv run audioatlas analyze tests/fixtures/sine_1k_-6dbfs_2s.wav \
  --out reports/example_sine \
  --graphs-profile minimal
```

Then open `reports/example_sine/report.html`.

The sine fixture verifies deterministic mechanics; it is not evidence that
finding thresholds generalize to music.

## Analyze your own audio

```bash
uv run audioatlas analyze /path/to/song.wav --out reports/song
uv run audioatlas analyze /path/to/song.wav --out reports/verse --start 30 --end 62
uv run audioatlas sections /path/to/song.wav --out reports/sections \
  --section intro:0:30 \
  --section verse:30:62 \
  --section ending:62:
uv run audioatlas batch /path/to/folder --out reports/catalog
```

Manual section ranges may also come from YAML:

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

Omit `end` to analyze through EOF. AudioAtlas does not detect sections.

Generated reports are ignored by git. Keep personal and calibration audio
private unless you own it and intentionally publish it under a compatible
license.
