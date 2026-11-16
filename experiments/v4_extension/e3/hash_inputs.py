"""SHA-256 of every E3 input and protected file, before and after the E3 run.

Covers the 53 untracked Run B / Run T files hashed by E1/E2
(results/untracked_inputs_sha256_before.txt), every file of E1/E2 in
experiments/v4_extension outside e3/, and predictions/.

    code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/hash_inputs.py before|after
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

E3 = Path(__file__).resolve().parent
V4 = E3.parent
SUB = V4.parents[1]


def files() -> list[Path]:
    out = []
    for line in (V4 / "results" / "untracked_inputs_sha256_before.txt").read_text(
            encoding="utf-8-sig").splitlines():
        if line.strip():
            out.append((SUB / line.split(None, 1)[1].strip().replace("\\", "/")).resolve())
    out += [p for p in V4.rglob("*") if p.is_file() and E3 not in p.parents]
    out += [p for p in (SUB / "predictions").rglob("*") if p.is_file()]
    return sorted(set(out))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    tag = sys.argv[1]
    lines = [f"{sha(p)}  {p.relative_to(SUB.parent).as_posix()}" for p in files()]
    out = E3 / "results" / f"inputs_sha256_{tag}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} files -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
