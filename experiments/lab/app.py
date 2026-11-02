"""Combined lab: the original Research Demonstration Lab plus the supplementary
ablation and cross-log pages, in one app.

    cd experiments/lab
    ..\\..\\code\\demo\\.venv\\Scripts\\python.exe -B -m streamlit run app.py --server.headless true

The five original pages are loaded unchanged from code/demo/pages/ and read the
same verified evidence and derived cache. The two new pages read only files
under experiments/. Nothing in code/ is modified.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
DEMO = HERE.parents[1] / "code" / "demo"
sys.path.insert(0, str(DEMO))
sys.path.insert(0, str(HERE))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Research Demonstration Lab - IoT integrated monitoring",
                   layout="wide", initial_sidebar_state="expanded")

import ui  # noqa: E402

PAGES = {
    "Verified thesis results (Run B)": [
        st.Page(DEMO / "pages" / "1_overview.py", title="Research Overview", default=True),
        st.Page(DEMO / "pages" / "2_replay.py", title="Recorded Attack Replay",
                url_path="replay"),
        st.Page(DEMO / "pages" / "3_correlation.py", title="Event Correlation Explorer",
                url_path="correlation"),
        st.Page(DEMO / "pages" / "4_detection.py",
                title="Random Forest Detection Comparison", url_path="detection"),
        st.Page(DEMO / "pages" / "5_evidence.py", title="Research Evidence Explorer",
                url_path="evidence"),
    ],
    "Supplementary analyses": [
        st.Page(HERE / "pages" / "6_ablation.py", title="Controlled Ablation",
                url_path="ablation"),
        st.Page(HERE / "pages" / "7_cross_log.py", title="Cross-Log Correlation",
                url_path="cross-log"),
    ],
}

nav = st.navigation(PAGES)
ui.sidebar()
with st.sidebar:
    st.caption("Supplementary pages: ablation and cross-log experiments. "
               "They read only files under experiments/.")
nav.run()
