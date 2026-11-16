# Run log — E3 simulated response (offline mitigation replay)

All times UTC. E3 is an **offline, simulated** mitigation measurement: recorded test events are
replayed and blocking is applied on paper. No network device was controlled.

## 1. Design fixed before any result (2026-11-16, before the first full run)

| # | Decision | Reason |
|---|---|---|
| D1 | Events: `W.load_test_events()` from E2 (Stage-3 parquet, `event_id` = stream position as in the ablation and E2), joined one-to-one with `results/e2/e2_events.parquet` on `event_id`; stop unless 1,692,332 rows, unique ids, and matching `incident_id`, `label`, `ts` | The Stage-3 files have no `event_id` column; the ablation and E2 both define it as the position in the concatenated sorted files |
| D2 | Replay order: (source, ts, event_id). Keys include the source, so captures never interact | Brief |
| D3 | Block window is half-open `[t, t + D)`: an event at exactly `t + D` is not blocked. Events with the same ts as the alert but a later event_id are blocked | Causal order is (ts, event_id); fixed convention |
| D4 | An alert restarts the block at its own time; it is an *extension* if a block on that key was active (`t - t_prev < D`), otherwise a *start*. Block actions = starts + extensions = alerts | Brief ("extends it from the new alert's time") |
| D5 | Alerts continue during a block (blocked events still carry their saved prediction): the sensor is assumed to sit before the block point | Saved predictions exist for every event; needed for extensions; no retraining |
| D6 | B alert time = the incident's last event in replay order; that event's key (all Run B incidents are one flow and one host: checked) | As in E2; complete incident needed |
| D7 | C trigger = every member of A's 300 s alert groups (E2 `groups`) opening or updating its group alert; result must equal A (checked on positions and on every blocked vector) | Brief |
| D8 | Oracle = event label as trigger (upper bound, not achievable); none = no alerts | Brief |
| D9 | Containment uses incidents with ≥ 2 attack events (attack events "after the first" exist). Contained: ≥ 90% of those blocked; none blocked: 0 of them. Single-attack-event incidents are counted separately | Brief's "after the first" is undefined for one event |
| D10 | Time to block: 0 if the incident's first attack event is already blocked; else next alert on its key at or after that event (own alert included) minus its time. Incidents never covered are counted, not given a value. Also reported: incidents whose block starts by their last attack event | "Start of the first block that covers it" |
| D11 | Benign hosts affected = distinct (source, src_ip) with ≥ 1 benign event blocked, under either policy | Brief |
| D12 | Dataset: Bot-IoT = sources `data_*`, IoT-23 = the rest (as E1) | Same split as before |
| D13 | Bootstrap: 1,000 replicates, seed 42, clusters = Run B incident_id; block outcomes are held fixed per event (not re-simulated) and the ratio of resampled sums is used. Also reported for prevented excluding DoS | Same as E1; re-simulating per replicate is not defined for resampled incidents |
| D14 | Per-capture "beats": strictly more attack events prevented / strictly fewer benign events wrongly blocked; ties and captures without attack or benign events reported | Brief |

## 2. Environment

| Item | Value |
|---|---|
| Machine | AMD Ryzen 7 7800X3D (16 logical CPUs), 31.2 GB RAM, Windows 11 Pro 10.0.26300 (as E1/E2) |
| Python | 3.15.0, project venv `code/.venv` |
| Packages | numpy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1 (not used for fitting), pyarrow 26.0.0, scipy 1.18.1, matplotlib 3.11.2 |
| Git HEAD at start | `6c66f80` (clean; only untracked `experiments/v4_extension/e3/`) |
| Flags | `PYTHONPATH=code`, `PYTHONDONTWRITEBYTECODE=1`, `python -B` |
| Seeds | no model seed (no training). Bootstrap seed 42, 1,000 replicates. Ablation triggers are the seed-42 predictions |

Reused unchanged by import: `experiments/v4_extension/run_alert_workload.py` (`load_test_events`,
`groups`) and, through it, `experiments/ablation/run_ablation.py` (`correlation_key`, `log`, config).
Nothing was copied or edited.

## 3. Commands and run times (UTC; script logs print local time, UTC+4)

All commands were run from `submission/`.

| Step | Command | Time | Output |
|---|---|---|---|
| Hashes before | `code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/hash_inputs.py before` | 15:38 | `results/inputs_sha256_before.txt` (164 files) |
| Tests | `cd experiments/v4_extension/e3; PYTHONPATH=<submission>/code ../../../code/.venv/Scripts/python.exe -B -m unittest discover -s tests` | ~15:40 | **7 tests OK** (first attempt) |
| Replay | `PYTHONPATH=code code/.venv/Scripts/python.exe -B -u experiments/v4_extension/e3/run_response_sim.py > experiments/v4_extension/e3/results/run.log` | 15:40:44–15:41:27, exit 0, one attempt | `results/response_*.csv`, `bootstrap.json`, `per_capture_wins.json`, `checks.json`, `blocked_300s.parquet` |
| Diagnostics | `PYTHONPATH=code code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/diagnostics.py` | ~15:42 | `results/diagnostics.json` |
| Figures | `code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/make_figures_e3.py` | ~15:42 | `results/figures/*.png`, 300 dpi |
| Tables | `code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/report_e3.py > experiments/v4_extension/e3/results/tables.md` | ~15:43 | `results/tables.md` (inserted into RESULTS.md) |
| Hashes after | `… hash_inputs.py after` | 15:43 | `results/inputs_sha256_after.txt`: **identical** to before |

The tests cover:
- the right events are blocked (including a same-timestamp tie);
- the trigger event is not counted;
- nothing is blocked before the first alert;
- expiry at `t + D`;
- start vs extension;
- P1 vs P2 scope;
- B alerts at the incident's last event;
- labels do not change any non-oracle trigger, and C's triggers equal A's;
- scoring of containment and time to block.

## 4. Checks (`results/checks.json`)

- **Join:** 1,692,332 test events and 1,692,332 E2 rows, joined one-to-one. Event ids are unique,
  and `incident_id`, `label` and `ts` match.
- **Keys:** 171,489 flows and 4,258 hosts. Every incident has one flow key and one host key.
- **Integrated prediction:** constant within every incident.
- **Incidents:** 175,489 true incidents, 64,243 with an attack event (as in E2).
- **C = A:** the trigger positions are equal, and the blocked vectors are equal for P1 and P2 at
  60 s, 300 s, 900 s and end.
- **Protected files:** `git status` shows only `experiments/v4_extension/e3/` as new. No tracked
  file changed.

## 5. Deviations and post-run additions

No design choice changed after results were seen.

| # | What | Reason |
|---|---|---|
| X1 | `diagnostics.py` was added after the main run | It explains three results (B rarely in time under P1; benign events from infected hosts under P2; DoS volume inside the first incidents). It is descriptive only and changes no result |
| X2 | Figure layout edited once after the first render (legend moved off the bars; note that overlapping event-level points coincide) | Readability only; same data |
| X3 | One wording correction in RESULTS.md (benign hosts range 14–21, not 17–21) | Checked against `response_all.csv` |

## 6. Commits

Pushed to the `copy-v4` remote (`iot-smart-home-integrated-detection-v4`) only. The original
repository (`origin`) is not updated.
