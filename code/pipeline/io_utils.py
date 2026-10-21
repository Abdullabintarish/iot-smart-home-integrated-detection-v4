"""Shared IO helpers.

``pandas.read_parquet`` has no ``chunksize`` (that parameter is CSV-only), but
parquet stores row groups that map naturally onto chunks. ``iter_parquet``
reads one row group at a time via pyarrow, which is how every stage here stays
inside the memory budget while reading multi-GB shards.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd
import pyarrow.parquet as pq


def iter_parquet(path: Path, batch_size: int = 250_000,
                 columns: list[str] | None = None) -> Iterator[pd.DataFrame]:
    """Yield a parquet file as DataFrames of at most ``batch_size`` rows."""
    pf = pq.ParquetFile(path)
    pending: list[pd.DataFrame] = []
    pending_rows = 0
    for batch in pf.iter_batches(batch_size=batch_size, columns=columns):
        df = batch.to_pandas()
        pending.append(df)
        pending_rows += len(df)
        if pending_rows >= batch_size:
            yield pd.concat(pending, ignore_index=True)
            pending, pending_rows = [], 0
    if pending:
        yield pd.concat(pending, ignore_index=True)


def iter_parquet_dir(directory: Path, pattern: str = "*.parquet",
                     batch_size: int = 250_000) -> Iterator[pd.DataFrame]:
    """Yield every parquet file under ``directory`` in sorted order."""
    files = sorted(Path(directory).glob(pattern))
    if not files:
        return
    for f in files:
        yield from iter_parquet(f, batch_size=batch_size)


def peak_rss_mb() -> float:
    """Peak resident set size of this process in MB (Linux/macOS/Windows)."""
    try:
        import resource
    except ImportError:                      # Windows has no ``resource`` module
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        pmc = _PMC()
        pmc.cb = ctypes.sizeof(pmc)
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,
                                               ctypes.POINTER(_PMC), wintypes.DWORD]
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / (1024 * 1024)
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024