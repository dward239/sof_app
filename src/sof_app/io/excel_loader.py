"""Validated input loading for CSV and XLSX files."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
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
    names = {}
    for old in df.columns:
        key = str(old).strip().casefold()
        if key in names:
            raise SchemaError(f"Duplicate column name: {old}")
        names[key] = old
    updates = {}
    for standard, aliases in alias_map.items():
        matches = [names[a] for a in aliases if a in names]
        if len(matches) > 1:
            raise SchemaError(f"Ambiguous headers for {standard}: {matches}")
        if matches:
            updates[matches[0]] = standard
    out = df.rename(columns=updates)
    required = (["nuclide", "limit_value", "limit_unit"]
                if "limit_value" in alias_map
                else ["nuclide", "value", "unit"])
    for key in required:
        if key not in out.columns:
            raise SchemaError(f"Missing required column: {key}")
    return out


def _read(path_or_buf):
    name = getattr(path_or_buf, "name", None)
    if name is None:
        name = str(path_or_buf) if isinstance(path_or_buf, (str, Path)) else ""
    extension = Path(str(name)).suffix.casefold()
    if extension == ".csv":
        return pd.read_csv(path_or_buf, encoding="utf-8-sig")
    if extension == ".xlsx":
        return pd.read_excel(path_or_buf, engine="openpyxl")
    if extension == ".xls":
        raise SchemaError("Legacy .xls is not supported. Save the input as .xlsx or .csv.")
    raise SchemaError(f"Unsupported input file type {extension or '(unknown)'}. Use .csv or .xlsx.")


def load_samples(path_or_buf) -> pd.DataFrame:
    frame = _normalize_columns(_read(path_or_buf), SAMPLE_COL_ALIASES)
    return frame[[c for c in SAMPLE_COL_ALIASES if c in frame.columns]].copy()


def load_limits(path_or_buf) -> pd.DataFrame:
    frame = _normalize_columns(_read(path_or_buf), LIMIT_COL_ALIASES)
    return frame[[c for c in LIMIT_COL_ALIASES if c in frame.columns]].copy()
