# AudioAtlas Static HTML Report Mockup (Refined)

This directory contains a **design-only** static HTML prototype for a possible future `report.html` output.

**Refined:** design-only task — no changes were made to the analysis pipeline, CLI, tests, schemas, or any Python code. Only `design/report_mockup.html` and this README were edited.

## Files
- `report_mockup.html` — the complete, self-contained mockup (embedded CSS only, no external dependencies, minimal inline JS limited to graceful image fallback).
- This README.

## Major refinements in this version (for Codex implementation reference)
- All 10 plot cards now use real `<img src="0N_....png">` elements exclusively (no SVG proxies or text placeholders for the visuals).
- Simple persistent fallback caption under every plot image: “If image missing: place this HTML in the same folder as the real PNGs from an AudioAtlas run.”
- Findings changed from dense 2-column grid to a clean **vertical one-column list** (stacked cards). This significantly improves scanability and readability for long reports with many findings.
- The four wide/detailed plots (Log-Frequency Spectrogram, Welch Average Spectrum, Band Energy Timeline, Onset Density Timeline) now span the full available width via the `.plot-card-wide` class. This gives the important visual maps breathing room and better readability on long pages.
- Added a simple top navigation row with anchor links: **Findings · Plots · Technical details · Human notes**. Helps users jump quickly in long reports.
- Added a prominent but calm “How to read this report” callout near the top (exact wording requested). Sets expectations immediately.
- Human notes textareas now have completely neutral/blank placeholders (no suggestive example text such as “Lows feel consistent…” or “Maybe a gentle cut…”). Labels remain; content areas are ready for user input only.
- All other calm, professional styling, embedded CSS, guardrails, and data fidelity preserved.

## How to view the mockup with real plots
1. Copy `report_mockup.html` into any real output directory that already contains the PNGs, e.g.:
   - `reports/calibration/dittoguitar/`
   - `reports/aster_after_findings_cleanup/`
   - or any other `reports/<name>/` folder that has `01_waveform_rms.png` … `10_onset_density.png`
2. Open the copied HTML file directly in a browser.

The image `src` attributes exactly match the filenames the pipeline produces.

## Layout sections (current)

1. **Header** — Track filename, exact subtitle, metadata chips, plus the new top navigation row.

2. **How to read this report callout** — Short, prominent guidance box (new in this refinement).

3. **Key metric cards** — Same 9 cards as before.

4. **Findings** — Now a vertical one-column list of cards (changed for long-report readability). Severity badges, category, title, evidence, “Why it matters”, “Suggested checks”, time-range summaries, and suppression note all retained.

5. **Plots** — 
   - Compact grid for the first six plots.
   - Four wide plots (spectrogram, average spectrum, band energy timeline, onset density) rendered full-width below for better visual inspection.
   - Every plot uses a real `<img>` + filename + description + fallback caption. No proxies.

6. **Technical details** — Same set of `<details>` collapsibles.

7. **Human notes** — Four neutral `<textarea>` boxes with blank placeholders.

## Design choices & rationale (updated)

- **Real images first** — The mockup is now structured exactly as a production `report.html` should be (real relative `<img>` tags). Proxy graphics were removed so Codex sees the intended final DOM.
- **Readability for long reports** — Vertical findings list + full-width wide plots + top nav + upfront “How to read” callout are direct responses to the goal of improving usability when there are many findings or dense visual data.
- **Graceful degradation** — Persistent simple fallback caption under every image (no reliance on complex JS or broken-image icons alone).
- **Strictly static & local** — Still 100% embedded CSS + minimal onerror only for images. No CDNs, no build, no external assets.
- **Tone & wording** — Unchanged guardrails compliance.
- **Neutral notes area** — Placeholders contain no content that could be mistaken for advice or examples.
- **Anchor navigation** — Lightweight and native; improves the experience precisely when the page becomes long.

## What this mockup is *not*
- Not a replacement for the current Markdown report
- Not a feature request or implementation ticket
- Not a comparison tool, scorer, or anything that violates the “song microscope” framing

The mockup continues to be built directly from real `summary.json` + `findings.json` structures so the numbers and finding shapes remain faithful.

No source code was modified in any way.