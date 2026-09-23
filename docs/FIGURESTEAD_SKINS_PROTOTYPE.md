# Optional Figurestead skins — local prototype T

T adds `lavender_fog_notebook` and `ultraviolet_laboratory`. It depends on the
separately reviewable shared plot-style prototype S; it does not change any S
renderer, opacity, or legend behavior. It is not a published-package availability
claim. Default, featured list, and all 25 existing theme definitions/palettes are
unchanged; existing-theme rendered pixels are expected to remain byte-identical
to S.

## Source and mapping

Figurestead source commit: `2fcff6c6f898ed96d9f1e6ab0c4eb915a3d9f0cd`, current
remote HEAD/main directly verified for this pass. Tokens were inspected from
`src/figurestead/themes/lavender_fog_notebook.json` and
`src/figurestead/themes/ultraviolet_laboratory.json`. Copied values are explicit;
there is no Figurestead runtime dependency.

Field maps to background, quiet chip/callout and badge surfaces. Panel maps to
cards, plot canvas, and lightbox surface. Label maps to body text; secondary maps
to essential small/muted text (faint is intentionally not used there). Primary
maps to accent; spine/grid supply borders. SummaryCore supplies distribution
median. Shadows and a black lightbox scrim at 0.88 opacity are AudioAtlas-specific
derivations.

Issue text uses series 4, warning series 3, info secondary, trait primary. Quiet
field-colored backgrounds avoid competing saturated blocks in long reports.
Existing category names, hierarchy, and finding semantics remain unchanged.

Optional `plot_series` metadata carries each skin's six exact source series
colors independently of UI severity tokens. The shared S role contract maps S1,
S2, S3 to its first three entries. Existing themes omit the metadata and retain
their original palette derivation. Metadata validates hex colors; explicit plot
palettes reject duplicates and insufficient opaque contrast. Hex uniqueness
alone is not a perceptual-distinguishability guarantee.

## Validation boundaries

S's dynamic shared-style tests also cover both new skins, including actual
alpha-composited panel/opaque-legend contexts after eight-bit rounding. T-specific
tests cover exact source series, UI/series independence, backward-compatible
absent metadata, and invalid palette rejection.

External acceptance renders the complete canonical report under Default,
Midnight Studio, Lavender Fog Notebook, and Ultraviolet Laboratory. Summary and
findings JSON plus raw measurements and actual plotted numeric data are compared
exactly against M/S. Default/Midnight PNGs are compared byte-for-byte against S.
No data parity claim is inferred from images.

Static plot inspection and numerical checks do not certify full HTML layout,
long-report fatigue, antialiased edges, curve intersections, color-vision
accessibility, or universal legibility. Default and Midnight remain available.

No public snapshot is regenerated for T. Regeneration is required if promoted.
Review T independently from S; its scope is optional skins and necessary palette
metadata only.
