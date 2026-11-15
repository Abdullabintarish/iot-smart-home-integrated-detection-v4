"""Run manifest for every v2 run: commit, input/output hashes, config, seeds, versions."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

REQUIRED = ("run_id", "created_utc", "git_commit", "git_dirty", "python", "packages",
            "command", "inputs", "outputs", "config", "seeds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              cwd=Path(__file__).parent).stdout.strip()
    except OSError:
        return "unavailable"


def write_manifest(path: Path, run_id: str, inputs, config: dict, seeds, outputs) -> dict:
    import numpy, pandas, sklearn  # noqa: E401
    m = {"run_id": run_id,
         "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "git_commit": _git("rev-parse", "HEAD"),
         "git_dirty": bool(_git("status", "--porcelain")),
         "python": platform.python_version(),
         "packages": {"numpy": numpy.__version__, "pandas": pandas.__version__,
                      "scikit-learn": sklearn.__version__},
         "command": " ".join(sys.argv),
         "inputs": {str(Path(p).name): sha256(Path(p)) for p in inputs},
         "outputs": {str(Path(p).name): sha256(Path(p)) for p in outputs},
         "config": config, "seeds": list(seeds)}
    Path(path).write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")
    return m
