"""Reviewer analysis 2: Run T boundary sensitivity (saved predictions only).

Run T cuts each source at its 75th timestamp percentile and appends the split
side to the correlation key, so a conversation group that spans the cut
becomes two incidents. A test event is a *boundary event* when its group key
without the split suffix (source, rule, src/dst/proto fields, 300 s bucket;
pipeline.correlate.correlation_key in incident mode) also has training
events. Boundary incidents are the test-side incidents of those groups.

Secondary definition (reported separately, labelled as such): the same key
without the time bucket, i.e. the flow is seen on both sides of the cut at
any time.

Metrics are recomputed from the saved Run T fragmented and integrated
predictions with pipeline.detect.evaluate_split. Nothing is retrained and
nothing under thesis_final_validation/ is written.

    PYTHONPATH=code code/.venv/Scripts/python.exe -B \
        experiments/review/boundary_sensitivity.py
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.correlate import correlation_key
from pipeline.detect import evaluate_split

HERE = Path(__file__).resolve().parent
RUN_T = HERE.parents[2] / "thesis_final_validation" / "supplementary_temporal" / "code"
COLS = ["ts", "src_ip", "dst_ip", "proto", "source", "split", "incident_id", "label"]
METRICS = ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr", "fnr")
WINDOW_S = 300
NO_BUCKET = 10 ** 12          # one bucket for any timestamp of these captures


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_events(path: Path) -> pd.DataFrame:
    files = sorted(Path(path).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no parquet files in {path}")
    df = pd.concat([pd.read_parquet(f, columns=COLS) for f in files], ignore_index=True)
    df["event_id"] = np.arange(len(df), dtype="int64")   # stream position, as Stage 4
    return df


def boundary_mask(df: pd.DataFrame, window_s: int = WINDOW_S) -> np.ndarray:
    """True for events whose split-free group key has both train and test events.

    Uncorrelatable (singleton) events have no key and are never boundary.
    """
    key, _, _ = correlation_key(df, window_s=window_s)
    split = df["split"].astype(str).to_numpy()
    codes = pd.factorize(key)[0]
    ok = codes >= 0
    n = codes.max() + 1 if ok.any() else 0
    has_tr = np.bincount(codes[ok & (split == "train")], minlength=n) > 0
    has_te = np.bincount(codes[ok & (split == "test")], minlength=n) > 0
    cut = has_tr & has_te
    out = np.zeros(len(df), bool)
    out[ok] = cut[codes[ok]]
    return out


def metrics(y: np.ndarray, p: np.ndarray, detail: list | None = None, **tag) -> dict:
    r = evaluate_split(pd.Series(y), pd.Series(p))
    if detail is not None:
        detail.append({**tag, "per_class": r["per_class"],
                       "classes": sorted(set(y) | set(p)),
                       "confusion_matrix": np.asarray(r["confusion_matrix"]).tolist()})
    return {"n": int(len(y)), **{k: r[k] for k in METRICS},
            **{f"n_{k}": v for k, v in r["binary_counts"].items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-t", type=Path, default=RUN_T)
    ap.add_argument("--out", type=Path, default=HERE / "results" / "boundary")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    ev_dir = a.run_t / "data" / "processed" / "stage3_events"
    res_dir = a.run_t / "results"

    log(f"loading Run T events from {ev_dir}")
    df = load_events(ev_dir)
    split = df["split"].astype(str).to_numpy()
    test = split == "test"
    log(f"{len(df):,} events, {int(test.sum()):,} test")

    key, _, _ = correlation_key(df, window_s=WINDOW_S)
    n_keys = int(key.nunique())
    n_key_split = int((key.astype("string") + "|" + df["split"].astype("string")).nunique())
    n_single = int(key.isna().sum())
    checks = {"run_t_dir": str(a.run_t), "n_events": len(df), "n_test": int(test.sum()),
              "run_t_incidents": int(df["incident_id"].nunique()),
              "split_free_groups_plus_singletons": n_keys + n_single,
              "groups_with_split_side_plus_singletons": n_key_split + n_single}

    bnd = boundary_mask(df)
    flow = boundary_mask(df, window_s=NO_BUCKET)
    checks["cut_groups"] = int(pd.factorize(key[bnd])[1].size)
    reports = json.loads((res_dir / "stage5_report.json").read_text(encoding="utf-8"))

    tables, counts, detail = [], {}, []
    for name in ("fragmented", "integrated"):
        f = res_dir / f"{name}_event_predictions.csv"
        log(f"reading {f.name}")
        pr = pd.read_csv(f, dtype={"incident_id": str, "source": str, "label": str,
                                   "split": str, "pred": str})
        if pr["event_id"].duplicated().any():
            raise ValueError(f"{f.name}: duplicate event_id")
        ev = df.iloc[pr["event_id"].to_numpy()]
        same = {c: bool((ev[c].astype(str).to_numpy() == pr[c].to_numpy()).all())
                for c in ("source", "incident_id", "split", "label")}
        checks[f"{name}_rows"] = len(pr)
        checks[f"{name}_join"] = same
        if not all(same.values()) or len(pr) != int(test.sum()):
            raise ValueError(f"{f.name} does not line up with the Run T event table: {same}")
        y, p = pr["label"].to_numpy(), pr["pred"].to_numpy()
        b = bnd[pr["event_id"].to_numpy()]
        fb = flow[pr["event_id"].to_numpy()]
        saved = {k: reports[name][k] for k in METRICS}
        allm = metrics(y, p)
        checks[f"{name}_all_matches_stage5_report"] = all(
            abs(allm[k] - saved[k]) <= 1e-12 for k in METRICS)
        for subset, m in (("all", np.ones(len(y), bool)),
                          ("excluding_boundary_groups", ~b),
                          ("boundary_groups_only", b),
                          ("secondary_excluding_flows_spanning_cut", ~fb)):
            tables.append({"condition": name, "subset": subset,
                           **metrics(y[m], p[m], detail, condition=name, subset=subset)})
        if name == "fragmented":
            inc = pr["incident_id"].to_numpy()
            counts = {
                "boundary_test_events": int(b.sum()),
                "boundary_test_incidents": int(pd.Series(inc[b]).nunique()),
                "test_incidents": int(pd.Series(inc).nunique()),
                "boundary_train_events": int((bnd & ~test).sum()),
                "secondary_flow_test_events": int(fb.sum()),
                "secondary_flow_test_incidents": int(pd.Series(inc[fb]).nunique()),
                "boundary_test_events_by_source_label": (
                    pr[b].groupby(["source", "label"]).size()
                    .rename("events").reset_index().to_dict("records")),
                "boundary_test_incidents_by_source": (
                    pr[b].groupby("source")["incident_id"].nunique()
                    .rename("incidents").reset_index().to_dict("records")),
                "test_events_by_label_all": pr["label"].value_counts().sort_index().to_dict(),
                "test_events_by_label_excluding": pr.loc[~b, "label"].value_counts()
                .sort_index().to_dict()}

    out = pd.DataFrame(tables)
    out.to_csv(a.out / "boundary_metrics.csv", index=False)
    (a.out / "boundary_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    (a.out / "per_class.json").write_text(json.dumps(detail, indent=2), encoding="utf-8")
    (a.out / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(out.to_string(index=False))
    print(json.dumps({k: v for k, v in counts.items() if not isinstance(v, (list, dict))}, indent=2))
    log(f"finished; results in {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
