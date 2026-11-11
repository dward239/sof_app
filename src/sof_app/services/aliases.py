"""Nuclide alias resolution with explicit paths and packaged fallback."""
from __future__ import annotations

import csv
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

from sof_app.services.matching import to_canonical


def alias_source_path() -> Path:
    """Prefer explicit override; otherwise use packaged data or source checkout."""
    override = os.getenv("SOF_ALIAS_PATH")
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"SOF_ALIAS_PATH is not a readable file: {path}")
        return path
    packaged = Path(__file__).resolve().parents[1] / "data" / "nuclide_aliases.csv"
    if packaged.is_file():
        return packaged
    checkout = Path(__file__).resolve().parents[3] / "data" / "nuclide_aliases.csv"
    if checkout.is_file():
        return checkout
    raise FileNotFoundError(
        "Nuclide alias table is missing; install package data or set SOF_ALIAS_PATH"
    )


def _load_one(path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not {"alias", "canonical"}.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"Alias CSV missing alias/canonical columns: {path}")
            rows = ((r.get("alias"), r.get("canonical")) for r in reader)
            result = _build(rows)
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if isinstance(data, dict):
            rows = data.items()
        elif isinstance(data, list):
            rows = ((r.get("alias"), r.get("canonical")) for r in data)
        else:
            raise ValueError("Alias JSON must be an object or an array")
        result = _build(rows)
    else:
        raise ValueError(f"Unsupported alias file: {path}")
    if not result:
        raise ValueError(f"Alias file has no usable entries: {path}")
    return result


def _build(rows) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for alias, canonical in rows:
        key = str(alias or "").replace(" ", "").replace("_", "").casefold()
        value = str(canonical or "").strip()
        if not key or not value:
            continue
        value = to_canonical(value)
        if key in values and values[key] != value:
            raise ValueError(f"Conflicting alias mapping for {alias}")
        values[key] = value
    return values


@lru_cache(maxsize=8)
def _load_cached(path: str, modified_ns: int, size: int) -> Dict[str, str]:
    return _load_one(Path(path))


def load_alias_map() -> Dict[str, str]:
    path = alias_source_path()
    info = path.stat()
    return _load_cached(str(path.resolve()), info.st_mtime_ns, info.st_size)


def canonicalize(nuclide: str) -> Tuple[str, bool]:
    raw = str(nuclide or "").strip()
    if not raw:
        return "", False
    key = raw.replace(" ", "").replace("_", "").casefold()
    aliases = load_alias_map()
    if key in aliases:
        return aliases[key], True
    no_hyphen = key.replace("-", "")
    if no_hyphen in aliases:
        return aliases[no_hyphen], True
    return to_canonical(raw), False
