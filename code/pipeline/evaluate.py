"""Stage 5 - Risk mitigation assessment via baseline vs integrated comparison.

The thesis question is whether integrating and correlating logs *helps*. That is
only answerable by running the identical detector over two conditions:

  fragmented (baseline) : raw per-event features, per-source, no correlation
  integrated (proposed): Stage 3 incident features (correlated within each
                         source capture)

Both are scored on the same metric set from section 3.5, then differenced
(integrated - fragmented). Further Stage 5 checks: alert reduction per dataset
family, size-restricted and incident-majority-vote re-scoring, and an
incident-clustered percentile bootstrap.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RESULTS
from .correlate import _majority
from .detect import BENIGN, _slim, evaluate_split

COMPARISON_METRICS = ("accuracy", "precision_macro", "recall_macro", "f1_macro",
                      "fpr", "fnr")
LOWER_IS_BETTER = ("fpr", "fnr")
# Source-name prefix -> dataset family (IoT-23 captures vs Bot-IoT CSVs).
DATASET_FAMILIES = (("CTU-", "IoT-23"), ("data_", "Bot-IoT"))
BOOT_METRICS = ("accuracy", "f1_macro", "fpr", "fnr")


def comparison_table(fragmented: dict, integrated: dict) -> pd.DataFrame:
    """Side-by-side metrics, the raw difference (integrated - fragmented) and
    which condition scored better given the metric's direction."""
    rows = []
    for k in COMPARISON_METRICS:
        f, i = fragmented.get(k), integrated.get(k)
        delta, better = None, None
        if f is not None and i is not None and pd.notna(f) and pd.notna(i):
            delta = i - f
            if delta == 0:
                better = "tie"
            elif (delta < 0) == (k in LOWER_IS_BETTER):
                better = "integrated"
            else:
                better = "fragmented"
        rows.append({"metric": k, "fragmented": f, "integrated": i,
                     "difference": delta, "better": better,
                     "direction": "lower_is_better" if k in LOWER_IS_BETTER
                     else "higher_is_better"})
    return pd.DataFrame(rows)


def dataset_family(source: str) -> str:
    """IoT-23 for ``CTU-*`` captures, Bot-IoT for ``data_*`` CSVs, else other."""
    for prefix, name in DATASET_FAMILIES:
        if str(source).startswith(prefix):
            return name
    return "other"


def _reduction(events: int, incidents: int) -> dict:
    return {"events": int(events), "incidents": int(incidents),
            "alert_reduction": float(1 - incidents / max(1, events)),
            "mean_events_per_incident": float(events / max(1, incidents))}


def alert_reduction_by_dataset(incidents: pd.DataFrame) -> dict:
    """Alert reduction (1 - incidents / events) per source, per dataset family
    and overall, from the Stage 3 incident table (``source``, ``n_events``)."""
    inc = incidents.assign(source=incidents["source"].astype(str))
    per_src = inc.groupby("source", sort=True)["n_events"].agg(["sum", "size"])
    out: dict = {"family_rule": "IoT-23 = sources starting 'CTU-'; "
                                "Bot-IoT = sources starting 'data_'",
                 "per_source": {}, "per_dataset": {}}
    for src, r in per_src.iterrows():
        out["per_source"][src] = dict(_reduction(r["sum"], r["size"]),
                                      dataset=dataset_family(src))
    fam = per_src.groupby(per_src.index.map(dataset_family)).agg(
        events=("sum", "sum"), incidents=("size", "sum"), n_sources=("sum", "size"))
    for name, r in fam.iterrows():
        out["per_dataset"][name] = dict(_reduction(r["events"], r["incidents"]),
                                        n_sources=int(r["n_sources"]))
    out["overall"] = _reduction(per_src["sum"].sum(), per_src["size"].sum())
    out["overall"]["cross_source_incidents"] = (
        int((inc["cross_source"] > 1).sum()) if "cross_source" in inc else 0)
    return out


# --------------------------------------------------------------------------
# Robustness checks on the held-out predictions
# --------------------------------------------------------------------------
def _aligned(preds_frag: pd.DataFrame, preds_integ: pd.DataFrame
             ) -> pd.DataFrame:
    """One frame (event_id, incident_id, label, pred_fragmented,
    pred_integrated); raises unless both conditions cover the same events."""
    cols = ["event_id", "incident_id", "label", "pred"]
    f = preds_frag[cols].astype({"incident_id": str, "label": str, "pred": str})
    i = preds_integ[["event_id", "pred"]].astype({"pred": str})
    if len(f) != len(i) or not f["event_id"].is_unique \
            or set(f["event_id"]) != set(i["event_id"]):
        raise ValueError("conditions were not scored on the same events")
    df = f.rename(columns={"pred": "pred_fragmented"}).merge(
        i.rename(columns={"pred": "pred_integrated"}), on="event_id",
        how="inner", validate="one_to_one")
    return df.sort_values("event_id", kind="mergesort").reset_index(drop=True)


def incident_vote(df: pd.DataFrame, col: str) -> pd.Series:
    """Per-incident majority of ``df[col]`` with correlate's tie-break
    (count desc, benign first, then A-Z), indexed by incident_id."""
    counts = (df.groupby(["incident_id", col], sort=False).size()
              .rename("n").reset_index().rename(columns={col: "label"}))
    return _majority(counts)


def robustness(preds_frag: pd.DataFrame, preds_integ: pd.DataFrame,
               incidents: pd.DataFrame, max_incident_events: int = 10_000
               ) -> dict:
    """Two re-scorings of the same held-out predictions.

    (i) event-level metrics on events whose incident has at most
    ``max_incident_events`` events, so a few huge incidents cannot dominate;
    (ii) incident-level majority vote: one vote per test incident, true label
    = majority of its event labels, prediction = majority of the condition's
    event predictions, both with correlate's tie-break.
    """
    df = _aligned(preds_frag, preds_integ)
    size = (incidents.assign(incident_id=incidents["incident_id"].astype(str))
            .set_index("incident_id")["n_events"])
    n_ev = df["incident_id"].map(size)
    if n_ev.isna().any():
        raise KeyError("predictions reference incidents missing from the table")
    small = (n_ev <= max_incident_events).to_numpy()
    test_inc = df["incident_id"].unique()
    excl_inc = df.loc[~small, "incident_id"].unique()
    out: dict = {"small_incidents": {
        "rule": f"events in incidents with n_events <= {max_incident_events:,}",
        "max_incident_events": int(max_incident_events),
        "n_events_kept": int(small.sum()), "n_events_excluded": int((~small).sum()),
        "n_incidents_kept": int(len(test_inc) - len(excl_inc)),
        "n_incidents_excluded": int(len(excl_inc)),
    }}
    for cond in ("fragmented", "integrated"):
        sub = df[small]
        out["small_incidents"][cond] = _slim(evaluate_split(
            sub["label"], sub[f"pred_{cond}"])) if len(sub) else {}

    truth = incident_vote(df, "label")
    out["incident_majority_vote"] = {
        "rule": "one vote per test incident; true = majority of its event "
                "labels, pred = majority of the condition's event predictions "
                "(ties: count desc, benign first, then alphabetical)",
        "n_incidents": int(len(truth)),
    }
    for cond in ("fragmented", "integrated"):
        vote = incident_vote(df, f"pred_{cond}").reindex(truth.index)
        m = evaluate_split(truth, vote)
        out["incident_majority_vote"][cond] = dict(
            _slim(m), per_class={c: v["f1"] for c, v in m["per_class"].items()})
    return out


# --------------------------------------------------------------------------
# Incident-clustered bootstrap
# --------------------------------------------------------------------------
def _cluster_counts(df: pd.DataFrame, col: str, inc_codes: np.ndarray,
                    n_inc: int) -> tuple[list[str], np.ndarray]:
    """Per-incident confusion counts, shape (n_inc, k*k), for one condition;
    classes = sorted union of true and predicted labels (sklearn default)."""
    classes = sorted(set(df["label"]) | set(df[col]))
    code = {c: j for j, c in enumerate(classes)}
    k = len(classes)
    cell = df["label"].map(code).to_numpy() * k + df[col].map(code).to_numpy()
    flat = np.bincount(inc_codes * (k * k) + cell, minlength=n_inc * k * k)
    return classes, flat.reshape(n_inc, k * k).astype("float64")


def _metrics_from_counts(cm: np.ndarray, classes: list[str]) -> dict:
    """accuracy / macro F1 / FPR / FNR for a stack of confusion matrices
    (b, k, k), matching ``detect.evaluate_split`` with a fixed label set."""
    total = cm.sum(axis=(1, 2))
    tp = np.diagonal(cm, axis1=1, axis2=2)
    fp, fn = cm.sum(axis=1) - tp, cm.sum(axis=2) - tp
    denom = 2 * tp + fp + fn
    f1 = np.divide(2 * tp, denom, out=np.zeros_like(tp), where=denom > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = {"accuracy": tp.sum(axis=1) / total, "f1_macro": f1.mean(axis=1)}
        if BENIGN in classes:
            b = classes.index(BENIGN)
            n_benign = cm[:, b, :].sum(axis=1)
            n_attack = total - n_benign
            out["fpr"] = (n_benign - cm[:, b, b]) / n_benign
            out["fnr"] = (cm[:, :, b].sum(axis=1) - cm[:, b, b]) / n_attack
        else:
            out["fpr"] = np.full(len(cm), np.nan)
            out["fnr"] = np.zeros(len(cm))
    # Empty denominators are NaN, as in evaluate_split.
    return {k: np.where(np.isfinite(v), v, np.nan) for k, v in out.items()}


def _summary(values: np.ndarray, point: float) -> dict:
    ok = values[~np.isnan(values)]
    return {"point": float(point),
            "mean": float(ok.mean()) if len(ok) else float("nan"),
            "ci_low": float(np.percentile(ok, 2.5)) if len(ok) else float("nan"),
            "ci_high": float(np.percentile(ok, 97.5)) if len(ok) else float("nan"),
            "n_undefined": int(len(values) - len(ok))}


def cluster_bootstrap(preds_frag: pd.DataFrame, preds_integ: pd.DataFrame,
                      n_boot: int = 1000, seed: int = 42,
                      max_bytes: int = 256 * 2**20) -> dict:
    """Incident-clustered percentile bootstrap of accuracy, macro F1, FPR, FNR.

    Each replicate draws the test incidents with replacement (all events of a
    drawn incident come along); both conditions and their difference
    (integrated - fragmented) use the same draw. Replicate metrics come from
    summed per-incident confusion counts; the label set per condition is
    fixed to the full-test-set union. The weight matrix is built in batches
    so it stays under ``max_bytes``. This is a percentile confidence
    interval, NOT a significance test.
    """
    df = _aligned(preds_frag, preds_integ)
    inc_codes, inc_ids = pd.factorize(df["incident_id"], sort=True)
    n_inc = len(inc_ids)
    counts, point, reps = {}, {}, {}
    for cond in ("fragmented", "integrated"):
        classes, c = _cluster_counts(df, f"pred_{cond}", inc_codes, n_inc)
        counts[cond] = (classes, c)
        k = len(classes)
        point[cond] = {m: float(v[0]) for m, v in _metrics_from_counts(
            c.sum(axis=0).reshape(1, k, k), classes).items()}
        reps[cond] = {m: np.empty(n_boot) for m in BOOT_METRICS}
    rng = np.random.default_rng(seed)
    # Per batch: int64 draws + float64 weights, each (batch, n_inc).
    batch = int(max(1, min(n_boot, max_bytes // (16 * max(1, n_inc)))))
    for start in range(0, n_boot, batch):
        b = min(batch, n_boot - start)
        draw = rng.integers(0, n_inc, size=(b, n_inc))
        w = np.bincount((draw + n_inc * np.arange(b)[:, None]).ravel(),
                        minlength=b * n_inc).reshape(b, n_inc).astype("float64")
        del draw
        for cond, (classes, c) in counts.items():
            k = len(classes)
            m = _metrics_from_counts((w @ c).reshape(b, k, k), classes)
            for name in BOOT_METRICS:
                reps[cond][name][start:start + b] = m[name]
    out: dict = {
        "method": "incident-clustered bootstrap: test incidents resampled with "
                  "replacement, all events of a drawn incident included; "
                  "both conditions use the same draws",
        "interval": "95% percentile confidence interval (2.5th / 97.5th "
                    "percentiles of the replicates)",
        "note": "a percentile CI from a clustered bootstrap, NOT a "
                "significance test",
        "n_boot": int(n_boot), "seed": int(seed), "n_incidents": int(n_inc),
        "n_events": int(len(df)),
        "label_sets": {cond: counts[cond][0] for cond in counts},
    }
    for cond in ("fragmented", "integrated"):
        out[cond] = {m: _summary(reps[cond][m], point[cond][m])
                     for m in BOOT_METRICS}
    out["difference"] = {
        m: _summary(reps["integrated"][m] - reps["fragmented"][m],
                    point["integrated"][m] - point["fragmented"][m])
        for m in BOOT_METRICS}
    return out


def alert_reduction_summary(events: pd.DataFrame, incidents: pd.DataFrame) -> dict:
    """Quantify the correlation stage's compression ratio."""
    if events is None or len(events) == 0:
        return {}
    return {
        "raw_alerts": int(len(events)),
        "unified_incidents": int(len(incidents)) if incidents is not None else 0,
        "alert_reduction": float(1 - (len(incidents) / max(1, len(events)))),
        "mean_alerts_per_incident": float(len(events) / max(1, len(incidents))),
        "cross_source_incidents": int((incidents["cross_source"] > 1).sum())
        if incidents is not None and "cross_source" in incidents else 0,
    }


def save_report(fragmented: dict, integrated: dict, reduction: dict,
                results_dir: Path = RESULTS, extra: dict | None = None) -> dict:
    """Persist the Stage 5 deliverable: table, JSON and a plaintext summary.

    ``extra`` holds further top-level report sections (split, model config,
    incident-level metrics, diagnostics), stored as given.
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    table = comparison_table(fragmented, integrated)
    table.to_csv(results_dir / "baseline_vs_integrated.csv", index=False)

    def slim(d: dict) -> dict:
        """Make a result dict JSON-safe without discarding report inputs.

        The confusion matrix (an 8x8 integer grid) and the top-15 feature
        importances are both tiny, and ``pipeline.reporting`` needs them to draw
        the confusion and importance figures, so they are kept. Only the
        DataFrame is converted to plain records.
        """
        out = {}
        for k, v in d.items():
            if k == "feature_importance" and isinstance(v, pd.DataFrame):
                out[k] = v.to_dict(orient="records")
            else:
                out[k] = v
        return out

    report = {
        "fragmented": slim(fragmented),
        "integrated": slim(integrated),
        "alert_reduction": reduction,
        "comparison": table.to_dict(orient="records"),
    }
    for k, v in (extra or {}).items():
        report[k] = slim(v) if isinstance(v, dict) else v
    (results_dir / "stage5_report.json").write_text(
        json.dumps(report, indent=2, default=str))

    lines = ["Stage 5 - Cybersecurity Risk Mitigation Summary", "=" * 60]
    n_f, n_i = fragmented.get("n_test"), integrated.get("n_test")
    if n_f is not None and n_f == n_i:
        lines.append(f"Held-out events   : {n_f} (identical set for both "
                     "conditions)")
    acc_f, acc_i = fragmented.get("accuracy"), integrated.get("accuracy")
    if acc_f is not None and acc_i is not None:
        lines.append(f"Detection accuracy : {acc_f:.4f} -> {acc_i:.4f} "
                     f"({(acc_i - acc_f) * 100:+.2f} pp)")
    f_f, f_i = fragmented.get("f1_macro"), integrated.get("f1_macro")
    if f_f is not None and f_i is not None:
        lines.append(f"F1 (macro)        : {f_f:.4f} -> {f_i:.4f} "
                     f"({(f_i - f_f) * 100:+.2f} pp)")
    r_f, r_i = fragmented.get("fpr"), integrated.get("fpr")
    if r_f is not None and r_i is not None:
        lines.append(f"False-positive rate: {r_f:.4f} -> {r_i:.4f} "
                     f"({(r_i - r_f) * 100:+.2f} pp)")
    e_f, e_i = fragmented.get("fnr"), integrated.get("fnr")
    if e_f is not None and e_i is not None:
        lines.append(f"False-negative rate: {e_f:.4f} -> {e_i:.4f} "
                     f"({(e_i - e_f) * 100:+.2f} pp)")
    if reduction:
        lines.append(f"Alert reduction   : {reduction.get('alert_reduction', 0):.4f} "
                     f"({reduction.get('raw_alerts', 0)} alerts -> "
                     f"{reduction.get('unified_incidents', 0)} incidents)")
    lines.append(f"Baseline  train {fragmented.get('train_time_s', 0)}s on "
                 f"{fragmented.get('n_features') or 'n/a'} features")
    lines.append(f"Integrated train {integrated.get('train_time_s', 0)}s on "
                 f"{integrated.get('n_features', 0)} features")
    text = "\n".join(lines)
    (results_dir / "stage5_summary.txt").write_text(text)
    return report