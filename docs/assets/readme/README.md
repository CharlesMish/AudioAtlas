# README visual assets

These screenshots come from real AudioAtlas reports generated with the
rights-cleared recordings in `examples/demo_audio`. They are not mockups and do
not use synthetic test fixtures.

## Default Studio overview

Generate `report_overview.png` from the normal no-theme report:

```bash
uv run audioatlas analyze examples/demo_audio/guitar.wav \
  --out /tmp/audioatlas-readme-default-source \
  --graphs-profile standard
```

Capture the top of `report.html` at 1500 x 1050 pixels. Do not pass `--theme` or
`--presentation`: the image documents the regular light-theme, Studio-opening
experience.

## Midnight plot cards

Generate `midnight_report_plots.png` from the full Midnight Studio report:

```bash
uv run audioatlas analyze examples/demo_audio/guitar_koto_cello_drums.wav \
  --out /tmp/audioatlas-readme-midnight-source \
  --graphs-profile full \
  --theme midnight_studio
```

Capture the report's actual `#plots` cards at 1500 x 1050 pixels. Keep the
generated PNG plot canvases visible so the image demonstrates shell and plot
theme unity.

Regenerate both images whenever the report shell or plot theming changes.
