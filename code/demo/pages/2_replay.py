"""Page 2 - Recorded Attack Replay: step through staged records in time order.

Historical dataset records only; nothing is generated or sent.
"""
from __future__ import annotations

import sys
import time
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import evidence as ev  # noqa: E402
import ui  # noqa: E402

ui.setup("Recorded Attack Replay",
         "Chronological replay of staged flow records (data/interim) for one threat "
         "category and capture.")
ui.banner(ui.REPLAY_BANNER)

S = st.session_state
lc = ui.label_counts()
idx = ui.source_index()
order = {s: i for i, s in enumerate(idx["source"])}
fam = dict(zip(idx["source"], idx["dataset"]))
present = sorted(lc["label"].unique())

c1, c2 = st.columns(2)
with c1:
    cls = st.selectbox("Threat category (classes present in the data)", present,
                       format_func=lambda c: ev.CLASS_NAMES.get(c, c), key="replay_class")
sub = lc[lc["label"] == cls].copy()
sub["o"] = sub["source"].map(order)
sub = sub.sort_values("o")
counts = dict(zip(sub["source"], sub["events"]))
with c2:
    source = st.selectbox(f"Capture containing '{cls}' events", list(sub["source"]),
                          format_func=lambda s: f"{s}  ({fam[s]}) — {counts[s]:,} events",
                          key="replay_source")
st.caption("Category presence and counts: demo/cache/meta.json → label_counts "
           "(derived from data/interim label column).")

ids, tss = ui.class_events(source, cls)
n = len(ids)
sel = (source, cls)
if S.get("replay_sel") != sel:
    S.replay_sel = sel
    S.replay_start, S.replay_pos, S.replay_playing = 0, 0, False
    S.replay_verify = None


def _jump_offset() -> None:
    S.replay_start = int(S[f"replay_jump_{source}_{cls}"])
    S.replay_pos = 0


def _port(v) -> str:
    return "-" if pd.isna(v) else str(int(v))


def _jump_time() -> None:
    t = pd.Timestamp(S[f"replay_time_{source}_{cls}"])
    if t.tzinfo is None:
        t = t.tz_localize("UTC")      # slider values are UTC wall-clock
    S.replay_start = int(min(max(0, np.searchsorted(tss, t.timestamp(), side="left")), n - 1))
    S.replay_pos = 0


def _toggle() -> None:
    S.replay_playing = not S.replay_playing
    S.replay_tick = 0.0


def _step(d: int) -> None:
    S.replay_playing = False
    g = S.replay_start + S.replay_pos + d
    g = int(min(max(g, 0), n - 1))
    S.replay_start = (g // S.replay_size) * S.replay_size if g < S.replay_start or \
        g >= S.replay_start + S.replay_size else S.replay_start
    S.replay_pos = g - S.replay_start


k = st.columns([1, 1, 1, 2])
with k[0]:
    S.replay_size = st.selectbox("Rows per window", [50, 100, 200], index=1, key="replay_size_sel")
with k[1]:
    speed = st.selectbox("Replay speed (events / s)", [0.5, 1.0, 2.0, 4.0], index=1,
                         key="replay_speed")
with k[2]:
    st.number_input(f"Start at event # (0 … {n - 1:,})", min_value=0,
                    max_value=max(0, n - 1), value=0, step=1, key=f"replay_jump_{source}_{cls}")
    st.button("Jump to event #", on_click=_jump_offset, key="replay_jump_btn")
with k[3]:
    # whole seconds (UTC wall clock, naive) so the 1 s slider step is exact
    lo_t = datetime.fromtimestamp(math.floor(np.nanmin(tss)), timezone.utc).replace(tzinfo=None)
    hi_t = datetime.fromtimestamp(math.ceil(np.nanmax(tss)), timezone.utc).replace(tzinfo=None)
    if hi_t > lo_t:
        st.slider("Start time (UTC)", min_value=lo_t, max_value=hi_t, value=lo_t,
                  step=timedelta(seconds=1), format="YYYY-MM-DD HH:mm:ss",
                  key=f"replay_time_{source}_{cls}")
        st.button("Jump to first event at/after this time", on_click=_jump_time,
                  key="replay_time_btn")
    else:
        st.caption(f"All selected events share one timestamp ({ev.to_utc([tss[0]])[0]}).")

S.replay_start = int(min(S.replay_start, max(0, n - 1)))
b = st.columns([1, 1, 1, 4])
b[0].button("Pause" if S.replay_playing else "Play", on_click=_toggle, key="replay_play")
b[1].button("Step back", on_click=_step, args=(-1,), key="replay_back")
b[2].button("Step forward", on_click=_step, args=(1,), key="replay_fwd")
b[3].caption(f"{n:,} '{cls}' events in {source}, ordered by timestamp (ties: original "
             f"record order). Window of {S.replay_size} rows; at most "
             f"{ev.MAX_SELECTION:,} rows are ever read per selection.")

interval = (1.0 / float(speed)) if S.replay_playing else None


@st.fragment(run_every=interval)
def player() -> None:
    size = int(S.replay_size)
    if S.replay_playing and time.time() - S.get("replay_tick", 0.0) >= 0.8 / float(speed):
        S.replay_tick = time.time()
        if S.replay_pos + 1 < min(size, n - S.replay_start):
            S.replay_pos += 1
        elif S.replay_start + size < n:
            S.replay_start += size
            S.replay_pos = 0
        else:
            S.replay_playing = False
    win = ui.window_rows(source, cls, int(S.replay_start), size)
    pos = int(min(S.replay_pos, len(win) - 1))
    cur = win.iloc[pos]
    g = int(S.replay_start) + pos

    left, right = st.columns([2, 3])
    with left:
        ui.kv_card(f"Current event {g + 1:,} of {n:,}" + ("  — playing" if S.replay_playing else ""), [
            ("dataset family", cur["dataset"]), ("capture", cur["capture"]),
            ("event_id", f"{int(cur['event_id']):,}"),
            ("record in original file", f"{int(cur['record_in_file']):,} (0-based data record)"),
            ("timestamp (UTC)", cur["ts_utc"]), ("timestamp (epoch s)", f"{cur['ts_epoch']:.6f}"),
            ("src_ip : sport", f"{cur['src_ip']} : {_port(cur['sport'])}"),
            ("dst_ip : dport", f"{cur['dst_ip']} : {_port(cur['dport'])}"),
            ("proto", cur["proto"]), ("ground-truth label", cur["label"]),
            ("split", cur["split"]), ("incident_id", cur["incident_id"]),
        ])
        with st.expander("Available attributes (non-null staged raw columns)"):
            st.code(str(cur["attributes (non-null raw columns)"]).replace("; ", "\n"),
                    language=None)
        if st.button("Verify against raw file", key="replay_verify_btn"):
            S.replay_playing = False
            S.replay_verify = ui.compare_with_raw(int(cur["event_id"]))
        v = S.get("replay_verify")
        if v and v["event_id"] == int(cur["event_id"]):
            ui.check_line(v["key_match"], f"ts/src/dst/ports/proto/label agree "
                          f"({'all' if v['all_match'] else 'not all'} staged columns agree)")
            st.caption(f"{v['raw_file']}, physical line {v['line_no']:,} "
                       f"(data record {v['record']:,})")
            st.code(v["raw_text"], language=None)
            ui.table(v["rows"].astype({"staged (data/interim)": str,
                                       "raw after Stage 1 normalisation": str}).assign(
                match=v["rows"]["match"].map(ui.mark)), height=300)
    with right:
        ui.chart(ui.window_scatter(win, pos, int(S.replay_start) + 1))
        ui.chart(ui.time_hist(tss, marker_ts=float(cur["ts_epoch"]), color=ui.MUTED,
                              title=f"All {n:,} '{cls}' events in this capture (dashed: current)"))
    show = win.drop(columns=["attributes (non-null raw columns)"]).copy()
    show.insert(0, "now", np.where(np.arange(len(win)) == pos, "▶", ""))
    ui.table(show, height=320)


player()
st.caption("Sources: data/interim/shard_*.parquet (staged records), "
           "data/processed/stage2 (split), data/processed/stage3_events (incident_id); "
           "raw lines from data/raw_combined (read on request, bounded read).")
