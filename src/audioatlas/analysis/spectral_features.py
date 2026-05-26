"""Higher-order spectral features.

Status: STUB (v0.2 target). Not wired into the pipeline yet.

Planned content:

- ``SpectralCentroidResult`` - per-frame centroid (Hz) over time.
- ``SpectralRolloffResult`` - per-frame rolloff (Hz) at a configurable
  percentile (default 85%).
- ``compute_spectral_centroid(y, sr, config)``
- ``compute_spectral_rolloff(y, sr, config, percentile=0.85)``

These should both delegate to ``librosa.feature.*`` rather than rolling
custom DSP - librosa's implementations are well-tested and standard.

Required when implementing:

1. Define dataclasses with frozen=True. Include ``sample_rate`` on each
   for parity with ``SpectrogramResult``.
2. Both functions take ``y`` as ``(n_samples, n_channels)`` and downmix
   internally with ``audioatlas.utils.to_mono``.
3. Reuse ``cfg.n_fft`` and ``cfg.hop_length`` so the time axes line up
   with the spectrogram exactly.
4. Add ``to_summary_dict()`` returning median + IQR of the time series.
5. Add tests in ``tests/test_spectral_features.py`` using a known signal
   (a sine at 1 kHz should have centroid ~1 kHz; pink-ish noise should
   have rolloff lower than white noise).
6. Add plot under ``audioatlas/visualize/spectral_features.py``.
7. Wire into ``pipeline.py``.

See ``docs/AGENT_TASKS.md`` (T-004).
"""

from __future__ import annotations

__all__: list[str] = []
