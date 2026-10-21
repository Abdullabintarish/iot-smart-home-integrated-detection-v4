"""Verify live inference of the saved integrated model on ALL test incidents.

    python verify_live_inference.py

Loads models/rf_integrated.joblib read-only, predicts every incident that has
held-out test events (features from stage3_incidents, prepared exactly as
pipeline.detect.feature_matrix does) and compares with the saved integrated
predictions. The result is written to demo/cache/live_inference_check.json;
the app shows it and only calls live output "equivalent" when every
incident agrees.
"""
from __future__ import annotations

import json
import sys
import time

import evidence as ev


def main() -> int:
    st = ev.cache_status()
    if st["state"] != "ok":
        print(f"cache {st['state']}: run build_cache.py first")
        return 2
    t = time.perf_counter()
    preds = ev.load_predictions()
    load_s = time.perf_counter() - t
    res = ev.verify_live_inference(preds)
    res["load_predictions_seconds"] = round(load_s, 2)
    ev.LIVE_CHECK.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0 if res["n_mismatch"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
