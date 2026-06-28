# AudioAtlas Starter Kit

This folder is for people who do not want to use command-line tools directly.

## One-Time Requirement

AudioAtlas must already be installed on this computer.

If a launcher says:

> AudioAtlas was not found. Install AudioAtlas first, or run this from an activated environment.

then AudioAtlas is not available to the launcher yet.

## Quick Start

1. Put one audio file into `PUT_AUDIO_HERE`.
2. Double-click `RUN_STANDARD`.
   - On Windows, use `RUN_STANDARD.bat`.
   - On macOS, use `RUN_STANDARD.command`.
3. Wait for the report to finish.
4. Open the generated `REPORTS/.../report.html` file in a browser.

## Modes

- Minimal: quick report, 4 plots.
- Standard: default report, 14 plots.
- Full: detailed report, 17 plots.

Use:

- `RUN_MINIMAL` for the quick report.
- `RUN_STANDARD` for the default report.
- `RUN_FULL` for the most detailed report.

## Sections

Sections are optional.

Use `RUN_SECTIONS_PROMPTED` only if you know rough timestamps for the song.
It will ask for:

- number of sections,
- each section name,
- each section start time in seconds,
- each section end time in seconds.

For the final section, you may leave the end time blank to mean "through the end of the file".

If you do not know timestamps, use `RUN_STANDARD` or `RUN_FULL` instead.

## Supported Audio

Supported file types:

- `.wav`
- `.mp3`
- `.flac`
- `.aiff`
- `.aif`

WAV is safest. MP3, FLAC, and AIFF may depend on local decoder support.

## Troubleshooting

### "AudioAtlas was not found"

AudioAtlas is not installed or is not available on your system PATH.
Install AudioAtlas first, or run the launcher from an activated environment.

### "No audio file found"

Put one supported audio file into `PUT_AUDIO_HERE`, then run the launcher again.

### More than one audio file

The launcher will ask you to choose by number.

### Permission denied on macOS

If macOS refuses to run the `.command` files, open Terminal in this folder and run:

```bash
chmod +x RUN_*.command
```

Then double-click the launcher again.

### Report was created but I do not know what to open

Open:

```text
REPORTS/<your_song>_<mode>/report.html
```

For section reports, open `section_index.md` or open `report.html` inside one of the section folders.

## What AudioAtlas Does And Does Not Do

AudioAtlas provides measurement and reporting context. It does not give mix scores, mastering advice, or automated pass/fail verdicts.

