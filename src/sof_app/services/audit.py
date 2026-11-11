"""Reproducible audit records with integrity checks bound to computed inputs."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sof_app.version import __version__


def file_identity(path: str | Path | None) -> dict:
    """Capture file SHA-256 and length. Does not modify the input."""
    info = {"path": str(path) if path else None,
            "exists": False, "size_bytes": None, "sha256": None}
    if not path:
        return info
    p = Path(path)
    if not p.is_file():
        return info
    digest = hashlib.sha256()
    size = 0
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    info.update(exists=True, size_bytes=size, sha256=digest.hexdigest())
    return info


def _clean(value: Any):
    """Convert numpy scalar-like values and reject non-finite JSON numbers."""
    if hasattr(value, "item") and callable(value.item):
        value = value.item()
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, bool, float)) or value is None:
        return value
    return str(value)


def build_audit_record(
    inputs: Dict[str, Any],
    results: Dict[str, Any],
    *,
    input_integrity: Dict[str, dict] | None = None,
) -> dict:
    """Assemble a report and reject changes to source files after calculation."""
    inputs = dict(inputs or {})
    if input_integrity is None:
        integrity = {
            key: file_identity(inputs.get(f"{key}_path"))
            for key in ("samples", "limits", "alias")
        }
        captured_at = "audit_export"
    else:
        integrity = dict(input_integrity)
        for key in ("samples", "limits", "alias"):
            expected = integrity.get(key)
            if not expected or not expected.get("exists"):
                continue
            actual = file_identity(expected.get("path"))
            if not actual["exists"] or actual["sha256"] != expected["sha256"]:
                raise ValueError(
                    f"{key} input changed since calculation; recompute before exporting audit"
                )
        captured_at = "calculation"

    summary = (results or {}).get("summary", {})
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_version": __version__,
        "sof_summary": {
            key: summary.get(key) for key in (
                "sof_total", "sof_sigma", "status", "pass_limit",
                "margin_to_1", "category", "rule_name", "rule_rev",
                "batch_id", "uncertainty_status"
            )
        },
        "file_integrity": integrity,
        "integrity_capture_stage": captured_at,
        "inputs": inputs,
        "results": results,
    }
    return _clean(record)


def write_audit(path: str | Path, inputs: Dict[str, Any],
                results: Dict[str, Any], *,
                input_integrity: Dict[str, dict] | None = None) -> None:
    record = build_audit_record(
        inputs, results, input_integrity=input_integrity
    )
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, allow_nan=False)
