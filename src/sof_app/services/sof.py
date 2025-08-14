from __future__ import annotations
import re
import pandas as pd
import numpy as np
from uncertainties import ufloat
from uncertainties import unumpy as unp
from typing import Optional, Tuple
from sof_app.core.units import parse_quantity, convert_to
from sof_app.core.exceptions import UnitMismatchError, NuclideNotFoundError, CountsUnitDetectedError
from sof_app.services.matching import to_canonical  # limits side
from sof_app.services.aliases import canonicalize

# Detect counts units like cpm, cps, counts/s, cpm/100 cm^2, etc.
_COUNTS_PAT = re.compile(r"(?:\bcpm\b|\bcps\b|count(?:s)?\s*(?:/|per)?\s*(?:min(?:ute)?|s(?:ec(?:ond)?)?))", re.IGNORECASE)

def _detect_counts_units(units: pd.Series) -> list[str]:
    out = set()
    for u in units.astype(str).fillna(""):
        if _COUNTS_PAT.search(u.strip().lower()):
            out.add(u)
    return sorted(out)

def _align_and_convert(
    samples: pd.DataFrame,
    limits: pd.DataFrame,
    category: Optional[str],
    treat_missing_as_zero: bool,
) -> Tuple[pd.DataFrame, list[str]]:
    s = samples.copy()
    l = limits.copy()

    # 1) Safety: block counts-only units
    counts_found = _detect_counts_units(s["unit"] if "unit" in s.columns else pd.Series(dtype=str))
    if counts_found:
        msg = (
            "Counts units detected in sample 'unit' column: "
            + ", ".join(counts_found)
            + ".\nCounts (cpm/cps) require detector efficiency to convert to activity (dpm or Bq). "
              "Please pre-convert your data (e.g., cpm → dpm or Bq) and re-run."
        )
        raise CountsUnitDetectedError(msg)

    # 2) Canonicalize: samples via alias map, limits via regex
    s["_canon_used_alias"] = False
    s["nuclide_canon"], s["_canon_used_alias"] = zip(*s["nuclide"].map(canonicalize))
    l["nuclide_canon"] = l["nuclide"].map(to_canonical)

    # optional category filter
    if category and "category" in l.columns:
        l = l[l["category"].str.lower() == category.lower()].copy()
        if l.empty:
            raise ValueError(f"No limits found for category '{category}'")

    # names that changed by regex (not alias file) → audit visibility
    unmapped = sorted(set(
        s.loc[
            (~s["_canon_used_alias"]) &
            (s["nuclide"].astype(str).str.strip() != s["nuclide_canon"]),
            "nuclide"
        ].astype(str).str.strip()
    ))

    # Merge on canonical nuclide
    merged = pd.merge(s, l, how="left", on="nuclide_canon", suffixes=("_samp", "_lim"))

    # Handle missing limits
    if merged["limit_value"].isna().any() and not treat_missing_as_zero:
        missing = merged.loc[merged["limit_value"].isna(), "nuclide"].unique().tolist()
        raise NuclideNotFoundError(f"Limits not found for: {missing}")
    if treat_missing_as_zero:
        merged = merged[~merged["limit_value"].isna()].copy()
        if merged.empty:
            return merged, unmapped

    # Unit convert samples to the limit units
    def convert_row(row):
        q_s = parse_quantity(row["value"], row["unit"])
        q_l = parse_quantity(row["limit_value"], row["limit_unit"])
        try:
            q_s_conv = convert_to(q_s, str(q_l.units))
        except Exception as exc:
            raise UnitMismatchError(
                f"Cannot convert sample unit '{row['unit']}' to limit unit '{row['limit_unit']}' for {row['nuclide_canon']}"
            ) from exc
        return float(q_s_conv.magnitude), float(q_l.magnitude), str(q_l.units)

    converted = merged.apply(
        lambda r: pd.Series(convert_row(r), index=["value_conv", "limit_value_base", "unit_base"]), axis=1
    )
    merged = pd.concat([merged, converted], axis=1)
    return merged, unmapped

def _combine_duplicates(merged: pd.DataFrame) -> pd.DataFrame:
    """Combine duplicates AFTER conversion. Only aggregate optional cols if present."""
    if merged.empty:
        return merged
    if "sigma" not in merged.columns:
        merged["sigma"] = np.nan

    agg = {
        "value_conv": "sum",
        "limit_value_base": "first",
        "unit_base": "first",
        "sigma": (lambda x: np.sqrt(np.nansum(np.square(x.values))) if np.any(~pd.isna(x.values)) else np.nan),
    }
    # Add optional metadata columns if they exist
    for col in ("rule_name", "category", "note"):
        if col in merged.columns:
            agg[col] = "first"

    return merged.groupby("nuclide_canon", as_index=False).agg(agg)

def compute_sof(
    samples: pd.DataFrame,
    limits: pd.DataFrame,
    category: Optional[str] = None,
    *,
    combine_duplicates: bool = True,
    treat_missing_as_zero: bool = True,
    display_sigfigs: int = 4,
) -> Tuple[pd.DataFrame, dict]:
    m, unmapped = _align_and_convert(samples, limits, category, treat_missing_as_zero)

    if combine_duplicates:
        m = _combine_duplicates(m)

    # Fractions, with uncertainty if sigma present
    if "sigma" in m.columns and not m["sigma"].isna().all():
        fracs, sigmas = [], []
        for _, r in m.iterrows():
            if pd.notna(r.get("sigma", np.nan)):
                q = ufloat(r["value_conv"], r["sigma"]) / r["limit_value_base"]
                fracs.append(unp.nominal_values(q))
                sigmas.append(unp.std_devs(q))
            else:
                fracs.append(r["value_conv"] / r["limit_value_base"])
                sigmas.append(np.nan)
        m["fraction"], m["fraction_sigma"] = fracs, sigmas
    else:
        m["fraction"] = m["value_conv"] / m["limit_value_base"]
        m["fraction_sigma"] = np.nan

    sof_total = float(m["fraction"].sum()) if not m.empty else 0.0
    sof_sigma = None
    if m["fraction_sigma"].notna().any():
        var = np.nansum(np.square(m["fraction_sigma"].values))
        sof_sigma = float(np.sqrt(var))

    summary = {
        "rule_name": (m["rule_name"].dropna().iloc[0] if "rule_name" in m.columns and not m["rule_name"].dropna().empty else "(unspecified)"),
        "category": (category if category else (m["category"].dropna().iloc[0] if "category" in m.columns and not m["category"].dropna().empty else None)),
        "sof_total": sof_total,
        "sof_sigma": sof_sigma,
        "pass_limit": sof_total <= 1.0,
        "margin_to_1": 1.0 - sof_total,
        "unmapped_aliases": unmapped,
    }

    m["allowed_additional_in_limit_units"] = m.apply(lambda r: max(0.0, (1.0 - sof_total) * r["limit_value_base"]), axis=1)

    sf = max(1, int(display_sigfigs))
    fmt = f"{{:.{sf}g}}"
    m["conc_display"] = m.apply(lambda r: f"{fmt.format(r['value_conv'])} {r['unit_base']}", axis=1)
    m["limit_display"] = m.apply(lambda r: f"{fmt.format(r['limit_value_base'])} {r['unit_base']}", axis=1)

    out_cols = [
        "nuclide_canon", "conc_display", "limit_display", "fraction", "fraction_sigma",
        "allowed_additional_in_limit_units",
    ]
    out = m[out_cols].rename(columns={"nuclide_canon": "nuclide"})
    return out, summary
