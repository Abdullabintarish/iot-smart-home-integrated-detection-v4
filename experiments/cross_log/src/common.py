"""Shared helpers. Imports the thesis label mapping read-only.

``sys.dont_write_bytecode`` is set before importing from ``code/`` so that no
``__pycache__`` file is written into the existing project.
"""
from __future__ import annotations

import ipaddress
import sys
from pathlib import Path

sys.dont_write_bytecode = True
SUBMISSION = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SUBMISSION / "code"))
from pipeline.ingest import _zeek_label  # noqa: E402  (thesis mapping, unchanged)

WINDOW_S = 300            # main correlation window (thesis config value)
LABEL_TS_TOLERANCE_S = 1.0  # max |ts difference| for a label match


def thesis_class(binary: str, detailed: str) -> str:
    """IoT-23 (label, detailed-label) -> thesis class (benign/c2/dos/recon/malware)."""
    return _zeek_label(binary, detailed, "unknown")


def is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def local_host(a: str, b: str) -> str:
    """The monitored-network endpoint of a flow: the private one, else ``a``.

    ``a`` is the originator / packet source. If both or neither are private,
    the originator is used.
    """
    pa, pb = is_private(a), is_private(b)
    if pb and not pa:
        return b
    return a
