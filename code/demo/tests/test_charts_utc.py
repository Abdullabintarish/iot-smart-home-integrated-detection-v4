"""Every temporal Altair encoding renders in UTC; chart layout specs.

Vega-Lite draws temporal fields in the browser's local time zone unless the
scale is ``utc`` (or a ``utc*`` timeUnit is used). The tables show UTC
strings, so the charts must too.
"""
import unittest

import numpy as np
import pandas as pd

from _common import HAS_STREAMLIT, ensure_cache, ev


def _encodings(spec):
    """Yield every ``encoding`` dict anywhere in a Vega-Lite spec."""
    if isinstance(spec, dict):
        if isinstance(spec.get("encoding"), dict):
            yield spec["encoding"]
        for v in spec.values():
            yield from _encodings(v)
    elif isinstance(spec, list):
        for v in spec:
            yield from _encodings(v)


def _is_utc(fd: dict) -> bool:
    return (fd.get("scale", {}).get("type") == "utc"
            or str(fd.get("timeUnit", "")).startswith("utc"))


def temporal_problems(chart) -> list[str]:
    spec = chart.to_dict()
    bad, n = [], 0
    for enc in _encodings(spec):
        for ch, fd in enc.items():
            items = fd if isinstance(fd, list) else [fd]
            for d in items:
                if not isinstance(d, dict) or d.get("type") != "temporal":
                    continue
                n += 1
                if ch in ("x2", "y2"):        # shares the scale of x / y
                    if not _is_utc(enc.get(ch[0], {})):
                        bad.append(f"{ch}:{d.get('field')} (primary channel not utc)")
                    continue
                if ch == "tooltip":
                    if not (_is_utc(d) or d.get("formatType") == "utc"):
                        bad.append(f"tooltip:{d.get('field')}")
                    continue
                if not _is_utc(d):
                    bad.append(f"{ch}:{d.get('field')} scale={d.get('scale')}")
                elif d.get("axis", {}).get("formatType") not in (None, "utc"):
                    # a non-utc formatType would print local wall-clock labels
                    bad.append(f"{ch}:{d.get('field')} axis formatType "
                               f"{d['axis']['formatType']}")
    return bad if n else ["no temporal encoding found"]


@unittest.skipUnless(HAS_STREAMLIT, "needs streamlit/altair (demo/.venv)")
class TestChartsUTC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_cache()
        import ui
        cls.ui = ui
        ids, ts = ev.class_events("CTU-Honeypot-Capture-4-1", "benign")
        cls.ts = ts
        cls.win = ev.event_rows(ids[:50])

    def test_replay_window_scatter_utc(self):
        c = self.ui.window_scatter(self.win, 0, 1)
        self.assertEqual(temporal_problems(c), [])

    def test_time_histograms_utc(self):
        lab = np.where(np.arange(len(self.ts)) % 2 == 0, "a", "b")
        for c in (self.ui.time_hist(self.ts),
                  self.ui.time_hist(self.ts, marker_ts=float(self.ts[3])),
                  self.ui.time_hist(self.ts, labels=lab)):
            self.assertEqual(temporal_problems(c), [])

    def test_temporal_values_are_absolute_utc(self):
        # The serialised datetimes carry a UTC offset, so the browser cannot
        # reinterpret them as local wall-clock time.
        spec = self.ui.window_scatter(self.win, 0, 1).to_dict()
        vals = [r["t"] for d in spec["datasets"].values() for r in d]
        got = pd.to_datetime(pd.Series(vals), format="ISO8601")
        self.assertIsNotNone(got.dt.tz)
        want = pd.to_datetime(np.round(self.win["ts_epoch"].to_numpy() * 1e6), unit="us", utc=True)
        self.assertTrue((got.reset_index(drop=True) == pd.Series(want)).all())
        self.assertEqual(got.iloc[0].strftime("%Y-%m-%dT%H:%M:%S"), self.win["ts_utc"].iloc[0][:19])

    def test_proba_chart_all_classes_fixed_order(self):
        pr = pd.Series({"recon": 0.1, "benign": 0.6, "malware": 0.05, "dos": 0.2, "c2": 0.05})
        spec = self.ui.proba_chart(pr).to_dict()
        layers = spec["layer"]
        self.assertEqual(layers[0]["encoding"]["y"]["sort"],
                         ["benign", "c2", "dos", "malware", "recon"])
        self.assertFalse(layers[0]["encoding"]["y"]["axis"]["labelOverlap"])
        self.assertGreaterEqual(spec["height"], 5 * 30)
        texts = [r["text"] for d in spec["datasets"].values() for r in d]
        self.assertEqual(texts, ["0.600", "0.050", "0.200", "0.050", "0.100"])

    def test_metric_bars_short_legend(self):
        df = pd.DataFrame([{"metric": "FPR", "condition": c, "value": 0.1}
                           for c in self.ui.COND_SHORT.values()])
        spec = self.ui.metric_bars(df, domain=None).to_dict()
        self.assertEqual(spec["encoding"]["color"]["scale"]["domain"],
                         ["Fragmented baseline", "Integrated"])
        self.assertNotIn("column", spec["encoding"])


if __name__ == "__main__":
    unittest.main()
