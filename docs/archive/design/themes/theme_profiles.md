# AudioAtlas Theme Profiles — Expanded Gallery Edition (Legacy)

> **Note:** The authoritative, implementation-ready version of all 25 themes is now in:
> - `all_themes.json`
> - `all_themes.md`

This file is kept for historical reference.

**Design-only artifact (v2).**  
This expands the previous exploration with 10 polished, calm, producer-friendly color profiles. The primary deliverable for interactive browsing is `theme_gallery.html` (self-contained, no dependencies). 

All themes are expressed via CSS custom properties compatible with the existing AudioAtlas `report.html` and `catalog.html` variable contract, plus the extended semantic tokens needed for:
- Priority badges ("check before delivery", "worth a listen", "for reference")
- Trait tags and pattern cards (catalog)
- Distribution visualizations (median tick + dots)
- Lightbox overlay

**Strict guardrails observed:** No Python, no src/, no tests/, no generated reports, no CLI changes, no network in any artifact.

## Core Design Principles (unchanged)
- Calm, readable, non-judgmental. Never traffic-light red/green.
- "Check before delivery" (issue) = distinct but calm (amber/ochre/warm gray).
- "Worth a listen" (warning) = neutral/curious (soft teal, indigo, slate, muted olive) — invites attention.
- "For reference" (info) = quiet, low-emphasis.
- High contrast suitable for long studio sessions.
- Works equally well for dense single-track reports and multi-track catalogs.
- Dark themes remain comfortable (no pure black, thoughtful shadows and accent brightness).
- No external fonts, images, CDNs, or JavaScript in the deliverables themselves (gallery uses only minimal inline JS for interactivity).

## The 10 Themes

See `theme_gallery.html` for the best interactive experience (click cards, modal with live components + full tokens + next/prev navigation).

See `theme_tokens.json` for the complete machine-readable token sets.

### 1. Default Refinement (recommended primary default)
Clean daylight studio. Precise, neutral, trustworthy.  
**Strengths:** Zero learning curve, excellent readability & print, safe for sharing.  
**Tradeoffs:** Can feel office-like in very creative/late-night contexts.  
**Recommended for:** Everyday use, client deliverables, bright rooms.  
**Accessibility:** High contrast after badge refinements (soft amber issue, curious teal warning).

### 2. Midnight Studio
Deep-focus dark control room. Quiet, technical, immersive.  
**Strengths:** Low eye strain for 3–4h sessions; modern studio feel.  
**Tradeoffs:** Not for bright environments.  
**Recommended for:** Night work, dim studios, dark-UI preferrers, long catalog reviews.

### 3. Warm Tape
Analog paper / vintage desk. Warm, human, comfortable.  
**Strengths:** Extremely restful; gorgeous in print; emotional "analog" connection.  
**Tradeoffs:** Narrower appeal; slightly softer contrast in bright light.  
**Recommended for:** Mixing notes, journals, acoustic work, printouts.

### 4. Studio Blue
Cool, precise, modern high-end control room (SSL/API vibe).  
**Strengths:** Strong pro personality; great density handling in catalogs.  
**Tradeoffs:** Cooler temperature can feel clinical to some.  
**Recommended for:** Technical/post/broadcast work, teams that like cool palettes.

### 5. Moss
Grounded, calm, slightly organic forest studio.  
**Strengths:** Very restful; unique but tasteful; pairs beautifully with acoustic/ambient.  
**Tradeoffs:** Narrowest appeal of the set.  
**Recommended for:** Personal calm workflows, nature/acoustic recordings.

### 6. High-Contrast Clean
Ultra-legible, bold, no-nonsense. Maximum clarity first.  
**Strengths:** Best readability in any lighting; strong hierarchy; accessibility-first.  
**Tradeoffs:** Can feel stark/clinical; less "warm".  
**Recommended for:** Presentations, outdoor viewing, accessibility needs, quick reference.

### 7. Soft Graphite
Elegant restrained almost-monochrome with cool accent. Content-forward.  
**Strengths:** Timeless, reduces visual noise, lets plots and numbers dominate.  
**Tradeoffs:** Low personality; accent must be used sparingly.  
**Recommended for:** Mastering, data-heavy reviews, users who want the UI to disappear.

### 8. Cream Notebook
Warm off-white paper, fountain-pen notes. Personal and inviting.  
**Strengths:** Comfortable for long sessions; excellent print; evokes careful listening.  
**Tradeoffs:** Warmth may not suit everyone.  
**Recommended for:** Personal journals, songwriting, acoustic focus, print.

### 9. Subtle Neon Studio (tasteful)
Modern dark studio with very restrained electric cyan accents.  
**Strengths:** Fresh contemporary feel without flashiness; good for electronic/hybrid genres.  
**Tradeoffs:** Accent is deliberately low-saturation.  
**Recommended for:** Synth/electronic/hybrid music; users who like dark modern UIs but reject harsh neon.

### 10. Dusk
Twilight calm — soft purple-gray with gentle lavender accents.  
**Strengths:** Serene, unique "evening" personality; bridges day/night.  
**Tradeoffs:** Purple undertone is polarizing (best as secondary option).  
**Recommended for:** Evening/low-light listening, ambient/experimental, wind-down reviews.

## Recommended Integration Set for Codex (4–6 themes)

If/when themes are wired into the generator, ship a small curated set:

1. **Default Refinement** (the safe universal default)
2. **Midnight Studio** (the essential dark mode)
3. **Warm Tape** (the warm/analog favorite)
4. **Studio Blue** (the cool technical option)
5. **Soft Graphite** or **High-Contrast Clean** (the minimal/legibility option)

This gives excellent coverage (light/dark, warm/cool, personality vs. restraint) without overwhelming users or the codebase.

## Notes for Future Implementation (Codex / engineers)

- The gallery and `theme_tokens.json` are the source of truth for token values.
- Each theme is fully defined by the ~27 CSS custom properties listed.
- The gallery's live previews demonstrate exactly which components must respond to which tokens (metric cards, findings with 3 priority classes, catalog patterns/traits, distribution viz, lightbox).
- Integration path (future): expose a `--theme` or `theme=` flag/setting that injects the chosen token set as a `<style>` block or `:root` override in generated HTML. The existing structural CSS already uses the var names (or can be updated to do so).
- Badge classes (`.priority-issue`, `.priority-warning`, `.priority-info`) and catalog classes (`.trait-tag`, `.pattern-count`, etc.) should read from the extended tokens so one profile themes everything.

## Bonus Fun Themes (Terminal / Hacker / Matrix styles)

Added in the latest round per request:

- **Terminal Green** — Classic bright green phosphor on deep black. Strong Matrix/hacker terminal energy.
- **Amber CRT** — Warm vintage amber terminal glow. Retro computing / old-school hacker CRT feel.
- **Cyan Terminal** — Dark navy base with bright electric cyan/blue accents. Clean modern cyber terminal.
- **Indigo Trim Terminal** — Dark terminal with purple accent trims and highlights on borders/edges.
- **Violet Terminal** — Deeper purple-tinted dark theme with a more immersive purple atmosphere.

These are more stylized and characterful than the core calm set. They work surprisingly well in the gallery preview and can be great for personal use or creative projects, even if they're not suitable as a default for general reports.

They are fully defined in both `theme_gallery.html` and `theme_tokens.json`.

### Latest Additions (bringing the total to 25)

- **Sepia Terminal** — Warm vintage sepia/brown terminal
- **Charcoal Gold** — Quiet luxury dark with subtle gold
- **Ocean Slate** — Cool professional blue-gray dark
- **Forest Ash** — Organic muted green-gray dark
- **Night Orchid** — Soft dreamy purple-gray
- **Desert Dust** — Warm terracotta/sand dark
- **Ice Slate** — Very cool crisp dark with icy highlights
- **Charcoal Rose** — Elegant charcoal with dusty rose/mauve
- **Solarized Dark (Calm)** — Refined, eye-friendly classic
- **Monochrome High Contrast** — Pure black & white, maximum clarity

This round mixes well-known reliable palettes (Solarized, high-contrast mono) with several fresh but sensible directions that still feel like they belong in the AudioAtlas world.
- Lightbox (added in prior work) already has dedicated tokens in these profiles.
- Keep the "no judgment" wording and calm semantics even when users switch themes.
- Provide a "custom" escape hatch using the JSON shape shown in the previous edition of this document (flat `tokens` object).

## How to Explore Right Now

1. Open `design/themes/theme_gallery.html` in any browser.
2. Click any theme card to open the interactive modal.
3. Use the live preview (real AudioAtlas-style components), read the full docs, browse the exact token values, and use Prev/Next to quickly compare 10 options.
4. The modal also has a "Copy tokens" helper for easy handoff to implementation work.
5. `theme_tokens.json` can be consumed by scripts or future tooling.

All artifacts remain 100% self-contained and respect the "song microscope" philosophy: factual, calm, listener-first.

---

*Expanded design exploration — no production code was touched.*