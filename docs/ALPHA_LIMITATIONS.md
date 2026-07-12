# AudioAtlas alpha limitations

AudioAtlas `0.2.0a5` is a measurement and report-generation tool for structured
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
- A fresh environment can have a noticeable first-analysis initialization
  delay from the scientific Python stack. Lightweight discovery commands avoid
  importing that stack, but report generation still requires it.
- The `0.2.0a5` dependency contract temporarily constrains Numba to
  `>=0.65.1,<0.66`. A clean Python 3.13 smoke with Numba 0.66.0 /
  llvmlite 0.48.0 stalled in LLVM code generation; the same workflow
  completed with Numba 0.65.1 / llvmlite 0.47.0. This ceiling should be
  revisited only after a clean report smoke on the newer line.
- The HTML note fields are temporary browser fields and are not saved.
- Full analysis runs for every graph profile; `compact` and its legacy
  `minimal` alias only publish fewer plots. Focus/Studio presentation changes
  the HTML shell and never changes measurements or plot pixels.
- Same-track identity is a user assertion. Matching hashed `--track-id` tokens
  do not recognize audio or prove that two files contain the same composition.
  Hashing omits plaintext from the artifact but does not protect a short token
  from guessing or prevent reused tokens from linking separate reports.
- Revision deltas are only as comparable as their recorded configuration, code,
  dependency, decoder, and environment fingerprints. Even an exact recorded
  signature is not a guarantee of bit-identical floating-point output.
- `--allow-incomparable` exists for forensic inspection, not routine comparison;
  its output remains explicitly caveated.
- Prompt appearance/disappearance in a revision diff is source-attributable only
  when the recorded finding-rule implementation and ruleset version also match.
- Calibration replay runs current finding logic over saved summaries. It does
  not reopen audio, test changed measurement code, or replace human listening.
- Measured plot alt text is a concise summary, not a substitute for the complete
  image, technical table, or listening check.

## Deliberately out of scope

- Scores, grades, automatic pass/fail, or mastering advice.
- Cross-track reference matching, ranking, or preferred-revision selection.
- Source, genre, instrument, or automatic section inference.
- Source separation.
- Cloud processing, accounts, telemetry, or hosted dashboards.
- Real-time playback, DAW sync, or plug-in architecture.

## Next evidence gates

- Deterministic edge fixtures and a documented rule ledger.
- Human calibration across authorized varied musical material.
- Frozen-ledger rule replay and adjudication for any candidate finding change.
- Continued installed-wheel and multi-platform CI evidence across supported
  dependency releases.
- Native launcher rehearsal before stronger ease-of-use claims.
- Real-use evidence before new analysis breadth or a GUI.
