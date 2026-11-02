"""Stage 4 features, one row per Zeek conn record.

Only information at or before the connection's start time ``ts`` is used:
DNS and alert features count records of the same local host with
``ts - WINDOW_S <= record ts <= ts``. Labels, IP addresses and raw timestamps
are never features (see ``FORBIDDEN``).
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from common import WINDOW_S, local_host

CONN_NUMERIC = ("duration", "orig_bytes", "resp_bytes", "missed_bytes",
                "orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes",
                "id.resp_p")
CONN_CATEGORICAL = ("proto", "service", "conn_state")
DNS_FEATURES = ("dns_query_count", "dns_unique_domains", "dns_nxdomain_count",
                "dns_mean_query_len")
ALERT_BASE = ("alert_count", "alert_max_severity")
FORBIDDEN = ("label", "detailed_label", "cls", "y", "ts", "uid", "id.orig_h",
             "id.resp_h", "id.orig_p", "community_id", "src_ip", "dest_ip",
             "signature", "signature_id", "capture", "incident_id", "host")


def _num(s: pd.Series) -> np.ndarray:
    return pd.to_numeric(s.replace("-", np.nan), errors="coerce").to_numpy(float)


def _window_bounds(ev_ts: np.ndarray, q_ts: np.ndarray, w: int):
    lo = np.searchsorted(ev_ts, q_ts - w, side="left")
    hi = np.searchsorted(ev_ts, q_ts, side="right")
    return lo, hi


def dns_features(conn: pd.DataFrame, dns: pd.DataFrame, w: int = WINDOW_S) -> pd.DataFrame:
    out = pd.DataFrame(0.0, index=conn.index, columns=list(DNS_FEATURES))
    if dns is None or dns.empty:
        return out
    d = pd.DataFrame({
        "host": [local_host(a, b) for a, b in zip(dns["id.orig_h"], dns["id.resp_h"])],
        "ts": dns["ts"].astype(float),
        "q": dns["query"].replace("-", "").fillna("").str.lower(),
        "nx": (dns.get("rcode_name", pd.Series("", index=dns.index)) == "NXDOMAIN").astype(float)})
    hosts = pd.Series([local_host(a, b) for a, b in
                       zip(conn["id.orig_h"], conn["id.resp_h"])], index=conn.index)
    cts = conn["ts"].astype(float)
    for h, dh in d.groupby("host", sort=False):
        idx = hosts.index[hosts == h]
        if len(idx) == 0:
            continue
        dh = dh.sort_values("ts", kind="mergesort")
        ets = dh["ts"].to_numpy()
        qlen = dh["q"].str.len().to_numpy(float)
        has_q = (qlen > 0).astype(float)
        cum = lambda a: np.concatenate([[0.0], np.cumsum(a)])  # noqa: E731
        c_n, c_nx, c_len, c_hq = cum(np.ones(len(dh))), cum(dh["nx"].to_numpy()), cum(qlen), cum(has_q)
        q = cts.loc[idx].to_numpy()
        lo, hi = _window_bounds(ets, q, w)
        out.loc[idx, "dns_query_count"] = c_n[hi] - c_n[lo]
        out.loc[idx, "dns_nxdomain_count"] = c_nx[hi] - c_nx[lo]
        nq = c_hq[hi] - c_hq[lo]
        out.loc[idx, "dns_mean_query_len"] = np.where(nq > 0, (c_len[hi] - c_len[lo]) / np.maximum(nq, 1), 0.0)
        # Distinct domains in a sliding window: two pointers over queries in ts order.
        qs = dh["q"].to_numpy()
        order = np.argsort(q, kind="mergesort")
        cnt: Counter = Counter()
        L = R = 0
        uniq = np.zeros(len(q))
        for j in order:
            while R < hi[j]:
                if qs[R]:
                    cnt[qs[R]] += 1
                R += 1
            while L < lo[j]:
                if qs[L]:
                    cnt[qs[L]] -= 1
                    if cnt[qs[L]] == 0:
                        del cnt[qs[L]]
                L += 1
            uniq[j] = len(cnt)
        out.loc[idx, "dns_unique_domains"] = uniq
    return out


def alert_categories(train_alerts: pd.DataFrame, k: int = 10) -> list[str]:
    """Top-k alert categories in TRAINING alerts only (fixed before testing)."""
    if train_alerts is None or train_alerts.empty:
        return []
    return list(train_alerts["category"].fillna("none").value_counts().index[:k])


def alert_columns(categories: list[str]) -> list[str]:
    return list(ALERT_BASE) + [f"alert_cat_{i}" for i in range(len(categories))] + ["alert_cat_other"]


def alert_features(conn: pd.DataFrame, alerts: pd.DataFrame, categories: list[str],
                   w: int = WINDOW_S) -> pd.DataFrame:
    cols = alert_columns(categories)
    out = pd.DataFrame(0.0, index=conn.index, columns=cols)
    if alerts is None or alerts.empty:
        return out
    cat_idx = {c: i for i, c in enumerate(categories)}
    a = pd.DataFrame({
        "host": [local_host(s, t) for s, t in zip(alerts["src_ip"], alerts["dest_ip"])],
        "ts": alerts["ts"].astype(float),
        # Suricata severity 1 = highest; score 4 - severity so larger = worse.
        "sev": 4 - pd.to_numeric(alerts["severity"], errors="coerce").fillna(3).clip(1, 3),
        "cat": alerts["category"].fillna("none").map(lambda c: cat_idx.get(c, -1))})
    hosts = pd.Series([local_host(x, y) for x, y in
                       zip(conn["id.orig_h"], conn["id.resp_h"])], index=conn.index)
    cts = conn["ts"].astype(float)
    for h, ah in a.groupby("host", sort=False):
        idx = hosts.index[hosts == h]
        if len(idx) == 0:
            continue
        ah = ah.sort_values("ts", kind="mergesort")
        lo, hi = _window_bounds(ah["ts"].to_numpy(), cts.loc[idx].to_numpy(), w)
        cum = lambda v: np.concatenate([[0.0], np.cumsum(v)])  # noqa: E731
        out.loc[idx, "alert_count"] = hi - lo
        best = np.zeros(len(idx))
        for s in (1, 2, 3):
            c = cum((ah["sev"].to_numpy() == s).astype(float))
            best = np.where(c[hi] - c[lo] > 0, s, best)
        out.loc[idx, "alert_max_severity"] = best
        cat = ah["cat"].to_numpy()
        for i in range(len(categories)):
            c = cum((cat == i).astype(float))
            out.loc[idx, f"alert_cat_{i}"] = c[hi] - c[lo]
        c = cum((cat == -1).astype(float))
        out.loc[idx, "alert_cat_other"] = c[hi] - c[lo]
    return out


def conn_frame(conn: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=conn.index)
    for c in CONN_NUMERIC:
        f[c] = _num(conn[c])
    for c in CONN_CATEGORICAL:
        f[c] = conn[c].astype(str)
    return f


class Preprocessor:
    """Fitted on training rows only: categorical vocabularies, missing -> -1."""

    def __init__(self, max_levels: int = 30):
        self.max_levels = max_levels
        self.vocab: dict[str, list[str]] = {}
        self.columns: list[str] = []

    def fit(self, df: pd.DataFrame, numeric: list[str], categorical: list[str]):
        self.numeric, self.categorical = list(numeric), list(categorical)
        for c in self.categorical:
            self.vocab[c] = list(df[c].value_counts().index[: self.max_levels])
        self.columns = self.numeric + [f"{c}={v}" for c in self.categorical
                                       for v in self.vocab[c]] + \
            [f"{c}=__other__" for c in self.categorical]
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        parts = [df[self.numeric].to_numpy(float)]
        for c in self.categorical:
            vals = df[c].to_numpy()
            parts.append(np.column_stack([(vals == v) for v in self.vocab[c]]
                                         + [~np.isin(vals, self.vocab[c])]).astype(float))
        X = np.hstack(parts)
        return np.where(np.isfinite(X), X, -1.0)
