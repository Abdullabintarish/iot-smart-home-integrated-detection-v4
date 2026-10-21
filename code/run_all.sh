#!/usr/bin/env bash
# End-to-end run on Linux/macOS: clean -> run manifest -> Stage 1 collection ->
# Stages 2-5 -> report + screenshots.
#
#   ./run_all.sh [raw-root] [extra run_pipeline args]
#
# Bash counterpart of run_all.ps1 (the Windows script used for the reported
# results). Defaults to data/raw_combined. Pass --skip-cv for a fast run, or
# nothing for full CV.
#
# NOTE: this script has NOT been executed in the current revision (the
# reported run used run_all.ps1 on Windows, and no bash was available to
# check it). Check its output before relying on it.
#
# WARNING: before Stage 1 the generated directories (data/interim,
# data/processed, results, models) are emptied so a stale intermediate from an
# earlier run cannot contaminate this one. The raw data under the raw root is
# never touched. Back up results/ first if you need the previous run.
set -euo pipefail

cd "$(dirname "$0")"

ROOT="${1:-data/raw_combined}"
if [ $# -gt 0 ]; then shift; fi

PY=.venv/bin/python
TRANSCRIPT_DIR=results/transcripts
STAGE1_LOG="$TRANSCRIPT_DIR/stage1_run.log"
RUN_LOG="$TRANSCRIPT_DIR/run_pipeline_run.log"
REPORT_LOG="$TRANSCRIPT_DIR/make_report_run.log"
INFO_LOG="$TRANSCRIPT_DIR/record_run_info_run.log"
RUN_ALL_LOG="$TRANSCRIPT_DIR/run_all.log"
export PYTHONIOENCODING=utf-8

stamp() { date -u +"%Y-%m-%d %H:%M:%S UTC"; }

# ---- clean stale intermediates (never the raw root) ------------------------
removed=()
for d in data/interim data/processed results models; do
    if [ -d "$d" ]; then
        for item in "$d"/* "$d"/.[!.]*; do
            [ -e "$item" ] || continue
            rm -rf -- "$item"
            removed+=("$item")
        done
    fi
done
mkdir -p "$TRANSCRIPT_DIR"

# From here on, everything printed also goes to results/transcripts/run_all.log.
exec > >(tee "$RUN_ALL_LOG") 2>&1

T0=$(date +%s)
echo "==> run_all started $(stamp)"
echo "==> Cleaned stale outputs: ${#removed[@]} item(s) removed"
for r in "${removed[@]+"${removed[@]}"}"; do echo "    removed $r"; done

# run_logged LOG ARGS... : run python, echo and write every line to LOG,
# framed by start/end times, exit code and runtime (same format as run_all.ps1).
run_logged() {
    local log="$1"; shift
    local t_start t_end code
    t_start=$(date +%s)
    echo "# start $(stamp): python $*" > "$log"
    set +e
    "$PY" -u "$@" 2>&1 | tee -a "$log"
    code=${PIPESTATUS[0]}
    set -e
    t_end=$(date +%s)
    echo "# end $(stamp): exit $code, runtime $((t_end - t_start))s" >> "$log"
    if [ "$code" -ne 0 ]; then
        echo "python $* failed (exit $code)"
        exit "$code"
    fi
}

echo "==> Run manifest (host, code and dataset hashes, config)"
run_logged "$INFO_LOG" record_run_info.py --raw "$ROOT"

echo "==> Stage 1: collecting from ${ROOT}"
run_logged "$STAGE1_LOG" stage1_collect.py --root "$ROOT"

echo "==> Stages 2-5: preprocess, correlate, detect, evaluate"
run_logged "$RUN_LOG" run_pipeline.py "$@"

echo "==> Report + screenshots"
run_logged "$REPORT_LOG" make_report.py --run-log "$RUN_LOG" --stage1-log "$STAGE1_LOG"

echo "==> run_all ended $(stamp); total runtime $(( $(date +%s) - T0 )) s"
echo "==> Outputs"
for p in results/run_manifest.json results/stage5_report.json \
         results/stage5_summary.txt results/baseline_vs_integrated.csv \
         results/fragmented_event_predictions.csv \
         results/integrated_event_predictions.csv \
         results/diagnostic_event_predictions.csv \
         results/report/REPORT.md results/transcripts; do
    if [ -e "$p" ]; then echo "    $p"; else echo "    $p  (missing)"; fi
done
