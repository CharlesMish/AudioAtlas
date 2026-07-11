# AudioAtlas launcher kit for an installed environment

This folder provides double-click launchers after AudioAtlas has already been
installed and the `audioatlas` command is available. It is not yet a standalone
installer or a PATH-independent application.

## Before using the launchers

Ask the person setting up the computer to verify:

```text
audioatlas --version
```

Then place one supported audio file in `PUT_AUDIO_HERE/`. The launchers find
WAV/WAVE, FLAC, OGG, AIFF/AIF, or MP3 files (when the local decoder supports
that format) and write a report folder beside this README.

## Report choices

- `RUN_MINIMAL`: compact 4-plot report. It runs the same full analysis as the
  other profiles; it only writes fewer PNGs.
- `RUN_STANDARD`: default 14-plot report.
- `RUN_FULL`: 17-plot report with extra distribution/detail views.
- `RUN_SECTIONS_PROMPTED`: asks for manual source ranges. AudioAtlas does not
  detect song sections automatically.

All launchers use share-safe metadata defaults. Generated JSON stores source
basenames rather than resolved usernames and folder paths.

## Current setup boundary

The launchers call the installed `audioatlas` command. Native Finder,
Gatekeeper, Windows shell, PATH, spaces, and non-ASCII filename behavior still
need platform rehearsal before this kit should be advertised as one-click
nontechnical installation. The first analysis on a fresh installation may take
longer while the scientific libraries initialize; keep the launcher window open.
Use `LAUNCHER_REHEARSAL_LOG.md` to record a native test.
