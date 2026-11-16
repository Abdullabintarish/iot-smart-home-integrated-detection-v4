# E1 rich incident features

Code: `rich_features.py` (`rich_incident_context`). The real-data column list is in
`results/e1/rich_feature_names.csv` and `results/e1/runb_checks.json` (`rich_features`).

## How groups are formed
- **Group:** the Run B correlation key (`pipeline.correlate.correlation_key`: source, rule,
  src_ip/dst_ip/proto, tumbling time bucket) **plus the event's split**. This is identical to
  `experiments/ablation/run_ablation.incident_context`, so no group crosses train and test.
- **Uncorrelatable events:** each forms its own group.
- **Leave-one-source-out:** the split is set to `"all"`, as in `experiments/v3/transfer_v3.py`.
  Groups stay inside a source, so they never cross a fold.
- **Per-event values:** every event carries its group's values.

## Inputs
- **Columns:** the 11 `shared_features` (`sport`, `dport`, `proto`, `app`, `duration`,
  `conn_state`, `history`, `bwd_pkts`, `bytes`, `flgs`, `state`), plus `dst_ip` for one
  distinct count and `ts` for timing.
- **No labels:** `label`, `incident_id` and `event_id` are never read. Asking for `label` as a
  feature raises an error (tested).
- **Encodings:** values are the Stage-2 encodings. Numeric features are MinMax-scaled with the
  training range; categorical features are integer codes.

## Missing values
- **Sentinel:** `C.MISSING_SENTINEL` (−1) is a missing numeric value or an unseen category, and is
  excluded from every statistic.
- **Absent fields:** the `__NA__` code of a field a dataset lacks was not saved by Stage 2. It is
  recovered without labels as the single code that every event of one dataset (Bot-IoT =
  `data_*`, IoT-23 = the rest) carries. Result: app 1, conn_state 13, history 200, flgs 0,
  state 10. This code is also excluded.
- **Empty groups:** a group with no observed value gets −1 for a statistic or share, and 0 for a
  distinct count.
- **Category columns:** the categories that become columns are the codes seen in **training**
  events (Run B train split).

## Features (77 on the real data)

| Feature | How it is computed |
|---|---|
| `n_events` | Number of events in the group (as `incident_context`) |
| `span_s` | Last minus first timestamp in the group, seconds |
| `events_per_s` | `n_events / span_s`; 0 when `span_s` = 0 |
| `n_distinct_dst_port` | Number of distinct observed `dport` values in the group |
| `n_distinct_src_port` | Number of distinct observed `sport` values |
| `n_distinct_dst_ip` | Number of distinct `dst_ip` values (constant 1 in this data: every group is keyed on src, dst, proto) |
| `n_distinct_proto` | Number of distinct observed `proto` codes (constant 1 in this data, same reason) |
| `duration_{mean,std,min,max,median,sum}` | Statistic of observed `duration` values in the group; std is the population SD (ddof 0) |
| `bwd_pkts_{mean,std,min,max,median,sum}` | Same six statistics of observed `bwd_pkts` |
| `bytes_{mean,std,min,max,median,sum}` | Same six statistics of observed `bytes` |
| `proto_share_<k>` (k = 1–5) | Share of the group's observed `proto` values equal to code k |
| `app_share_<k>` (k = 0, 2–7) | Share of observed `app` values equal to code k |
| `n_distinct_app` | Number of distinct observed `app` codes |
| `conn_state_share_<k>` (k = 0–12) | Share of observed `conn_state` values equal to code k |
| `n_distinct_conn_state` | Number of distinct observed `conn_state` codes |
| `history_top_share` | Share of the most common observed `history` code (200 categories, more than the 16 limit, so no per-category shares) |
| `n_distinct_history` | Number of distinct observed `history` codes |
| `flgs_share_<k>` (k = 1–11) | Share of observed `flgs` values equal to code k |
| `n_distinct_flgs` | Number of distinct observed `flgs` codes |
| `state_share_<k>` (k = 0–9) | Share of observed `state` values equal to code k |
| `n_distinct_state` | Number of distinct observed `state` codes |

## Rules fixed before any result was seen
- **Shares vs top share:** a categorical column gets per-category shares when it has at most 16
  training categories. Otherwise it gets the top share plus a distinct count.
- **Ports:** `sport` and `dport` are service identifiers. They get distinct counts, not
  means or sums.
- **Statistics:** every non-port numeric shared feature gets all six statistics.
