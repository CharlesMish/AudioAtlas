# Real AudioAtlas demo recordings

These two short recordings are intentionally public, human-made musical inputs
for trying AudioAtlas on something more representative than a generated test
tone. They make a useful pair: one is sparse and exposed, while the other is a
denser finished arrangement.

## Solo Guitar

`guitar.wav` is an informal solo-guitar performance recorded in a real room.
It is useful for seeing how AudioAtlas presents dynamics, spectrum, stereo, and
onset evidence when the source is sparse. The recording includes incidental
room noise and a little cat noise. That disclosure comes from the recording
context; AudioAtlas does not identify or detect the source of those sounds.

## Guitar, Koto, Cello & Drums

`guitar_koto_cello_drums.wav` is an original Charles Mish composition and a
finished New Recording. Charles wrote the music, performed the live material,
programmed and arranged the software-instrument parts, and recorded and mixed
the result. It is useful for exploring a fuller AudioAtlas report and for
building a two-track catalog beside the solo recording.

The arrangement embeds licensed Native Instruments/Kontakt content and may
include paid Splice kick/snare content. See the repository's
[audio rights notice](../../AUDIO_RIGHTS.md) before reusing the recording.

## Files and illustrative results

Both files are stereo, 44.1 kHz, PCM-16 WAV recordings.

| Track | File | Duration | SHA-256 |
|---|---|---:|---|
| Solo Guitar | `guitar.wav` | 13.77 s | `1ecba759cf090f06dc6446cba8ec392e2a10aeaa0dd2a6ad6e7b863a32ddc3b0` |
| Guitar, Koto, Cello & Drums | `guitar_koto_cello_drums.wav` | 26.30 s | `3735e5a3bf10d6038811643a65b2c6fde0a1cc704810fd73e843d568fc3c9d84` |

The following values illustrate one full-profile run with AudioAtlas `0.2.0a6`:

| Track | Integrated LUFS | True peak | PLR | Prioritized findings |
|---|---:|---:|---:|---:|
| Solo Guitar | -21.42 LUFS | -8.80 dBTP | 12.63 dB | 0 |
| Guitar, Koto, Cello & Drums | -13.98 LUFS | -0.013 dBTP | 13.97 dB | 0 |

The arrangement had five near-full-scale samples in that run, all below the
current prompt threshold. Measurements can vary with AudioAtlas version,
configuration, decoder, and scientific-library environment.

These are musical demonstrations, not deterministic golden fixtures,
threshold-calibration evidence, reference masters, or proof that finding rules
generalize. Listen and use the reports as descriptive maps.
