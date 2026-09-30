"""Platform-neutral entry point used to exercise frozen analysis engines."""

from __future__ import annotations

import argparse
from pathlib import Path


def run_frozen_smoke(argv: list[str]) -> None:
    from audioatlas.app_core import analyze_for_app
    from audioatlas.report_depth import REPORT_DEPTHS

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-analyze", type=Path, required=True)
    parser.add_argument("--output-parent", type=Path, required=True)
    parser.add_argument("--report-depth", choices=tuple(REPORT_DEPTHS), default="standard")
    args = parser.parse_args(argv)
    result = analyze_for_app(
        args.smoke_analyze, output_parent=args.output_parent, report_depth=args.report_depth,
    )
    if not result.html_report_path.is_file():
        raise SystemExit("Frozen smoke did not produce report.html")
