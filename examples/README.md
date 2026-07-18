# AudioAtlas examples

This directory contains two kinds of example input:

- `demo_audio/` contains three intentionally public musical recordings. Read its
  [recording notes](demo_audio/README.md) and the repository's
  [audio rights notice](../AUDIO_RIGHTS.md).
- `tests/fixtures/` contains project-generated signals for deterministic
  mechanics tests.

The musical recordings are demonstrations, not deterministic golden fixtures
or threshold-calibration evidence.

## Analyze one real recording

```bash
uv run audioatlas analyze examples/demo_audio/audioatlas_demo.wav \
  --out reports/audioatlas-demo \
  --graphs-profile standard \
  --theme midnight_studio
python -m webbrowser reports/audioatlas-demo/report.html
```

The generated HTML opens in Studio and still offers the Focus/Studio switch.

## Build a clean three-track catalog

Batch catalogs record non-audio files as skipped. Make an audio-only working
folder so the catalog contains exactly three tracks and zero skipped files:

```bash
rm -rf reports/demo-audio-input
mkdir -p reports/demo-audio-input
cp examples/demo_audio/*.wav reports/demo-audio-input/
uv run audioatlas batch reports/demo-audio-input \
  --out reports/demo-catalog \
  --graphs-profile full

python -m webbrowser reports/demo-catalog/catalog.html
python -m webbrowser reports/demo-catalog/audioatlas_demo/report.html
python -m webbrowser reports/demo-catalog/guitar/report.html
python -m webbrowser reports/demo-catalog/guitar_koto_cello_drums/report.html
```

AudioAtlas safely refreshes files it owns when the same output directory is
used again. Generated reports are ignored by Git.

## Generate a compact fixture report

```bash
uv run audioatlas analyze tests/fixtures/sine_1k_-6dbfs_2s.wav \
  --out reports/example-sine \
  --graphs-profile compact
```

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

Keep personal and calibration audio private unless you own it and intentionally
publish it under a compatible license.
