"""Experiment E1: richer incident summaries (see RUN_LOG.md, RESULTS.md).

Same split, 300 s window, per-class training sample, RF settings and seeds as
the Run B ablation (experiments/ablation/run_ablation.py, imported unchanged).

    PYTHONPATH=code code/.venv/Scripts/python.exe -B \
        experiments/v4_extension/run_rich_incident.py runb windows loso

  runb     six conditions at 300 s, 5 seeds; reproduction gate; bootstrap;
           impurity importances
  windows  incident_rich and event_plus_rich at 60 s and 900 s, 5 seeds
  loso     leave-one-source-out (13 sources), RF, event_only / incident_rich /
           event_plus_rich, 5 seeds; sign-flip tests with Holm adjustment

Writes experiments/v4_extension/results/e1/ only.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "review"))
sys.path.insert(0, str(HERE.parent / "v3"))
import rich_features as F  # noqa: E402
import permuted_context as P  # noqa: E402  (unchanged; permute_context)
from stats_v3 import holm, sign_flip_p  # noqa: E402  (unchanged)

R = F.R
C = F.C
OUT = HERE / "results" / "e1"
ORIGINAL = HERE.parent / "ablation" / "results" / "full" / "ablation_results.csv"
V3_LOSO = HERE.parent / "v3" / "results" / "transfer" / "loso" / "metrics.json"
SEEDS = (42, 1, 2, 3, 4)
WINDOW = 300
SIDE_WINDOWS = (60, 900)
CONDITIONS = ("incident_thin", "incident_rich", "event_only", "event_plus_thin",
              "event_plus_rich", "event_plus_rich_permuted")
# condition -> (feature_set, window_s) in the saved ablation
GATE = {"incident_thin": ("incident_only", WINDOW), "event_only": ("event_only", 0),
        "event_plus_thin": ("event_plus_incident", WINDOW)}
BOOT = (("incident_rich", "incident_thin"), ("incident_rich", "event_only"),
        ("event_plus_rich", "event_only"), ("event_plus_rich", "event_plus_rich_permuted"))
LOSO_SETS = ("event_only", "incident_rich", "event_plus_rich")
TOL = 1e-12
log = R.log


class Data:
    """Run B events, event features and the label-free encodings used by E1."""

    def __init__(self):
        plan = C.DATA_OUT / "stage2_feature_plan.csv"
        self.feats = R.event_features(plan)
        log(f"loading events ({len(self.feats)} event features)")
        self.df = R.load_events(C.DATA_OUT / "stage3_events", self.feats)
        df = self.df
        self.y = df["label"].astype(str).to_numpy()
        self.split = df["split"].astype(str).to_numpy()
        self.source = df["source"].astype(str).to_numpy()
        self.train_all = np.flatnonzero(self.split == "train")
        self.test = np.flatnonzero(self.split == "test")
        self.shared = R.shared_features(df, self.feats)
        self.roles = F.feature_roles(plan, self.feats)
        cat = [f for f in self.shared if self.roles[f] == "categorical"]
        self.na = F.na_codes(df, cat)
        self.cats = F.category_sets(df, cat, self.na, self.split == "train")
        log(f"{len(df):,} events: {len(self.train_all):,} train, {len(self.test):,} test; "
            f"shared {self.shared}; na codes {self.na}")

    def rich(self, window: int, frame: pd.DataFrame | None = None) -> pd.DataFrame:
        return F.rich_incident_context(self.df if frame is None else frame, window,
                                       self.shared, self.roles, self.cats, self.na)


def per_class_rows(y, p, **tag) -> list[dict]:
    r = R.evaluate_split(pd.Series(y), pd.Series(p))
    return [{**tag, "class": c, **v} for c, v in r["per_class"].items()]


# --------------------------------------------------------------------------
# Run B design (300 s conditions and window sensitivity)
# --------------------------------------------------------------------------
class RunB:
    def __init__(self, d: Data):
        self.d = d
        df, test = d.df, d.test
        self.dup = np.isin(R._row_hash(df.iloc[test], d.feats),
                           R._row_hash(df.iloc[d.train_all], d.feats))
        self.samples = {s: R.sample_train(d.train_all, d.y, C.BUDGET.train_budget_per_class, s)
                        for s in SEEDS}
        self.y_test = d.y[test]
        (OUT / "preds").mkdir(parents=True, exist_ok=True)
        rows = pd.DataFrame({"event_id": df["event_id"].to_numpy()[test],
                             "source": d.source[test], "label": self.y_test,
                             "incident_id": df["incident_id"].astype(str).to_numpy()[test],
                             "novel_vector": ~self.dup})
        rows.to_parquet(OUT / "preds" / "runb_test_rows.parquet")
        self.classes = sorted(set(d.y))
        self.res_path, self.pc_path = OUT / "runb_results.csv", OUT / "runb_per_class.csv"
        self.rows = pd.read_csv(self.res_path).to_dict("records") if self.res_path.exists() else []
        self.pc = pd.read_csv(self.pc_path).to_dict("records") if self.pc_path.exists() else []
        self.importance = []

    def matrix(self, cond: str, window: int, seed: int, thin, rich) -> pd.DataFrame:
        d = self.d
        if cond == "event_only":
            return d.df[d.feats]
        if cond == "incident_thin":
            return thin
        if cond == "incident_rich":
            return rich
        if cond == "event_plus_thin":
            return pd.concat([d.df[d.feats], thin], axis=1)
        if cond == "event_plus_rich":
            return pd.concat([d.df[d.feats], rich], axis=1)
        if cond == "event_plus_rich_permuted":
            return pd.concat([d.df[d.feats],
                              P.permute_context(rich, d.split, d.source, seed)], axis=1)
        raise KeyError(cond)

    def run(self, cond, window, seed, X, sizes) -> list[dict]:
        d, t = self.d, time.perf_counter()
        p, imp = R.fit_predict(X, d.y, self.samples[seed], d.test, seed,
                               C.N_ESTIMATORS, C.BUDGET.n_jobs)
        benign = self.y_test == "benign"
        masks = {"all": np.ones(len(p), bool), "novel_vector": ~self.dup,
                 f"groups_le_{R.LARGE_GROUP}": sizes <= R.LARGE_GROUP,
                 "multi_event_benign": benign & (sizes > 1),
                 "single_event_benign": benign & (sizes == 1)}
        new = [{"window_s": window, "seed": seed, "condition": cond, "n_features": X.shape[1],
                "n_train": len(self.samples[seed]), **r}
               for r in R.score(self.y_test, p, masks)]
        self.rows.extend(new)
        self.pc.extend(per_class_rows(self.y_test, p, window_s=window, seed=seed, condition=cond))
        if cond == "incident_rich":
            self.importance.extend({"window_s": window, "seed": seed, "feature": f, "importance": v}
                                   for f, v in zip(X.columns, imp))
        pd.DataFrame({"pred": pd.Categorical(p, categories=self.classes)}).to_parquet(
            OUT / "preds" / f"runb_w{window}_{cond}_s{seed}.parquet")
        pd.DataFrame(self.rows).to_csv(self.res_path, index=False)
        pd.DataFrame(self.pc).to_csv(self.pc_path, index=False)
        log(f"  {cond:26s} w={window:<4d} s={seed:<3d} f1={new[0]['f1_macro']:.4f} "
            f"fpr={new[0]['fpr']:.4f} ({X.shape[1]} feats, {time.perf_counter() - t:.0f}s)")
        return new

    def gate(self, new_rows: list[dict]) -> dict:
        orig = pd.read_csv(ORIGINAL)
        mapped = []
        for r in new_rows:
            fs, w = GATE[r["condition"]]
            mapped.append({**r, "feature_set": fs, "window_s": w})
        cmp = P.compare_to_original(mapped, orig)
        return {"all_match": all(c["match"] for c in cmp), "rows": cmp}

    def context(self, window):
        log(f"window {window}s: building thin and rich context")
        t = time.perf_counter()
        thin = R.incident_context(self.d.df, window)
        rich = self.d.rich(window)
        log(f"  {rich.shape[1]} rich features, {rich.attrs['n_groups']:,} groups "
            f"({time.perf_counter() - t:.0f}s)")
        return thin, rich

    def main300(self) -> int:
        self.rows, self.pc, self.importance = [], [], []      # a runb run starts afresh
        thin, rich = self.context(WINDOW)
        sizes = thin["n_events"].to_numpy()[self.d.test]
        checks = {"n_events": len(self.d.df), "n_test": len(self.d.test),
                  "n_novel": int((~self.dup).sum()), "groups_at_300s": thin.attrs["n_groups"],
                  "shared_features": self.d.shared, "na_codes": self.d.na,
                  "category_sets": self.d.cats, "rich_features": list(rich.columns),
                  "rich_thin_equal": bool(np.array_equal(rich[R.INCIDENT].to_numpy(),
                                                         thin.to_numpy())),
                  "n_train_per_seed": {str(s): len(v) for s, v in self.samples.items()}}
        rich.iloc[:0].to_csv(OUT / "rich_feature_names.csv", index=False)
        # 1. gate: seed 42 reproduces the saved ablation
        s0 = SEEDS[0]
        g_rows = []
        for cond in GATE:
            g_rows += self.run(cond, WINDOW, s0, self.matrix(cond, WINDOW, s0, thin, rich), sizes)
        checks["gate_seed42"] = self.gate(g_rows)
        (OUT / "runb_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
        if not checks["gate_seed42"]["all_match"]:
            log("STOP: seed 42 does not reproduce the Run B ablation; see runb_checks.json")
            return 2
        log("gate passed: incident_thin, event_only, event_plus_thin (seed 42) match the ablation")
        # 2. all conditions x seeds
        for cond in CONDITIONS:
            for seed in SEEDS:
                if cond in GATE and seed == s0:
                    continue
                self.run(cond, WINDOW, seed, self.matrix(cond, WINDOW, seed, thin, rich), sizes)
        res = pd.DataFrame(self.rows)
        gated = res[(res.window_s == WINDOW) & res.condition.isin(GATE)].to_dict("records")
        checks["gate_all_seeds"] = self.gate(gated)
        imp = pd.DataFrame(self.importance)
        imp.to_csv(OUT / "importance_incident_rich_all.csv", index=False)
        top = (imp[imp.window_s == WINDOW].groupby("feature")["importance"]
               .agg(["mean", "std"]).sort_values("mean", ascending=False).head(20).reset_index())
        top.to_csv(OUT / "importance_incident_rich_top20.csv", index=False)
        self.bootstrap()
        (OUT / "runb_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
        return 0

    def bootstrap(self, reps=1000, seed=42):
        y = self.y_test
        ids = self.d.df["incident_id"].astype(str).to_numpy()[self.d.test]
        out = {}
        for a, b in BOOT:
            pa = pd.read_parquet(OUT / "preds" / f"runb_w{WINDOW}_{a}_s{SEEDS[0]}.parquet")["pred"].astype(str).to_numpy()
            pb = pd.read_parquet(OUT / "preds" / f"runb_w{WINDOW}_{b}_s{SEEDS[0]}.parquet")["pred"].astype(str).to_numpy()
            ma, mb = (R.evaluate_split(pd.Series(y), pd.Series(x)) for x in (pa, pb))
            log(f"bootstrap {a} minus {b}")
            out[f"{a}_minus_{b}"] = {
                "window_s": WINDOW, "seed": SEEDS[0], "boot_seed": seed,
                "cluster": "Run B incident_id", "f1_macro_point": ma["f1_macro"] - mb["f1_macro"],
                "fpr_point": ma["fpr"] - mb["fpr"],
                **R.paired_bootstrap(y, pa, pb, ids, sorted(set(y)), reps, seed)}
        (OUT / "runb_bootstrap.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    def windows(self):
        for w in SIDE_WINDOWS:
            thin, rich = self.context(w)
            sizes = thin["n_events"].to_numpy()[self.d.test]
            for cond in ("incident_rich", "event_plus_rich"):
                for seed in SEEDS:
                    self.run(cond, w, seed, self.matrix(cond, w, seed, thin, rich), sizes)
        pd.DataFrame(self.importance).to_csv(OUT / "importance_incident_rich_windows.csv", index=False)


def summarise():
    res = pd.read_csv(OUT / "runb_results.csv")
    g = res.groupby(["window_s", "condition", "subset"], sort=True)
    s = g.agg(runs=("seed", "nunique"), n=("n", "first"), f1_mean=("f1_macro", "mean"),
              f1_sd=("f1_macro", "std"), acc_mean=("accuracy", "mean"), acc_sd=("accuracy", "std"),
              fpr_mean=("fpr", "mean"), fpr_sd=("fpr", "std"), fnr_mean=("fnr", "mean"),
              fnr_sd=("fnr", "std")).reset_index()
    s.to_csv(OUT / "runb_summary.csv", index=False)
    pc = pd.read_csv(OUT / "runb_per_class.csv")
    pcs = pc.groupby(["window_s", "condition", "class"]).agg(
        f1_mean=("f1", "mean"), f1_sd=("f1", "std"), support=("support", "first")).reset_index()
    pcs.to_csv(OUT / "runb_per_class_summary.csv", index=False)


# --------------------------------------------------------------------------
# Leave-one-source-out
# --------------------------------------------------------------------------
def loso(d: Data) -> None:
    out = OUT / "loso"
    (out / "preds").mkdir(parents=True, exist_ok=True)
    df = d.df
    log("loso: building 300 s rich context (groups within source; split ignored, as v3)")
    allsplit = df.assign(split="all")
    rich = d.rich(WINDOW, allsplit)
    X = pd.concat([df[d.feats], rich], axis=1)
    sets = {"event_only": d.feats, "incident_rich": list(rich.columns),
            "event_plus_rich": d.feats + list(rich.columns)}
    frames = {k: X[v] for k, v in sets.items()}
    del X
    sources = sorted(np.unique(d.source))
    classes = sorted(set(d.y))
    folds = {s: (np.flatnonzero(d.source != s), np.flatnonzero(d.source == s)) for s in sources}
    order = np.concatenate([t for _, t in folds.values()])
    pos = np.empty(len(df), np.int64)
    pos[order] = np.arange(len(order))
    pd.DataFrame({"event_id": df["event_id"].to_numpy()[order], "source": d.source[order],
                  "label": d.y[order]}).to_parquet(out / "preds" / "loso_rows.parquet")
    rows = []
    for seed in SEEDS:
        acc = {k: np.empty(len(order), dtype=object) for k in sets}
        for fold, (tr, te) in folds.items():
            smp = R.sample_train(tr, d.y, C.BUDGET.train_budget_per_class, seed)
            for name in sets:
                t = time.perf_counter()
                p, _ = R.fit_predict(frames[name], d.y, smp, te, seed, C.N_ESTIMATORS,
                                     C.BUDGET.n_jobs)
                acc[name][pos[te]] = p
                r = R.evaluate_split(pd.Series(d.y[te]), pd.Series(p))
                rows.append({"fold": fold, "seed": seed, "set": name, "n_test": len(te),
                             "n_train": len(smp), **{k: r[k] for k in R.METRICS},
                             "n_benign": r["binary_counts"]["benign"]})
                pd.DataFrame(rows).to_csv(out / "loso_results.csv", index=False)
                log(f"  loso {fold[:28]:28s} s{seed:<2d} {name:16s} f1={r['f1_macro']:.4f} "
                    f"({time.perf_counter() - t:.0f}s)")
        for name, p in acc.items():
            pd.DataFrame({"pred": pd.Categorical(p.astype(str), categories=classes)}).to_parquet(
                out / "preds" / f"loso_{name}_s{seed}.parquet")
    loso_stats(out)


def loso_stats(out: Path) -> None:
    res = pd.read_csv(out / "loso_results.csv")
    fm = res.groupby(["fold", "set"])[["f1_macro", "fpr"]].mean().reset_index()
    wide = fm.pivot(index="fold", columns="set")
    wide.columns = [f"{m}_{s}" for m, s in wide.columns]
    wide.reset_index().to_csv(out / "loso_per_source.csv", index=False)
    stats = {"unit": "held-out source, seed-mean (n = 13)", "tests": {}}
    for metric in ("f1_macro", "fpr"):
        rows = []
        for x in ("incident_rich", "event_plus_rich"):
            a, b = wide[f"{metric}_{x}"], wide[f"{metric}_event_only"]
            ok = a.notna() & b.notna()
            dd = (a[ok] - b[ok]).to_numpy()
            rows.append({"x": x, "y": "event_only", "n": int(ok.sum()),
                         "mean_x": float(a[ok].mean()), "mean_y": float(b[ok].mean()),
                         "mean_diff": float(dd.mean()), "median_diff": float(np.median(dd)),
                         "folds_positive": int((dd > 0).sum()), "folds_negative": int((dd < 0).sum()),
                         "p_sign_flip": sign_flip_p(dd)})
        for r, adj in zip(rows, holm([r["p_sign_flip"] for r in rows])):
            r["p_sign_flip_holm"] = adj
        stats["tests"][metric] = rows
    stats["means"] = {c: float(wide[c].mean()) for c in wide.columns}
    if V3_LOSO.exists():                      # does event_only reproduce v3 rf_event_only?
        v3 = json.loads(V3_LOSO.read_text(encoding="utf-8"))
        cmp = []
        for r in res[res.set == "event_only"].itertuples():
            o = v3["runs"].get(f"rf_event_only|{r.seed}", {}).get(r.fold)
            if o is not None:
                cmp.append(abs(o["f1_macro"] - r.f1_macro) <= TOL)
        stats["event_only_matches_v3_rf_event_only"] = {"compared": len(cmp), "all_match": all(cmp)}
    (out / "loso_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    steps = (argv if argv is not None else sys.argv[1:]) or ["runb", "windows", "loso"]
    OUT.mkdir(parents=True, exist_ok=True)
    d = Data()
    if "runb" in steps or "windows" in steps:
        rb = RunB(d)
        if "runb" in steps:
            rc = rb.main300()
            if rc:
                return rc
        if "windows" in steps:
            rb.windows()
        summarise()
    if "loso" in steps:
        loso(d)
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
