# AudioAtlas alpha limitations

AudioAtlas `0.2.0a2` is a measurement and report-generation tool for structured
listening. It is not a mastering assistant or quality judge.

## Current limitations

- Finding thresholds are still calibrating on representative musical material.
- Approximate true peak is useful context, but standards-sensitive delivery
  decisions should be checked with a dedicated validated true-peak meter.
- Relative spectral and broad-band dB values are normalized within an analysis
  view. They are not calibrated dBFS and are not direct cross-song measures.
- Broad-band values are mean power per included FFT bin, not integrated total
  band energy.
- Absolute rolloff is technical context, not proof that expected content is
  missing.
- Onset activity does not measure punch, groove quality, or drum-hit count.
- Chroma does not detect key or chords.
- Lossy sources are measured after decoding. Peak/clipping observations do not
  establish what occurred in the original master.
- Batch discovery recognizes `.wav`, `.wave`, `.flac`, `.ogg`, `.aif`,
  `.aiff`, and `.mp3`; actual decoding depends on the local audio stack.
- The launcher kit requires a prior installation and PATH setup. Native
  Windows/macOS double-click behavior has not been claimed as fully rehearsed.
- The HTML note fields are temporary browser fields and are not saved.
- Full analysis runs for every graph profile; `minimal` only publishes fewer
  plots.

## Deliberately out of scope

- Scores, grades, automatic pass/fail, or mastering advice.
- Reference matching.
- Source, genre, instrument, or automatic section inference.
- Source separation.
- Cloud processing, accounts, telemetry, or hosted dashboards.
- Real-time playback, DAW sync, or plug-in architecture.

## Next evidence gates

- Deterministic edge fixtures and a documented rule ledger.
- Human calibration across authorized varied musical material.
- Continued installed-wheel and multi-platform CI evidence across supported
  dependency releases.
- Native launcher rehearsal before stronger ease-of-use claims.
- Real-use evidence before new analysis breadth or a GUI.
