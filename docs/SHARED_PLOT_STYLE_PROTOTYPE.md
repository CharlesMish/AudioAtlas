# Shared plot styling — isolated local prototype

This prototype addresses shared plotting behavior across the existing 25 themes.
It adds no skins or theme metadata and leaves the palette derivation, default,
and featured theme list unchanged. It is independently reviewable from any
future optional theme additions.

## Explicit roles

Line/bar/mark renderers resolve colors directly from the scoped theme palette;
conditional marks never consume implicit cycler positions.

| Role | Mapping | Examples |
|---|---|---|
| S1 | Palette entry 1 | Sample peak, centroid, mid, raw onset |
| S2 | Palette entry 2 | Rolloff 85%, side, smoothed onset |
| S3 | Palette entry 3 | Rolloff 95% |
| Waveform | S1 | Downsampled mono amplitude |
| RMS | S2 | Overlay, timeline, histogram, peak-versus-RMS |
| Event | S2 | Near-clipping circles and dashed threshold pair |
| Threshold | S3 | Clipping-threshold x marks and dotted threshold pair |
| Reference | Secondary text | Integrated loudness and zero/correlation references |
| Median | S2 | Reserved plot role; existing report distribution tokens unchanged |
| Fill | S2 at existing 0.2 opacity | Decorative RMS area with essential outline |
| Grid | Existing grid/border styling | Decorative grid and supplementary frequency guides |
| Labels | Secondary text | Essential axes, annotations, legends |

Existing continuous color maps, normalization, extents, units, threshold
locations, downsampling, and measured/derived arrays remain unchanged. Existing
line widths/patterns, marker shapes, and labels retain non-color distinctions.

## Composited contrast

Existing opacity debt affects multiple original themes: nominal raw-onset
contrast at alpha 0.45 was below 3:1 in 21 of 25 themes. The helper raises essential
mark opacity only as necessary toward a 3.1:1 nominal sRGB-composited target on
the axes panel, allowing margin for eight-bit channel rounding. Decorative fills
and grid retain their existing opacity; they do not need the data-mark threshold.

Legends use an opaque panel-colored background. Plot and legend strokes thereby
share the tested substrate instead of compositing over a different muted surface
or underlying data. Tests cover all existing themes against actual resolved
role colors and alpha after eight-bit compositing.

This intentionally changes pixels in Default, Midnight Studio, High Contrast
Clean, and other existing themes. RMS and waveform receive distinct roles;
conditional event marks keep stable identity; numerical reference lines become
neutral. These styling changes do not alter measured or plotted numeric data.

Nominal stroke-interior contrast is not a blanket accessibility claim.
Antialiased edges, intersecting series, color-vision differences, thin-line
perception, browser layout, and long-report reading still require human review.
Unique hex values do not establish perceptual distinguishability. External rc
styles used outside report themes may not reach the target even at full opacity.

## Validation and promotion

The external acceptance experiment renders the canonical complete report under
Default, Midnight Studio, and High Contrast Clean. It compares summary/findings
JSON and raw measurement plus actual plotted numerical-artist data against the
pre-styling integration baseline. Plot pixels intentionally change; data parity
is not inferred from images. Dense meshes are hashed by corner coordinates and
arrays without materializing millions of redundant paths.

No public snapshot is modified in this exploratory prototype. Regenerate the
snapshot if this change is promoted. No new plotting or screenshot tooling is
required.
