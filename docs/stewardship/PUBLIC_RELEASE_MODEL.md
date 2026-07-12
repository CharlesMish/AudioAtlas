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
source commit, package version, included-file count, and content hash.

Before publishing, verify:

```bash
python scripts/export_public_tree.py --out /tmp/AudioAtlas-public
cd /tmp/AudioAtlas-public
python -m pytest
python -m build
```

Native launcher and private musical-calibration evidence remain owner-side
records. Public documentation should report only the conclusions that are safe
and useful to users.
