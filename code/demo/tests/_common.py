"""Shared test setup: import paths, the derived cache and the write guard.

The guard snapshot (size + mtime of every file under the code folder except
demo/, plus SHA-256 of the small result / model files) is taken the first
time this module is imported. unittest discovery imports every test module
before running any test, so the snapshot precedes all test activity;
test_zz_no_writes.py compares against it at the end.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
CODE = DEMO.parent
if str(DEMO) not in sys.path:
    sys.path.insert(0, str(DEMO))
sys.dont_write_bytecode = True        # never write .pyc next to pipeline/

import evidence as ev  # noqa: E402


def _snapshot() -> dict[str, tuple]:
    out = {}
    for root, dirs, files in os.walk(CODE):
        r = Path(root)
        if r == CODE:
            dirs[:] = [d for d in dirs if d != "demo"]
        for f in files:
            p = r / f
            st = p.stat()
            out[p.relative_to(CODE).as_posix()] = (st.st_size, st.st_mtime_ns)
    for d in ("results", "models"):
        for p in sorted((CODE / d).glob("*.*")):
            if p.stat().st_size < 50_000_000:
                key = p.relative_to(CODE).as_posix()
                out[key] = out[key] + (hashlib.sha256(p.read_bytes()).hexdigest(),)
    return out


SNAPSHOT_BEFORE = _snapshot()


def snapshot_now() -> dict[str, tuple]:
    return _snapshot()


def ensure_cache() -> None:
    """Build demo/cache if it is missing or stale (writes only demo/cache)."""
    if ev.cache_status()["state"] != "ok":
        ev.build_cache(log=lambda m: None)


try:
    import streamlit  # noqa: F401
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
