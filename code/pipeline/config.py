"""Central configuration for the IoT-23 / Bot-IoT integrated monitoring pipeline.

Design constraints baked in here (target host: 4 vCPU / 8 GB RAM):
  * Nothing is ever fully loaded into RAM. Every stage streams in chunks.
  * Flow aggregation from pcaps is time-windowed so active-flow memory is bounded.
  * ML training uses a stratified sampling budget instead of the full corpus.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = Path(os.environ.get("PIPE_DATA_RAW", ROOT / "data" / "raw"))
DATA_INT = ROOT / "data" / "interim"
DATA_OUT = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
MODELS = ROOT / "models"
for _d in (DATA_INT, DATA_OUT, RESULTS, MODELS):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Memory / throughput budgets
# --------------------------------------------------------------------------


@dataclass
class Budget:
    """Hard limits so a 29 GB corpus cannot exhaust an 8 GB box."""

    csv_chunksize: int = 250_000       # rows per pandas chunk when streaming CSVs
    max_active_flows: int = 120_000    # cap on tracked pcap flows before flush
    flush_rows: int = 200_000          # rows per flush batch
    train_budget_per_class: int = 60_000   # stratified sample for RF training
    eval_budget_per_class: int = 25_000    # stratified sample for evaluation
    n_jobs: int = max(1, (os.cpu_count() or 2) - 1)  # sklearn parallelism


BUDGET = Budget()

# --------------------------------------------------------------------------
# Stage 1 - collection
# --------------------------------------------------------------------------
# Substring matched against an IoT-23 capture filename to derive ground truth.
IOT23_DEFAULT_LABELS = {
    "mirai": "malware",
    "torii": "malware",
    "hakai": "malware",
    "okiru": "malware",
    "mozi": "malware",
    "censys": "recon",
    "scan": "recon",
    "brute": "bruteforce",
    "dns": "c2",
    "c2": "c2",
    "http": "benign",
    "benign": "benign",
    "ssh": "benign",
    "telnet": "benign",
    "iot23": "benign",
}

# Bot-IoT ships as CSVs; these are the scenario groups named in section 3.3.
BOTIOT_SCENARIOS = ("DDoS", "DoS", "Recon")

# Shared ground-truth vocabulary used by Stages 4 and 5 for both datasets.
CLASSES = ("benign", "c2", "malware", "botnet", "dos", "recon", "bruteforce",
           "theft")

# Label column names to look for, in priority order. Columns carrying a real
# threat vocabulary come first; a binary indicator column ("attack" = 0/1) is
# last, otherwise it would win and collapse every class onto {0, 1}.
LABEL_COLUMN_CANDIDATES = ("label", "Label", "category", "Category",
                           "subcategory", "Subcategory", "attack_type",
                           "attack", "Attack", "class")

# --------------------------------------------------------------------------
# Stage 2 - preprocessing / normalisation
# --------------------------------------------------------------------------
ID_COLUMNS = ("src_ip", "dst_ip", "label", "source", "ts", "capture",
              "ts_first", "ts_last", "split")
# Columns excluded from the feature matrix because they leak the answer or
# describe the capture rather than the traffic:
#   ts_first/ts_last/ts_end - absolute wall-clock times; attack phases occupy
#                             distinct time blocks, so a model would memorise
#                             "when" instead of learning "how" traffic looks
#   attack                  - the Argus export's binary label indicator
#   pkSeqID, seq            - row counters and TCP sequence numbers
#   smac/dmac/soui/doui/sco/dco - hardware identifiers, not traffic behaviour
#   category/subcategory/...    - raw label source columns (every
#                             LABEL_COLUMN_CANDIDATES name except "label"
#                             itself, plus IoT-23's detailed-label variants);
#                             the unified "label" is derived from them
LEAKAGE_COLUMNS = ("ts_first", "ts_last", "ts_end", "attack", "Attack",
                   "pkSeqID", "seq", "smac", "dmac", "soui", "doui",
                   "sco", "dco",
                   "Label", "category", "Category", "subcategory",
                   "Subcategory", "attack_type", "class", "detailed-label",
                   "detailed_label", "det_label")
# Free-text / identifier noise dropped up-front; hurts RF and bloats memory.
DROP_COLUMNS = ("Flow ID", "Timestamp", "Src IP", "Dst IP", "Src Port",
                "Dst Port", "Flow Duration", "Total Length of Fwd Packets",
                "Total Length of Bwd Packets", "Fwd Header Length",
                "Bwd Header Length", "Flow Bytes/s", "Flow Packets/s")

MIN_CORR_WITH_LABEL = 0.05   # |Pearson(feature, label code)| floor ("label_pearson")
VARIANCE_FLOOR = 1e-9        # raw range below this = constant column

# Feature selection method (section 3.2: correlation analysis to remove
# redundant or low-variance features):
#   "redundancy"    - drop one of each numeric pair with |r| >= threshold
#   "label_pearson" - keep numeric features with |r(feature, label code)| >=
#                     MIN_CORR_WITH_LABEL (earlier approach, kept for comparison;
#                     depends on the arbitrary label -> integer code order)
FEATURE_SELECTION = "redundancy"
REDUNDANCY_THRESHOLD = 0.95  # |feature-feature Pearson| at which one is dropped
LOW_VARIANCE_THRESHOLD = 0.0  # drop if variance of MinMax-scaled feature <= this
MISSING_SENTINEL = -1.0      # scaled value for a missing/absent numeric feature
TEST_FRACTION = 0.25         # rows hashed into the held-out "test" split

# --------------------------------------------------------------------------
# Stage 3 - event correlation
# --------------------------------------------------------------------------
CORRELATION_WINDOW_S = 300   # timestamp proximity window (5 min, tumbling)
# Rule-based correlation keys, evaluated in order; first hit wins. A rule is
# only applicable when its IP fields are present (R1 needs both endpoints).
CORRELATION_RULES = (
    "R1_pair_proto",   # (src_ip, dst_ip, proto) - direct conversation
    "R2_src_proto",    # (src_ip, proto)          - host behaviour
    "R3_dst_proto",    # (dst_ip, proto)          - target fan-out / campaign
)
# Recorded for an event that cannot be correlated (no timestamp, or neither IP
# present): it becomes its own one-event incident and is never grouped.
SINGLETON_RULE = "R0_singleton"
# "source": the key includes the event's source capture, so events from
#           independently recorded captures/datasets are never merged.
# "global": no source in the key; any capture may match any other.
CORRELATION_SCOPE = "source"

# --------------------------------------------------------------------------
# Stage 4 - threat detection
# --------------------------------------------------------------------------
RANDOM_STATE = 42
N_SPLITS = 5                # stratified cross-validation folds
MAX_TREE_DEPTH = 24         # bounded depth for the 8 GB box
N_ESTIMATORS = 300

# --------------------------------------------------------------------------
# Stage 5 - evaluation
# --------------------------------------------------------------------------
METRICS = ("accuracy", "precision_macro", "recall_macro", "f1_macro",
           "fpr", "alert_reduction", "processing_time_s")