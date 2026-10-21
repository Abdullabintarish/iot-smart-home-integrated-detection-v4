"""Research Demonstration Lab - entry point.

    streamlit run app.py        (from the demo folder; see run_demo.ps1)

Demonstrates the verified outputs of the thesis pipeline. It reads evidence
files read-only, never retrains a model, never generates or sends traffic,
and writes only under demo/ (the derived cache).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Research Demonstration Lab - IoT integrated monitoring",
                   layout="wide", initial_sidebar_state="expanded")

import ui  # noqa: E402

PAGES = [
    st.Page("pages/1_overview.py", title="Research Overview", default=True),
    st.Page("pages/2_replay.py", title="Recorded Attack Replay", url_path="replay"),
    st.Page("pages/3_correlation.py", title="Event Correlation Explorer",
            url_path="correlation"),
    st.Page("pages/4_detection.py", title="Random Forest Detection Comparison",
            url_path="detection"),
    st.Page("pages/5_evidence.py", title="Research Evidence Explorer",
            url_path="evidence"),
]

nav = st.navigation(PAGES)
ui.sidebar()
nav.run()
