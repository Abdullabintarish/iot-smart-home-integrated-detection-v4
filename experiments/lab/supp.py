"""Read-only loaders for the supplementary result files under experiments/."""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

EXP = Path(__file__).resolve().parents[1]
# The pages import the demo's ui module; make it importable even when a page
# runs without app.py having set the path first.
_DEMO = str(EXP.parent / "code" / "demo")
if _DEMO not in sys.path:
    sys.path.insert(0, _DEMO)
ABL = EXP / "ablation" / "results"
XL = EXP / "cross_log" / "results"
PENDING = "Supplementary analysis to the thesis experiment."
CAPTURES = ["8-1", "42-1", "20-1", "21-1", "3-1", "34-1", "1-1"]
TRAIN = ["1-1", "3-1", "20-1", "42-1"]
SEEDS = ["42", "1", "2", "3", "4"]
COND_NAME = {"A": "A · connection", "B": "B · + DNS", "C": "C · + alerts",
             "D": "D · + DNS + alerts"}


@st.cache_data(show_spinner=False)
def jload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def src(*paths: Path) -> None:
    items = "<br>".join(html.escape(str(p.relative_to(EXP.parent)).replace("\\", "/"))
                        for p in paths)
    st.markdown(f"<div class='lab-src'>Source: <br>{items}</div>", unsafe_allow_html=True)
