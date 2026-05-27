# AudioAtlas model review prompt

I’m building AudioAtlas, a local audio-analysis/reporting tool for music creators.

I uploaded a review package containing:
- project docs
- schema/docs
- report mockup
- calibration report outputs
- findings.json / summary.json / report.md / plot PNGs
- calibration context explaining what some tracks actually are

Raw audio is intentionally excluded.

Please do not write Python implementation code. This is a product/UX/report-language/spec review.

Core product framing:
AudioAtlas is a “song microscope.” It generates measurement-based listening prompts, visual maps, and technical observations for one song at a time. It should not judge tracks as good/bad, professional/amateur, AI/non-AI, or score the mix. It should not give prescriptive “fix this” mastering advice.

What I want help with:
The tool now produces a lot of useful measurements, but some metrics are hard to interpret without context. I want the reports to be useful to musicians/producers/mix engineers, including people who are not DSP experts.

Please review the package and help with five things:

## 1. Metric explanation framework

For each metric, provide:
- plain-English explanation
- what higher/lower values often imply
- what it does NOT mean
- how to interpret it within one song
- how it could be interpreted across a calibration folder / catalog
- suggested listening checks

Metrics:
- Integrated LUFS
- true peak
- sample peak
- RMS
- PLR
- clipped / near-clipping samples
- stereo correlation
- side/mid ratio
- spectral centroid
- spectral rolloff
- spectral bandwidth
- average spectrum
- band energy
- onset density
- relative dB / track-normalized plots

Special note on onset density:
Please be especially clear here. My current confusion is: I understand that onset density should be higher in a percussion/vocal-driven song than in a pad-heavy song, but I do not know how to interpret one track’s onset density versus another track’s onset density. Make clear that it is an attack/activity map, not a direct measure of “punch” or mix quality.

## 2. Calibration-folder concept

I like the idea of analyzing a folder of tracks — maybe an album, a creator’s catalog, or old mixes over time.

Please propose a calibration-folder summary concept that avoids ranking or scoring tracks.

Ideas to explore:
- catalog medians/ranges
- per-track technical fingerprints
- “this track is above/below your folder median”
- album consistency
- changes over time
- loudness/headroom spread
- stereo-field spread
- spectral balance spread
- transient/onset activity spread
- outliers without implying better/worse

## 3. Findings refinement

Review the findings style and propose improvements.

Please identify:
- findings that are high-value
- findings that may be noisy or too eager
- findings that should be grouped
- findings that should move to technical details
- findings that need better wording
- findings that need more context
- any thresholds/heuristics that seem hard to justify

Important:
Do not use words like bad, good, amateur, professional, AI, broken, fix, score.
Use phrases like:
- suggested checks
- listening prompts
- technical footprint
- relative to this track
- relative to this folder/catalog

## 4. Static HTML report UX

Review the static HTML mockup and propose improvements.

Focus on:
- first-time musician readability
- report section order
- metric cards
- finding cards
- plot order
- glossary/tooltips/explainer text
- how to avoid overwhelming users
- how to make the report useful without turning it into a judgment engine

Please suggest specific copy blocks that could be inserted into the report.

## 5. Deliverables

Please produce:
- a concise executive summary
- recommended report structure
- metric glossary copy
- recommended finding wording patterns
- calibration-folder dashboard concept
- example language for 5–10 common findings
- a prioritized “change next” list

Please stay conceptual/spec-oriented. Do not implement code.