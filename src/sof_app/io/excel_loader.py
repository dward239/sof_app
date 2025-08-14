from __future__ import annotations
import pandas as pd
from sof_app.core.models import SampleRow, LimitEntry
from sof_app.core.exceptions import SchemaError

SAMPLE_COL_ALIASES = {
    "nuclide": ["nuclide", "isotope", "radionuclide", "id"],
    "value": ["value", "concentration", "activity_conc", "result"],
    "unit": ["unit", "units"],
    "sigma": ["sigma", "std", "u", "uncertainty"],
    "note": ["note", "comments"],
    "batch_id": ["batch_id", "sample", "sample_id"],
}

LIMIT_COL_ALIASES = {
    "nuclide": ["nuclide", "isotope", "radionuclide", "id"],
    "limit_value": ["limit_value", "limit", "value"],
    "limit_unit": ["limit_unit", "unit", "units"],
    "category": ["category", "class"],
    "rule_name": ["rule_name", "rule", "regulation"],
    "rule_rev": ["rule_rev", "rev", "revision", "date"],
    "provenance": ["provenance", "source"],
}

def _normalize_columns(df: pd.DataFrame, alias_map: dict) -> pd.DataFrame:
    colmap = {}
    lower = {c.lower().strip(): c for c in df.columns}
    for std, aliases in alias_map.items():
        for a in aliases:
            if a in lower:
                colmap[lower[a]] = std
                break
    out = df.rename(columns=colmap)
    required = ["nuclide", "value", "unit"] if "limit_value" not in alias_map else ["nuclide", "limit_value", "limit_unit"]
    for r in required:
        if r not in out.columns:
            raise SchemaError(f"Missing required column: {r}")
    return out

def load_samples(path_or_buf) -> pd.DataFrame:
    df = pd.read_excel(path_or_buf) if str(path_or_buf).lower().endswith("x") else pd.read_csv(path_or_buf)
    df = _normalize_columns(df, SAMPLE_COL_ALIASES)
    keep = [c for c in SAMPLE_COL_ALIASES.keys() if c in df.columns]
    return df[keep].copy()

def load_limits(path_or_buf) -> pd.DataFrame:
    df = pd.read_excel(path_or_buf) if str(path_or_buf).lower().endswith("x") else pd.read_csv(path_or_buf)
    df = _normalize_columns(df, LIMIT_COL_ALIASES)
    keep = [c for c in LIMIT_COL_ALIASES.keys() if c in df.columns]
    return df[keep].copy()
