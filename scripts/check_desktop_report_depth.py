#!/usr/bin/env python3
"""Check all desktop depth presets against source reports using a frozen app."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True, help="Frozen app executable")
    parser.add_argument("--output-parent", type=Path, required=True, help="New smoke directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests/fixtures/sine_1k_-6dbfs_2s.wav"
    app = args.app.resolve()
    output = args.output_parent.resolve()
    output.mkdir(parents=True, exist_ok=False)

    for depth, count in (("overview", 4), ("standard", 14), ("detailed", 18)):
        source = output / depth / "source"
        frozen_parent = output / depth / "frozen"
        subprocess.run(
            [sys.executable, "-m", "audioatlas", "analyze", str(fixture), "--out", str(source),
             "--report-depth", depth, "--theme", "default", "--presentation", "studio"],
            check=True,
            timeout=180,
        )
        command = [str(app), "--smoke-analyze", str(fixture),
                   "--output-parent", str(frozen_parent), "--report-depth", depth]
        subprocess.run(command, check=True, timeout=180)
        frozen = frozen_parent / f"AudioAtlas Report – {fixture.stem}"
        for name in ("summary.json", "findings.json"):
            assert json.loads((source / name).read_text()) == json.loads((frozen / name).read_text())
        plots = sorted(path.name for path in source.glob("*.png"))
        assert len(plots) == count
        assert sorted(path.name for path in frozen.glob("*.png")) == plots
        for name in plots:
            assert (source / name).read_bytes() == (frozen / name).read_bytes(), name
        for name in ("evidence_ranges.html", "evidence_ranges.md"):
            assert (frozen / name).is_file() == (depth == "detailed")
        html = (frozen / "report.html").read_text()
        assert ('id="evidence-index"' in html) == (depth == "detailed")
        if depth == "detailed":
            assert 'href="evidence_ranges.html#' in html
            assert "evidence_ranges.md" in (frozen / "report.md").read_text()
            note = frozen / "review-note.txt"
            note.write_text("Unowned file must survive a depth change.\n")
            command[-1] = "standard"
            subprocess.run(command, check=True, timeout=180)
            assert note.read_text() == "Unowned file must survive a depth change.\n"
            assert not (frozen / "evidence_ranges.html").exists()
            assert not (frozen / "evidence_ranges.md").exists()
        print(f"Desktop depth parity passed: {depth} ({count} plots)")


if __name__ == "__main__":
    main()
