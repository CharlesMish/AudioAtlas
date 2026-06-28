# AudioAtlas Alpha Limitations

AudioAtlas v0.2-alpha is a measurement and report-generation tool. It is useful
for structured listening and technical inspection, but it is not a mastering
assistant or quality judge.

## Current Limitations

- Findings are heuristic. Thresholds and wording are expected to change as more
  calibration material is tested.
- Approximate true peak uses oversampling and is useful context, but delivery
  decisions should still be checked with a dedicated true-peak meter.
- Relative dB plots are normalized to the strongest measured content in the
  track. They are not dBFS and should not be compared directly across songs.
- Onset density is an activity map. It does not measure punch, groove quality,
  drum hits per second, or production quality.
- Integrated loudness above -10 LUFS is delivery/headroom context, not a
  finding or verdict.
- Lossy files are analyzed after decoding. Clipping and peak observations
  describe decoded audio and do not prove what happened in the source master.
- Batch/catalog mode is descriptive. It does not rank, score, or recommend
  which tracks are better.

## Deliberately Out of Scope

- Mix score or mix-health grade.
- Automated mastering advice.
- Reference-track matching.
- Source separation or instrument identification.
- Section segmentation.
- Real-time playback, DAW sync, or cloud processing.

## Roadmap

- Batch/catalog mode refinements.
- Report UX improvements.
- Optional interactive view.
- More calibration testing across formats, genres, loudness ranges, and stereo
  styles.
