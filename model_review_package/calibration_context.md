# AudioAtlas calibration context

These tracks are provided as report outputs only. Raw audio is intentionally excluded from this review package.

## What AudioAtlas is

AudioAtlas is a local “song microscope” for music creators. It generates measurement-based listening prompts, visual maps, and technical observations for one audio file at a time.

**It should not:**
- Judge tracks as good/bad/professional/amateur
- Score mixes
- Identify AI-generated content
- Give prescriptive mastering advice (“fix this”, “you need more compression”)

The human using the report decides what (if anything) the measurements mean for their creative goals.

## Track context (for calibration only)

The following notes are provided solely so reviewers understand the provenance of the calibration set. They are not part of the product.

- **aster** — AI-generated (Suno). Relatively clean and conservative production.
- **bunnyparty** — Professionally produced / viral-ish reference track (with music video/animation context).
- **DC_kMM_Censored** — Most-worked-on human mix by the author (~30 instruments, heavy automation). Created after several years of Ableton hobby work. May still legitimately trigger some warnings.
- **dittoguitar** — Older/sloppier cover/mix. Useful as a “rougher” calibration case.
- **sufjanm** — Oldest mix in the set. Expected to surface the most obvious technical issues.
- **rept** — Intentionally distorted/loud aesthetic, short/quick mix. Distortion is at least partly deliberate; may still benefit from headroom/delivery checks.
- **jarmedley** — AI-generated / postmodern style. Possible interesting stereo movement or hook-like elements.
- **Malone_Doja_BOL4_iKon_medley** — More recent human mix/cover/medley. Likely more efficient and controlled than older work.
- **hurt3** — Cover/mix; possibly smaller/drier production.
- **sufjandry** — Cover/mix; possibly dry/wide.
- **birdcansing** — Calibration track; exact category/context uncertain from available notes.
- **Prompt_Architect__Toking_On_Tokens** — AI or AI-adjacent calibration track; exact context uncertain.

## Important calibration lesson

Some findings can be technically accurate yet highly context-dependent.

Examples:
- Brief stereo-correlation dips can come from intentional panning, hi-hats, vocal throws, delays, hooks, or stereo FX — not necessarily a “problem.”
- Loud or heavily distorted tracks may be *intentionally* loud/distorted for artistic reasons, yet the tool can still usefully surface true-peak or headroom data for delivery formats.
- Onset density, spectral centroid, etc. are maps and fingerprints, not direct quality scores.

The tool’s job is to surface measurable fingerprints clearly and humbly. The user supplies the artistic context.

## Questions for reviewers

- How should the report explain potentially confusing metrics (onset density, PLR, stereo correlation, side/mid ratio, spectral centroid/rolloff/bandwidth, average spectrum, band energy, relative dB / track-normalized plots) to non-DSP experts?
- How can a “calibration folder” or catalog view help a creator understand their own body of work without creating a ranking or scoring system?
- Which current findings feel most useful vs. noisy or in need of better wording/context?
- What should a static HTML report contain (or avoid) to be genuinely understandable and non-intimidating to working musicians and producers?

Raw audio is deliberately omitted so this package can be shared freely for review across different models and humans.