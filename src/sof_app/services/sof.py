
from __future__ import annotations
import re
import time
from typing import Optional, Tuple, Sequence

import numpy as np
import pandas as pd
from uncertainties import ufloat
from uncertainties import unumpy as unp

from sof_app.core.units import parse_quantity, convert_to
from sof_app.core.exceptions import (
    UnitMismatchError,
    NuclideNotFoundError,
    CountsUnitDetectedError,
)
from sof_app.services.matching import to_canonical  # limits side
from sof_app.services.aliases import canonicalize   # samples side

VERSION = "0.1.1"

# Expanded detection of counts-like strings (friendly error before units layer raises)
_COUNTS_PAT = re.compile(
    r"""
    \b(?:cpm|cps)\b
  | \bcount(?:s)?\s*/\s*(?:min(?:ute)?|s(?:ec(?:ond)?)?)\b
  | \bcount(?:s)?\s*per\s*(?:min(?:ute)?|s(?:ec(?:ond)?)?)\b
  | \bcount(?:s)?\s*(?:min|s)\s*(?:-?1|\^-?1)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


_REQUIRED_S_COLS: Sequence[str] = ("nuclide", "value", "unit")
_REQUIRED_L_COLS: Sequence[str] = ("nuclide", "limit_value", "limit_unit")

def _require_columns(df: pd.DataFrame, cols: Sequence[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required column(s): {missing}. "
                         f"Expected at least: {list(cols)}")

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
) -> Tuple[pd.DataFrame, list[str], list[str]]:
    # Validate schemas up-front
    _require_columns(samples, _REQUIRED_S_COLS, "samples")
    _require_columns(limits, _REQUIRED_L_COLS, "limits")

    s = samples.copy()
    l = limits.copy()

    # 1) Safety: block counts-only units with a clear message
    counts_found = _detect_counts_units(s["unit"])
    if counts_found:
        msg = (
            "Counts units detected in sample 'unit' column: "
            + ", ".join(counts_found)
            + ". Counts (cpm/cps) require detector efficiency to convert to activity "
              "(dpm or Bq). Please pre-convert (e.g., cpm → dpm or Bq) and re-run."
        )
        raise CountsUnitDetectedError(msg)

    # 2) Canonicalize names
    s["_canon_used_alias"] = False
    s["nuclide_canon"], s["_canon_used_alias"] = zip(*s["nuclide"].map(canonicalize))
    l["nuclide_canon"] = l["nuclide"].map(to_canonical)

    # Optional category filter (robust normalization)
    if category and "category" in l.columns:
        key = category.strip().casefold()
        l = l[l["category"].astype(str).str.strip().str.casefold() == key].copy()
        if l.empty:
            raise ValueError(f"No limits found for category '{category}'")

    # Names changed by regex (not alias file) → audit
    unmapped_aliases = sorted(set(
        s.loc[
            (~s["_canon_used_alias"]) &
            (s["nuclide"].astype(str).str.strip() != s["nuclide_canon"]),
            "nuclide"
        ].astype(str).str.strip()
    ))

    # Ensure one limit per nuclide (avoid silent duplication)
    dup_l = l["nuclide_canon"].value_counts(dropna=False)
    dup_l = dup_l[dup_l > 1]
    if not dup_l.empty:
        raise ValueError(f"Limits table has multiple rows for canonical nuclide(s): "
                         f"{', '.join(dup_l.index.astype(str))}")

    # Merge samples → limits (many-to-one)
    merged = pd.merge(
        s, l, how="left", on="nuclide_canon", suffixes=("_samp", "_lim"), validate="m:1"
    )

    # Detect missing limit matches
    missing_mask = merged["limit_value"].isna()
    missing_samples: list[str] = []
    if missing_mask.any():
        missing_samples = merged.loc[missing_mask, "nuclide"].astype(str).unique().tolist()
        if not treat_missing_as_zero:
            raise NuclideNotFoundError(f"Limits not found for: {missing_samples}")
        merged = merged[~missing_mask].copy()

    if merged.empty:
        # Nothing to compute
        return merged, unmapped_aliases, missing_samples

    # Unit convert samples to the limit units
    def convert_row(row):
        q_s = parse_quantity(row["value"], row["unit"])
        q_l = parse_quantity(row["limit_value"], row["limit_unit"])

        # Validate limit > 0 (safety)
        if float(q_l.magnitude) <= 0:
            raise ValueError(
                f"Non-positive limit for {row['nuclide_canon']}: "
                f"{row['limit_value']} {row['limit_unit']}"
            )
        try:
            q_s_conv = convert_to(q_s, str(q_l.units))
        except Exception as exc:
            raise UnitMismatchError(
                f"Cannot convert sample unit '{row['unit']}' to limit unit "
                f"'{row['limit_unit']}' for {row['nuclide_canon']}"
            ) from exc
        return float(q_s_conv.magnitude), float(q_l.magnitude), str(q_l.units)

    converted = merged.apply(
        lambda r: pd.Series(convert_row(r), index=["value_conv", "limit_value_base", "unit_base"]),
        axis=1,
    )
    merged = pd.concat([merged, converted], axis=1)
    return merged, unmapped_aliases, missing_samples

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
        "sigma": (lambda x: np.sqrt(np.nansum(np.square(x.values)))
                  if np.any(~pd.isna(x.values)) else np.nan),
    }
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
    """
    Compute Sum of Fractions:
        SOF = Σ_i ( measurement_i_in_limit_units / limit_i )

    Expected schemas:
      samples columns: ['nuclide', 'value', 'unit', (optional: 'sigma', 'rule_name', 'category', 'note')]
      limits  columns: ['nuclide', 'limit_value', 'limit_unit', (optional: 'rule_name', 'category')]
    """
    m, unmapped_aliases, missing_samples = _align_and_convert(
        samples, limits, category, treat_missing_as_zero
    )

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

    # Per-row “allowed additional” (truncate below 0)
    m["allowed_additional_in_limit_units"] = m.apply(
        lambda r: max(0.0, (1.0 - sof_total) * r["limit_value_base"]), axis=1
    )

    # Display formatting
    sf = max(1, int(display_sigfigs))
    fmt = f"{{:.{sf}g}}"
    m["conc_display"] = m.apply(lambda r: f"{fmt.format(r['value_conv'])} {r['unit_base']}", axis=1)
    m["limit_display"] = m.apply(lambda r: f"{fmt.format(r['limit_value_base'])} {r['unit_base']}", axis=1)
    m["fraction_display"] = m["fraction"].map(lambda x: fmt.format(x))

    out_cols = [
        "nuclide_canon", "conc_display", "limit_display",
        "fraction", "fraction_display", "fraction_sigma",
        "allowed_additional_in_limit_units",
    ]
    out = m[out_cols].rename(columns={"nuclide_canon": "nuclide"})

    summary = {
        "rule_name": (m["rule_name"].dropna().iloc[0] if "rule_name" in m.columns and not m["rule_name"].dropna().empty else "(unspecified)"),
        "category": (category if category else (m["category"].dropna().iloc[0] if "category" in m.columns and not m["category"].dropna().empty else None)),
        "sof_total": sof_total,
        "sof_sigma": sof_sigma,
        "pass_limit": sof_total <= 1.0,
        "margin_to_1": 1.0 - sof_total,
        "unmapped_aliases": unmapped_aliases,
        "missing_limit_for_samples": missing_samples,
        "version": VERSION,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "assumptions": [
            "Fractions computed as measurement_in_limit_units / limit_value.",
            "Measurement units converted to limit units per-row.",
            f"Missing limits {'contribute 0 (dropped)' if treat_missing_as_zero else 'raise an error'}.",
            "Duplicates (if any) combined after conversion (values summed; σ combined in quadrature).",
            "Limits must be positive; zero/negative limits are rejected.",
        ],
    }

    return out, summary
