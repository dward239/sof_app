from __future__ import annotations
import os, csv, json
from pathlib import Path
from functools import lru_cache
from typing import Dict, Tuple

def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    # 1) Environment variable first (explicit wins)
    env = os.getenv("SOF_ALIAS_PATH")
    if env:
        try:
            paths.append(Path(env))
        except Exception:
            pass
    # 2) Project working dir (when running from source)
    paths += [
        Path("data/nuclide_aliases.csv"),
        Path("data/nuclide_aliases.json"),
    ]
    # 3) Repo-relative (src/sof_app/services/... -> parents[2] == project root)
    base = Path(__file__).resolve().parents[2]
    paths += [
        base / "data" / "nuclide_aliases.csv",
        base / "data" / "nuclide_aliases.json",
    ]
    # de-duplicate while preserving order
    seen = set()
    ordered: list[Path] = []
    for p in paths:
        if p and str(p) not in seen:
            ordered.append(p)
            seen.add(str(p))
    return ordered

def _load_one(path: Path) -> Dict[str, str]:
    m: Dict[str, str] = {}
    try:
        if not path.exists():
            return m
        suf = path.suffix.lower()
        if suf == ".csv":
            # utf-8-sig handles BOM if present
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    a = (row.get("alias") or "").strip()
                    c = (row.get("canonical") or "").strip()
                    if a and c:
                        key = a.replace(" ", "").replace("_", "").lower()
                        m[key] = c
        elif suf == ".json":
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    a = str(k).strip()
                    c = str(v).strip()
                    if a and c:
                        key = a.replace(" ", "").replace("_", "").lower()
                        m[key] = c
            elif isinstance(data, list):
                for item in data:
                    a = str(item.get("alias", "")).strip()
                    c = str(item.get("canonical", "")).strip()
                    if a and c:
                        key = a.replace(" ", "").replace("_", "").lower()
                        m[key] = c
    except Exception:
        # swallow file-specific errors; continue with others
        return {}
    return m

@lru_cache(maxsize=1)
def load_alias_map() -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for p in _candidate_paths():
        merged.update(_load_one(p))
    return merged

def canonicalize(nuclide: str) -> Tuple[str, bool]:
    """Return (canonical, used_alias_map) for a nuclide string."""
    from sof_app.services.matching import to_canonical as regex_canon
    raw = (nuclide or "").strip()
    if not raw:
        return "", False
    key = raw.replace(" ", "").replace("_", "").lower()
    aliases = load_alias_map()
    if key in aliases:
        return aliases[key], True
    alt = key.replace("-", "")
    if alt in aliases:
        return aliases[alt], True
    return regex_canon(raw), False
