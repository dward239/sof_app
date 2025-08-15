from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from sof_app.version import __version__

def _sha256_file(path: str | Path) -> dict:
    """Return {path, exists, size_bytes, sha256} for a file path."""
    info = {"path": str(path) if path else None, "exists": False, "size_bytes": None, "sha256": None}
    if not path:
        return info
    p = Path(path)
    if not p.is_file():
        return info
    h = hashlib.sha256()
    size = 0
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    info["exists"] = True
    info["size_bytes"] = size
    info["sha256"] = h.hexdigest()
    return info

def write_audit(path: str | Path, inputs: Dict[str, Any], results: Dict[str, Any]) -> None:
    summary = (results or {}).get("summary", {}) or {}
    warn_threshold = (inputs or {}).get("options", {}).get("warn_threshold")
    samples_path = (inputs or {}).get("samples_path")
    limits_path  = (inputs or {}).get("limits_path")
    alias_path   = (inputs or {}).get("alias_path")

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_version": __version__,

        # compact snapshot
        "sof_summary": {
            "sof_total": summary.get("sof_total"),
            "sof_sigma": summary.get("sof_sigma"),
            "pass_limit": summary.get("pass_limit"),
            "margin_to_1": summary.get("margin_to_1"),
            "category": summary.get("category"),
            "rule_name": summary.get("rule_name"),
            "warn_threshold": warn_threshold,
        },

        # file integrity stamps
        "file_integrity": {
            "samples": _sha256_file(samples_path),
            "limits":  _sha256_file(limits_path),
            "aliases": _sha256_file(alias_path) if alias_path else None,
        },

        # full payloads
        "inputs": inputs,
        "results": results,
    }

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
