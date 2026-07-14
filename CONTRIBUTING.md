# Contributing to AudioAtlas

AudioAtlas accepts focused bug fixes, tests, and documentation improvements.
Please keep measurement or finding-rule changes separate and explain their
evidence and compatibility impact.

## Setup and checks

AudioAtlas requires Python 3.11 or newer. With `uv` installed:

```bash
uv venv
uv sync --extra dev
uv pip install -e .
```

Run the complete source checks before proposing a change:

```bash
uv run python -m pytest
uv run ruff check .
uv run make check
```

Mypy is not currently an enforced project check. An initial whole-package run
found substantial pre-existing application typing work and scientific-library
stub gaps; contributions should not imply a type-safety gate that CI does not
run.

## Build and artifact checks

Build both distributions and validate their metadata:

```bash
uv run python -m build
uv run --with twine python -m twine check dist/*
```

The test suite contains an artifact regression that builds a clean sdist and
checks its deliberately demo-free test contract. CI also extracts the finished
sdist and runs every test it contains, then installs and smokes the wheel.

Run the committed golden fixture without regenerating it:

```bash
uv run audioatlas analyze tests/fixtures/sine_1k_-6dbfs_2s.wav \
  --out /tmp/audioatlas-golden-report --graphs-profile compact
```

## Public snapshot

Verify a public checkout or extracted public source artifact with:

```bash
uv run python scripts/verify_public_snapshot.py
```

Regeneration is owner-side because `source_commit` identifies the stewardship
commit that produced the public view. From a committed stewardship checkout:

```bash
uv run python scripts/export_public_tree.py \
  --out /tmp/AudioAtlas-public --zip /tmp/AudioAtlas-public.zip
uv run python /tmp/AudioAtlas-public/scripts/verify_public_snapshot.py \
  /tmp/AudioAtlas-public
```

Do not hand-edit `PUBLIC_SNAPSHOT.json`. Generate it only after every covered
file has reached its final content.
