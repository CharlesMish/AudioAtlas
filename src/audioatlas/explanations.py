"""Shared measurement explanations for human-readable reports.

These strings explain existing measurements; they do not define numerical behavior.
"""

ANALYZED_SCOPE_NOTE = (
    "Measurements describe the analyzed audio: the whole file or the selected range."
)
RANGE_TIME_NOTE = (
    "Times in plots and findings are relative to this analyzed range; "
    "add the source start time to locate the same point in the original file."
)

LR_BALANCE_CAPTION = (
    "Signed channel RMS difference over time: positive means Left higher RMS; "
    "negative means Right higher RMS. Gaps are undefined frames. "
    "This does not directly represent pan position or perceived balance."
)

GLOSSARY: list[tuple[str, str, str]] = [
    (
        "lr-balance", "L/R RMS balance",
        "20 log10(L_RMS / R_RMS), in dB, for exactly two channels. Positive means higher left "
        "RMS amplitude, negative means higher right RMS, and zero means equal RMS. Complete "
        "unwindowed frames use 4096 samples and hop 1024 by default; times mark frame centers "
        "relative to the analyzed audio. Each channel must meet the configured RMS floor "
        "(default -80 dBFS); otherwise the ratio is undefined with a channel-specific reason. "
        "The floor is an analysis limit, not a quality threshold. Mono and multichannel inputs "
        "are not applicable. Statistics exclude undefined frames. This does not establish pan "
        "position, perceived image position, loudness, a defect, or whether asymmetry is intentional.",
    ),
    (
        'lufs',
        'LUFS',
        'Integrated LUFS measures hearing-weighted loudness over the analyzed audio, including only '
        'the selected range when one is used. It gives delivery context, not a quality judgment.',
    ),
    (
        'short-term-lufs',
        'Short-term LUFS',
        'Short-term LUFS is a time-varying K-weighted loudness measurement using the configured '
        'window (3 seconds by default). Points mark window ends. It is distinct from RMS and '
        'integrated loudness.',
    ),
    (
        'true-peak',
        'Approximate true peak',
        'Approximate true peak estimates reconstructed peaks between samples. It is not a '
        'standards-grade true-peak measurement. Values above 0 dBTP can matter for playback, '
        'conversion, or encoding headroom.',
    ),
    (
        'sample-peak',
        'Sample peak',
        'Sample peak is the largest absolute decoded sample amplitude across all channels in the '
        'analyzed audio, expressed in dBFS. It is not loudness or a reconstructed intersample peak.',
    ),
    (
        'rms',
        'RMS',
        'RMS is root-mean-square signal amplitude, expressed in dBFS. The headline RMS pools samples across all channels; '
        'the RMS timeline uses their arithmetic-average mono signal, where opposing channels can '
        'cancel. Neither is hearing-weighted loudness.',
    ),
    (
        'crest-factor',
        'Crest factor',
        'Crest factor is sample-peak-to-RMS contrast in dB. Both the headline and each crest frame '
        'use all channels, unlike the mono RMS timeline. It describes measured peak contrast, not '
        'punch, quality, or dynamic range.',
    ),
    (
        'plr',
        'PLR',
        'PLR is approximate true peak minus integrated loudness. It describes the measured distance '
        'between those two values; it does not by itself identify compression, transient quality, '
        'or a delivery problem.',
    ),
    (
        'clipping',
        'Clipping / near-clipping',
        'Clipping counts samples at the configured ceiling; near-clipping counts samples close to '
        'it. Use the waveform and histogram to inspect where these samples occur.',
    ),
    (
        'stereo-correlation',
        'Stereo correlation',
        'Stereo correlation is Pearson r between left and right, from -1 to +1. +1 means matching '
        'variation, not necessarily equal levels; 0 means little linear correlation; negative '
        'values mean opposing variation. It does not directly measure perceived width or establish '
        'a phase defect.',
    ),
    (
        'side-mid-ratio',
        'Side/mid ratio',
        'Mid = (L + R) / 2 and side = (L - R) / 2. Their RMS ratio is expressed as side/mid dB: '
        'negative means mid-dominant, zero means equal RMS, and positive means side-dominant. '
        'Undefined ratios are not zero. This does not directly measure perceived width or isolate '
        'sources.',
    ),
    (
        'spectral-centroid',
        'Spectral centroid',
        'Spectral centroid is the magnitude-weighted mean frequency of each mono spectrum, in Hz. '
        'Higher values mean more weight at higher frequencies, not higher note pitch or an EQ '
        'recommendation.',
    ),
    (
        'rolloff',
        'Rolloff',
        'Spectral rolloff is the frequency in Hz below which 85% or 95% of summed spectral '
        'magnitude lies in a mono frame. It is not a filter cutoff or an audible-bandwidth '
        'estimate.',
    ),
    (
        'spectral-bandwidth',
        'Spectral bandwidth',
        'Spectral bandwidth is the magnitude-weighted root-mean-square frequency spread around the '
        'centroid, in Hz. Higher values mean more distributed spectral magnitude, not greater '
        'musical richness.',
    ),
    (
        'average-spectrum',
        'Average spectrum',
        'The Welch average spectrum describes the arithmetic-average mono signal over the analyzed '
        'audio. For measurable audio, 0 relative dB marks the strongest averaged bin at or above 20 '
        'Hz. Values describe shape within this analyzed view, not calibrated dBFS or absolute '
        'levels across files.',
    ),
    (
        'relative-band-power',
        'Relative mean band power',
        'This view averages spectral power per included FFT bin in each broad frequency band, then '
        'normalizes values within the file. It is not integrated total band energy and does not '
        'indicate absolute dBFS level.',
    ),
    (
        'onset-density',
        'Onset density',
        'Onset density is a smoothed onset-strength activity measure, not a count of events per '
        'second. Summary values retain the raw scale; each plotted curve is independently '
        'normalized to a maximum of 1 (or zero for no activity). It is not punch, groove quality, '
        'drum hits per second, or mix quality.',
    ),
    (
        'chroma-cqt',
        'Chroma CQT',
        'Chroma CQT shows normalized pitch-class energy, folded across octaves. Each nonzero frame '
        'is normalized to a maximum of 1. It is not exact note pitch (F0), tuning accuracy, key '
        'detection, or chord detection; values are not calibrated across unrelated songs.',
    ),
    (
        'relative-db',
        'Relative dB',
        'Relative dB plots show shape within this track. They are useful for shape within this '
        'track; not comparable to dBFS values from meters or other songs.',
    ),
]


def measurement_note(key: str) -> str:
    """Return the glossary wording shared by HTML and selective Markdown notes."""
    return next(text for glossary_id, _term, text in GLOSSARY if glossary_id == key)
