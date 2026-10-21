"""Record the provenance of a pipeline run in ``results/run_manifest.json``.

    python record_run_info.py [--raw data/raw_combined] [--out results/run_manifest.json]

Captures the host (OS, CPU, RAM, Python, ``pip freeze``), a SHA-256 of every
code file plus a code snapshot id (there is no git repository, so this hash
list is the code version), SHA-256 and provenance of every raw dataset file,
and all configuration values. Run it before Stage 1; it only reads.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline import config as C
from pipeline.detect import model_config

ROOT = Path(__file__).resolve().parent
IOT23_URL = ("https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/"
             "IndividualScenarios/{capture}/bro/conn.log.labeled")
BOTIOT_SOURCE = "Kaggle dataset vigneshvenkateswaran/bot-iot"


def sha256(path: Path, block: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def cpu_name() -> str:
    """Marketing CPU name where the OS exposes it, else platform.processor()."""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def ram_total_bytes() -> int | None:
    """Physical RAM in bytes, without third-party packages."""
    if sys.platform == "win32":
        import ctypes

        class MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = MemStatus()
        st.dwLength = ctypes.sizeof(MemStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullTotalPhys)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError, AttributeError):
        return None


def pip_freeze() -> list[str]:
    try:
        out = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                             capture_output=True, text=True, timeout=120)
        return [ln for ln in out.stdout.splitlines() if ln.strip()]
    except (subprocess.SubprocessError, OSError) as exc:
        return [f"pip freeze failed: {exc}"]


def code_files() -> list[Path]:
    """pipeline/ plus top-level *.py, *.ps1, *.sh and requirements.txt."""
    files = [p for p in (ROOT / "pipeline").rglob("*")
             if p.is_file() and "__pycache__" not in p.parts]
    for pat in ("*.py", "*.ps1", "*.sh", "requirements.txt"):
        files += [p for p in ROOT.glob(pat) if p.is_file()]
    return sorted(set(files))


def code_snapshot() -> dict:
    files = {p.relative_to(ROOT).as_posix(): sha256(p) for p in code_files()}
    snap = hashlib.sha256("\n".join(sorted(files.values())).encode()).hexdigest()
    return {"version_control": "no git repository; the code version is "
                               "identified by the snapshot id below",
            "snapshot_id": snap,
            "snapshot_id_definition": "SHA-256 of the newline-joined, sorted "
                                      "list of per-file SHA-256 hex digests",
            "files": files}


def provenance(rel: Path) -> dict:
    """Where a raw file was obtained, from its name and location."""
    parts = rel.parts
    if rel.name == "conn.log.labeled" and len(parts) >= 3:
        return {"dataset": "IoT-23", "capture": parts[-3],
                "url": IOT23_URL.format(capture=parts[-3])}
    if rel.name.startswith("data_") and rel.suffix == ".csv":
        return {"dataset": "Bot-IoT", "file": rel.name, "source": BOTIOT_SOURCE}
    return {"dataset": "unknown"}


def datasets(raw: Path) -> list[dict]:
    out = []
    for p in sorted(x for x in raw.rglob("*") if x.is_file()):
        rel = p.relative_to(raw)
        out.append({"path": (raw.name / rel).as_posix(), "bytes": p.stat().st_size,
                    "sha256": sha256(p), "provenance": provenance(rel)})
    return out


def _jsonable(v):
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, (tuple, list)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return v


def config_values() -> dict:
    consts = {k: _jsonable(v) for k, v in vars(C).items()
              if k.isupper() and not k.startswith("_")
              and isinstance(v, (str, int, float, bool, tuple, list, dict, Path))}
    return {"pipeline.config": consts,
            "BUDGET": dataclasses.asdict(C.BUDGET),
            "detect.model_config": model_config()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw_combined",
                    help="raw dataset directory to hash (read only)")
    ap.add_argument("--out", type=Path, default=C.RESULTS / "run_manifest.json")
    args = ap.parse_args()

    raw = args.raw if args.raw.is_absolute() else ROOT / args.raw
    ram = ram_total_bytes()
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": {"os": platform.platform(), "machine": platform.machine(),
                 "cpu": cpu_name(), "cpu_logical_cores": os.cpu_count(),
                 "ram_total_bytes": ram,
                 "ram_total_gib": round(ram / 2**30, 2) if ram else None},
        "python": {"version": sys.version, "executable": sys.executable,
                   "pip_freeze": pip_freeze()},
        "code": code_snapshot(),
        "datasets": {"root": raw.name, "files": datasets(raw) if raw.exists()
                     else [], "note": "raw files are read-only evidence; "
                                      "hashes taken before Stage 1"},
        "config": config_values(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, default=str),
                        encoding="utf-8")
    n = len(manifest["datasets"]["files"])
    print(f"run manifest written: {args.out}")
    print(f"  code snapshot {manifest['code']['snapshot_id'][:16]}... "
          f"({len(manifest['code']['files'])} files), {n} dataset files hashed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
