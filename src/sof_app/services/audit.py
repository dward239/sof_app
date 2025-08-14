from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from sof_app.version import __version__

def write_audit(path: str | Path, inputs: Dict[str, Any], results: Dict[str, Any]) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_version": __version__,
        "inputs": inputs,
        "results": results,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
