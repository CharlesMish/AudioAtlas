"""Measure full/compact with identical plots, inputs, and DSP settings.

Run with the checkout's Python: python scripts/benchmark_compact.py INPUT --out DIR.
Cold-process means a new interpreter, not a flushed OS/Numba/disk cache. Warm
totals include the pipeline only; process totals include imports and startup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


def run_one(source: Path, out: Path, mode: str, end: float | None) -> dict:
    from audioatlas.analysis.bundle import _COMPUTE
    from audioatlas.graphs.selection import GraphSelection
    from audioatlas.pipeline import analyze_file

    original = dict(_COMPUTE)
    calls: dict[str, dict] = {}
    stages = {}

    def wrap(name, compute):
        def measured(*args, **kwargs):
            start = time.perf_counter()
            result = compute(*args, **kwargs)
            record = calls.setdefault(name, {"calls": 0, "seconds": 0.0})
            record["calls"] += 1
            record["seconds"] += time.perf_counter() - start
            return result
        return measured

    def progress(event):
        stages.setdefault(event.stage, time.perf_counter())
        if event.stage == "rendering":
            stages["rendering_end"] = time.perf_counter()

    try:
        _COMPUTE.update({name: wrap(name, compute) for name, compute in original.items()})
        start = time.perf_counter()
        result = analyze_file(source, out, analysis_mode=mode, end_seconds=end,
                              selection=GraphSelection(profile="compact"), progress_callback=progress)
        elapsed = time.perf_counter() - start
    finally:
        _COMPUTE.update(original)
    assert all(item["calls"] == 1 for item in calls.values())
    return {
        "mode": mode, "pipeline_seconds": elapsed,
        "compute_seconds": sum(item["seconds"] for item in calls.values()),
        "plot_seconds": stages["rendering_end"] - stages["rendering"],
        "families": calls, "family_count": len(calls),
        "summary_path": str(result.summary_path), "findings_path": str(result.findings_path),
    }


def check_parity(full: dict, compact: dict) -> None:
    a = json.loads(Path(full["summary_path"]).read_text())
    b = json.loads(Path(compact["summary_path"]).read_text())
    for key in b.keys() - {"schema_version", "analysis_execution", "analysis_provenance"}:
        assert a[key] == b[key], key
    pa, pb = dict(a["analysis_provenance"]), dict(b["analysis_provenance"])
    pa.pop("summary_schema_version")
    pb.pop("summary_schema_version")
    assert pa == pb
    fa = json.loads(Path(full["findings_path"]).read_text())
    fb = json.loads(Path(compact["findings_path"]).read_text())
    fb.pop("analysis_execution")
    assert fa == fb


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--end", type=float)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--worker", choices=("full", "compact"))
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(run_one(args.input, args.out, args.worker, args.end)))
        return
    if args.out.exists():
        parser.error("Use a new evidence directory")
    args.out.mkdir(parents=True)
    cold = {}
    for mode in ("full", "compact"):
        command = [sys.executable, str(Path(__file__).resolve()), str(args.input.resolve()),
                   "--out", str(args.out / f"process-{mode}"), "--worker", mode]
        if args.end is not None:
            command += ["--end", str(args.end)]
        start = time.perf_counter()
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        cold[mode] = json.loads(result.stdout)
        cold[mode]["process_seconds"] = time.perf_counter() - start
    check_parity(cold["full"], cold["compact"])
    warmup = {mode: run_one(args.input, args.out / f"warmup-{mode}", mode, args.end)
              for mode in ("full", "compact")}
    check_parity(warmup["full"], warmup["compact"])
    runs = []
    for index in range(args.repeats):
        order = ("full", "compact") if index % 2 == 0 else ("compact", "full")
        pair = {mode: run_one(args.input, args.out / f"pair-{index}-{mode}", mode, args.end)
                for mode in order}
        check_parity(pair["full"], pair["compact"])
        runs.append(pair)
    medians = {mode: {key: statistics.median(pair[mode][key] for pair in runs)
                      for key in ("pipeline_seconds", "compute_seconds", "plot_seconds", "family_count")}
               for mode in ("full", "compact")}
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted((root / "src/audioatlas").rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    report = {
        "platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "source_python_sha256": digest.hexdigest(), "end_seconds": args.end,
        "method": "New-process pair; excluded warmup pair; alternating warm pairs; identical compact graph profile and unchanged DSP defaults. No OS/disk/JIT cache flush.",
        "parity": "exact retained blocks, provenance signatures and findings in every pair",
        "cold_process": cold, "warmup": warmup, "warm_runs": runs, "warm_medians": medians,
    }
    (args.out / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"cold_process_seconds": {m: cold[m]["process_seconds"] for m in cold},
                      "warm_medians": medians, "parity": report["parity"]}, indent=2))


if __name__ == "__main__":
    main()
