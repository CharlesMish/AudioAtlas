# Evidence Navigator v0.4 — Refinement C candidate

The accepted companion-ledger architecture remains Detailed-only. This candidate
combines the presence matrix and exact geometry; it does not add a graph, CLI
option, schema field, detector or evidence range. Overview/Standard remain
unchanged, with graph counts 4 / 14 / 18. The exhaustive inline writer option is
retired; no public toggle restores it.

## Three levels of precision

1. **Evidence by time window:** six navigation families × deterministic buckets.
   Every Present cell has equal visual weight. It indicates label overlap only,
   including ranges beginning earlier, never count, duration, severity, strength,
   corroboration or importance. Family links lead to precise lanes/definitions;
   presence links lead to companion time/family context.
2. **Exact original intervals:** one opaque equal-height SVG mark per original
   source interval. No union, snapping, retiming, minimum width or multiplicity
   encoding. Each spectral band keeps its own lane; correlation and mid/side
   remain separate. Source references and interpretation limits appear once in
   each lane's Meaning & limits disclosure. No active/starts/continues prose is
   repeated in the primary navigator.
3. **Complete evidence ledger:** `evidence_ranges.html` and `evidence_ranges.md`
   contain all canonical records, source identities and technical context.

## Label overlap and geometry

`NavigationBucket` contains original row IDs, not new evidence intervals. Buckets
are half-open: a row is present when `start < bucket.end` and `end > bucket.start`.
Original integration footprints are not consulted. Empty and continuation-only
windows are retained. The scale starts at 10 seconds and doubles until the
complete label domain fits within twelve buckets. It depends on duration, not
signal values. Legacy ends beyond decoded duration remain in that domain.

A 3–25 s interval produces one geometry mark and one canonical source record,
with presence in 0–10, 10–20 and 20–30 s. A 25 ms range retains its true width,
even if subpixel, and contributes the same binary presence as any other range.
No original label coordinates change. Exact-geometry row grouping is inherited
unchanged from v0.1; all origins remain individually recoverable.

The matrix is a categorical table: equal-width columns are navigation windows,
not a proportional time axis. Geometry lanes share the exact 0-to-domain time
scale. The final matrix column may represent a shorter window; its label states
that interval. Neither layer converts the other into new evidence.

## Native navigation and accessibility

Matrix cells use scoped table headers, accessible names and a shared boundary.
The matrix has at most 72 presence links (six families × twelve buckets).
A cell opens companion time/family context; a native disclosure reveals exact
source links; selecting one reaches its canonical record (three activations).
Geometry pointer shortcuts reach a record in one activation. They use
`tabindex=-1` so thousands of marks do not become sequential tab stops. Their
names retain source/type and displayed times, with reference/support descriptions.
The matrix/ledger route supplies keyboard-accessible exact text.

Table and geometry scroll horizontally on narrow screens. Every geometry lane
uses the same domain and 720px minimum axis width. Native graph/report backlinks
and disclosures work without JavaScript or remote assets. Markdown provides a
concise window/family table and links to exact geometry and both ledgers, without
repeating active/start/continuation columns.

## Companion behavior and ownership

Shared v0.3 navigation helpers and ledger context are reused as source changes,
not as ancestry. Canonical records appear once beneath their original start
window. Multiple navigation references may point to a long range, without
copying/clipping it into new records. Context distinguishes starts/continuations
only in the detail surface. Sticky headings, target outlines and scroll margins
retain location; print disables sticky behavior.

Companions retain the existing transactional output ownership contract. No new
filename or schema is added. Switching away from Detailed removes only owned
companions; unrelated files are never claimed. Relative local links contain no
source filesystem paths. Historical reports without companions remain readable.
Selected-range time labels remain slice-relative.

## Candidate history and review boundary

Parent is exact `cb1fd72e5bb3d5ea8137fa19d5c38a5ac67ae8f5`.
The alternative v0.3 commit `eb26d0a1cef5704e0051d9f82b77149e74467a6c`
is preserved separately. Its matrix-first default is not a prerequisite.

Static checks and exact parity establish technical validity, not visual approval.
The owner must judge whether combining matrix and geometry earns the additional
vertical/payload cost. No promotion is implied by this local prototype.
