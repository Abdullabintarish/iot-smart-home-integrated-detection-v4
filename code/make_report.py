"""Build the thesis evidence report from a completed pipeline run.

    python make_report.py [--run-log results/transcripts/run_pipeline_run.log] [--stage1-log ...]

Reads the artefacts a run already wrote (``results/stage5_report.json``) and
renders the Markdown report plus figures (including headless-Chrome terminal
screenshots) into ``results/report/``.

The defaults are the exact transcripts ``run_all.ps1`` produces
(``run_all.sh`` passes its own paths explicitly). Rendering from
any other log would draw a screenshot that disagrees with the numbers in the
report, so keep the pair in step when overriding either one.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline import config as C
from pipeline.reporting import build_report


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-log", type=Path,
                    default=C.RESULTS / "transcripts" / "run_pipeline_run.log",
                    help="transcript of the end-to-end run (same path run_all.ps1 writes)")
    ap.add_argument("--stage1-log", type=Path,
                    default=C.RESULTS / "transcripts" / "stage1_run.log",
                    help="optional Stage 1 collection transcript (same path run_all.ps1 writes)")
    args = ap.parse_args()

    report = json.loads((C.RESULTS / "stage5_report.json").read_text())

    transcripts: dict[str, str] = {}
    if args.run_log and args.run_log.exists():
        transcripts["run"] = _read(args.run_log)
    if args.stage1_log and args.stage1_log.exists():
        transcripts["stage1"] = _read(args.stage1_log)

    md = build_report(report, transcripts)
    print(f"report written: {md}")
    for p in sorted(md.parent.glob("fig_*.png")):
        print(f"  {p.name}  {p.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
