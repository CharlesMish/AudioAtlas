# AudioAtlas public-release model

AudioAtlas uses one implementation and two Git-facing views.

## `main`: friendly public distribution

The public branch contains the code, tests, CI, license, user documentation,
examples, starter launchers, schemas, compatibility notes, and changelog. It is
the branch intended for people who want to understand, install, or contribute
to AudioAtlas without receiving the project's internal review machinery.

## `stewardship`: full project record

The stewardship branch is a superset used by the owner and trusted maintainers.
It keeps the project charter, review protocol, calibration operations, launcher
rehearsal evidence, agent task board, and other decision records.

The stewardship branch is not a second implementation. Code changes originate
there during active owner-directed development, then a deterministic public
snapshot is generated from the same commit. The public snapshot must pass the
same tests and build the same wheel.

Public candidate branches preserve the existing GitHub `main` history. The
exported tree is overlaid onto a branch created from the current `origin/main`;
the exporter does not create an orphan history or replace public ancestry.

## Why not maintain a separate lite fork?

A second codebase would invite measurement drift, duplicated fixes, and unclear
comparability. AudioAtlas instead keeps one analysis engine and exposes lighter
or richer report experiences through graph and presentation profiles:

- `compact` renders four plots but keeps the complete analysis summary;
- `standard` renders the normal report depth;
- `full` renders every registered plot;
- every HTML report can switch between the restrained **Focus** shell and the
  embellished **Studio** shell without changing data or plot pixels.

## Creating a public tree

From the stewardship checkout:

```bash
python scripts/export_public_tree.py --out ../AudioAtlas-public --zip ../AudioAtlas-public.zip
```

The exporter copies tracked files, excludes the stewardship-only paths declared
in the script, and writes a deterministic `PUBLIC_SNAPSHOT.json` containing the
source commit, package version, included-file count, and content hash. It then
runs the shared verifier before writing an optional ZIP. The manifest does not
hash itself: it is written after the exported file list is hashed.

Before publishing, verify:

```bash
python scripts/export_public_tree.py --out /tmp/AudioAtlas-public
python /tmp/AudioAtlas-public/scripts/verify_public_snapshot.py
cd /tmp/AudioAtlas-public
python -m pytest
python -m build
```

Public verification checks the complete included path set, per-file SHA-256
values, count, aggregate tree hash, format version, package version, and the
shape of `source_commit`. Only the owner-side exporter can also prove that
`source_commit` equals the stewardship commit used for generation; a public
checkout cannot infer that private source commit from its own Git history.

## Staging a public candidate

Fetch GitHub and create the candidate from the exact public base that was
reviewed. Abort if `origin/main` changed after review:

```bash
git fetch origin
git worktree add -b public/v0.2.0a6-linear \
  /tmp/AudioAtlas-public-candidate origin/main
rsync -a --delete --exclude=.git \
  /tmp/AudioAtlas-public/ /tmp/AudioAtlas-public-candidate/
git -C /tmp/AudioAtlas-public-candidate add -A
git -C /tmp/AudioAtlas-public-candidate commit -m \
  "Publish AudioAtlas v0.2.0a6"
```

Before pushing, confirm the candidate worktree is byte-identical to the export
apart from Git metadata, `origin/main` is an ancestor of the candidate, and the
diff contains the intended public additions, modifications, and deletions.
Push the candidate to a new review branch and use a normal pull request.

Do not use `--allow-unrelated-histories` and do not force-push `main` for a
normal public release. An older unrelated candidate may remain temporarily for
comparison, but it is not a merge source and should be deleted after the
linear-history pull request lands.

Native launcher and private musical-calibration evidence remain owner-side
records. Public documentation should report only the conclusions that are safe
and useful to users.
