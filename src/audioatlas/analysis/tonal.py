"""Tonal analysis (chroma).

Status: STUB (v0.2 target). Not wired into the pipeline yet.

Planned content:

- ``ChromaCqtResult`` - 12-bin chromagram over time, plus aggregated
  pitch-class energy.
- ``compute_chroma_cqt(y, sr, config)`` - thin wrapper over
  ``librosa.feature.chroma_cqt``.

This is *descriptive* only - AudioAtlas does not attempt key detection
in v0.1 or v0.2. The plot is the deliverable; any "this song is in C minor"
claim would violate the no-verdict rule in AGENT_BRIEF.md.

Required when implementing:

1. Define result dataclass with frozen=True, including ``sample_rate``.
2. Downmix to mono before calling librosa.
3. Test that a pure A4 (440 Hz) sine produces a clear peak in the A
   chroma bin and that the chromagram has shape (12, n_frames).
4. Plot at ``audioatlas/visualize/chroma.py``.

See ``docs/AGENT_TASKS.md`` (T-005).
"""

from __future__ import annotations

__all__: list[str] = []
