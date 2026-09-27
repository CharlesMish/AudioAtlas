# Evidence Navigator v0.2 — local presentation candidate

The navigator reads the unchanged `RangeIndex`; it adds no ranges or thresholds.
Detailed-only placement is unchanged: full computation + full graph profile.
Overview and Standard have no navigator/companions. No CLI flag, schema field,
graph-registry entry, or DSP dependency is added.

## Geometry and identity

One opaque, equal-height SVG rectangle is emitted per original source record,
including every origin of an exact-geometry ledger row. Its x and width are the
original start and end-minus-start in seconds. The domain includes legacy end
labels that extend beyond decoded duration; no mark is clipped or retimed.
There is no minimum data width, blend, opacity, intensity, or stacking-height
encoding of multiplicity. Short intervals can be subpixel; exact times remain
in the accessible chronological ledger and original JSON.

Navigation groups are Level / peak, Spectral shape, Spectral bands, Stereo,
Activity / onset and Findings. These names imply neither independence nor equal
importance. Each of the seven spectral bands keeps a separate lane; correlation
and M/S have separate stereo lanes. Source/type identities survive in accessible
labels and shared reference/support descriptions. Coincident marks can occlude
one another visually, but every original remains in the ledger and source JSON.

## Interaction without JavaScript

A pointer segment links directly to a chronological ledger row. Native graph
links bypass the ledger for measurement context. Native details expose reference
systems and interpretation limits. Segment links have accessible time/type labels
and `aria-describedby` references, but `tabindex=-1` avoids thousands of keyboard
stops; a normally focusable ledger link and chronological start-group links are
the keyboard route to every original range. Scrollable lanes are keyboard
focusable, use a 720px minimum time-axis width, and wrap labels on narrow screens.
This requires owner visual/assistive-technology acceptance, not just DOM checks.

Fixed start groups use 10 seconds up to 120 seconds of domain, then double the
step until no more than twelve temporal groups cover the domain. Empty groups
are omitted. Headers name families with ranges *starting* in the group; longer
ranges can start earlier. Groups are navigation, never detected musical sections.
This calculation depends only on duration, not signal values or range density.

## Two architectures

- Inline navigator + ledger: graph/row shortcuts above the expanded ledger in
  the same report. Preserves one-file reading but keeps the full ledger payload.
- Companion candidate (default): the main report contains the navigator and
  concise Markdown equivalent. `evidence_ranges.html` / `evidence_ranges.md`
  hold all original rows, reference notes and source links. HTML rows have no
  collapsed ancestors, so fragment destinations are visible without JavaScript.
  Backlinks return to the navigator and associated plots. The main report's
  plots, findings, references and ordinary navigation remain self-contained.

`navigator_layout` is a report-writer keyword for comparison harnesses, not a
new CLI option. Both prototypes use identical `RangeIndex` objects. Exact equal
interval grouping and all source records remain unchanged from v0.1.

Companions are optional explicitly owned outputs in the existing transactional
publisher. They never claim arbitrary same-named files; switching away from
Detailed removes only previously owned companions. Report paths remain local
relative filenames, with no embedded source filesystem paths. Older historical
reports lacking companions remain readable. See COMPATIBILITY.md.

## Acceptance boundary

Static DOM, geometry, contrast, ownership and numerical parity checks are
necessary but do not establish visual usability or assistive-technology behavior.
Owner review remains required if browser policy prevents local-file inspection.
