# AudioAtlas Theme Library — All 25 Presets (Implementation Ready)

**Status:** Design/Spec artifact only.  
**Purpose:** Normalized, ready-to-implement theme definitions for future integration into `report.html` and `catalog.html`.

All themes follow a single consistent token schema and are safe for static HTML embedding (hex + limited rgba only).

## Overview

- **Total themes:** 25
- **Recommended default:** `default`
- **Featured themes (8):** A balanced, production-safe starting set
- **Friend favorites (7):** Themes especially suitable for users who enjoy purple, indigo, dark studio, cyberpunk, or colorful-but-readable dark interfaces

## Theme Table

| ID | Display Name | Mood | Type |
|----|--------------|------|------|
| default | Default | Clean daylight studio | Light / Core |
| midnight_studio | Midnight Studio | Deep-focus after-dark control room | Dark |
| warm_tape | Warm Tape | Analog paper, vintage desk | Warm Light |
| studio_blue | Studio Blue | Cool, precise modern control room | Light |
| moss | Moss | Grounded, calm, organic | Light |
| high_contrast_clean | High-Contrast Clean | Ultra-clear, bold, maximum legibility | Light |
| soft_graphite | Soft Graphite | Elegant restrained monochrome | Light |
| cream_notebook | Cream Notebook | Warm off-white paper, fountain pen | Warm Light |
| subtle_neon_studio | Subtle Neon Studio | Modern dark with restrained electric accents | Dark |
| dusk | Dusk | Twilight calm, soft purple-gray | Light |
| terminal_green | Terminal Green | Classic hacker / Matrix green phosphor | Dark Terminal |
| amber_crt | Amber CRT | Vintage amber terminal glow | Dark Terminal |
| cyan_terminal | Cyan Terminal | Dark with bright electric cyan/blue | Dark Terminal |
| indigo_trim_terminal | Indigo Trim Terminal | Dark with purple accent trims | Dark Terminal |
| violet_terminal | Violet Terminal | Deep purple-tinted dark terminal | Dark Terminal |
| sepia_terminal | Sepia Terminal | Warm sepia/brown vintage terminal | Dark Terminal |
| charcoal_gold | Charcoal Gold | Quiet luxury dark with subtle gold | Dark |
| ocean_slate | Ocean Slate | Deep slate with cool ocean blue-gray | Dark |
| forest_ash | Forest Ash | Muted forest green-gray dark | Dark |
| night_orchid | Night Orchid | Soft purple-gray atmospheric dark | Dark |
| desert_dust | Desert Dust | Warm terracotta/sand dark | Dark |
| ice_slate | Ice Slate | Very cool dark slate with icy highlights | Dark |
| charcoal_rose | Charcoal Rose | Elegant charcoal with dusty rose | Dark |
| solarized_dark | Solarized Dark (Calm) | Refined, eye-friendly classic dark | Dark |
| monochrome_high_contrast | Monochrome High Contrast | Pure black & white, maximum clarity | Dark (High Contrast) |

## Recommendations

### Recommended Default
**`default`** — The safest, most universally usable starting point. Excellent readability, familiar to existing users, and already refined for non-alarmist badge semantics.

### Featured Themes (Recommended 8 for initial integration)
These provide strong coverage across light/dark, warm/cool, and personality levels:
- `default`
- `midnight_studio`
- `warm_tape`
- `studio_blue`
- `moss`
- `high_contrast_clean`
- `charcoal_gold`
- `solarized_dark`

### Friend Favorites
Themes that align particularly well with preferences for purple, indigo, dark studio, cyberpunk, or colorful-but-readable dark interfaces:
- `cyan_terminal`
- `indigo_trim_terminal`
- `violet_terminal`
- `night_orchid`
- `charcoal_rose`
- `subtle_neon_studio`
- `terminal_green`

## Token Schema

Every theme uses exactly this flat structure:

```json
{
  "bg": "...",
  "surface": "...",
  "surface_muted": "...",
  "text": "...",
  "text_muted": "...",
  "text_soft": "...",
  "border": "...",
  "border_soft": "...",
  "accent": "...",
  "accent_muted": "...",
  "chip_bg": "...",
  "callout_bg": "...",
  "callout_border": "...",
  "shadow_card": "...",
  "issue_bg": "...",
  "issue_text": "...",
  "issue_border": "...",
  "warning_bg": "...",
  "warning_text": "...",
  "warning_border": "...",
  "info_bg": "...",
  "info_text": "...",
  "info_border": "...",
  "trait_bg": "...",
  "trait_text": "...",
  "trait_border": "...",
  "pattern_accent": "...",
  "distribution_median": "...",
  "distribution_dot": "...",
  "lightbox_scrim": "...",
  "lightbox_surface": "..."
}
```

All values are either hex colors or (where semantically required) `rgba()` strings. No external references.

## Accessibility & Contrast Notes

- Most themes target WCAG AA or better for body text.
- Dark terminal themes (especially the colorful ones) were iteratively improved for readability on dark backgrounds.
- `monochrome_high_contrast` and `high_contrast_clean` are the strongest accessibility options.
- Several dark themes (Midnight, Cyan, Indigo Trim, Violet, Night Orchid, etc.) use significantly lightened text tokens (`#f8fafc`, `#cbd5e1`, etc.) after user feedback.

**Themes that may benefit from extra contrast review in implementation:**
- `subtle_neon_studio`
- `night_orchid`
- `charcoal_rose`
- Any very low-saturation dark themes when used with small text.

## Integration Notes for Codex / Future Implementation

1. `all_themes.json` is the single source of truth.
2. A future `--theme <id>` flag (or config) can select any of the 25.
3. The generator should inject the chosen theme's tokens as CSS custom properties (either in a `<style>` block or as a data attribute on `<html>` / body).
4. Existing report/catalog structural CSS should reference the variables (most already do, or can be easily updated).
5. Badge classes (`.priority-issue`, `.priority-warning`, `.priority-info`), trait tags, pattern cards, distribution elements, and lightbox should all read from the corresponding tokens.
6. The `default_theme`, `featured_themes`, and `friend_favorites` arrays can drive UI pickers or "recommended" sections in the CLI or settings.
7. Users who want custom themes can be supported later via the JSON shape described in earlier design docs.

## File Locations

- `design/themes/all_themes.json` — Normalized, implementation-ready library (25 themes)
- `design/themes/theme_gallery.html` — Interactive browser (updated to reference the full set)
- `design/themes/theme_tokens.json` — Legacy/raw source (kept for reference)
- Individual `theme_*.css` files — Still available for manual copy-paste into existing reports

All themes remain calm, producer-friendly, and avoid green/red judgment semantics.

---

*Prepared with love for future integration. Thank you for the kind words — I love working on this project with you too.*
