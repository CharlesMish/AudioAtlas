# Real AudioAtlas demo recordings

These three recordings are intentionally public musical inputs for trying
AudioAtlas on something more representative than a generated test tone. They
span a sparse live recording, a denser human-made arrangement, and the complete
AI-assisted trailer/demo track created for this project.

## AudioAtlas Demo

`audioatlas_demo.wav` is the 70.98-second AudioAtlas trailer/demo track and the
source for the project's live Midnight Studio report. Charles Mish assembled it
from multiple AI-assisted source generations created under a paid Suno
subscription, then edited, arranged, mixed, mastered, and post-processed the
finished recording for AudioAtlas.

It is published to reproduce AudioAtlas demonstrations, not as stock music or
a generally reusable standalone music asset. See the repository's
[audio rights notice](../../AUDIO_RIGHTS.md) for its distinct terms.

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
building a multi-track catalog beside the other recordings.

The arrangement embeds licensed Native Instruments/Kontakt content and may
include paid Splice kick/snare content. See the repository's
[audio rights notice](../../AUDIO_RIGHTS.md) before reusing the recording.

## Files and illustrative results

All three files are stereo, 44.1 kHz, PCM-16 WAV recordings.

| Track | File | Duration | SHA-256 |
|---|---|---:|---|
| AudioAtlas Demo | `audioatlas_demo.wav` | 70.98 s | `e1a7da67c45523beb8b39f5a6ac10560ff47a49297e517f39e87ba19fbae22de` |
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
