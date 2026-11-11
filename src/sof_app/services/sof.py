"""Unit-aware Sum of Fractions calculation engine.

Conservative screening policy:
* Incomplete matching never produces a definitive PASS.
* Non-finite / negative measurement and uncertainty data are rejected.
* Each calculation represents a single batch / inventory.
* Uncertainties are converted to limit units before propagation.
"""
from __future__ import annotations

import math
import time
from typing import Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from sof_app.core.exceptions import (
    CountsUnitDetectedError, NuclideNotFoundError, UnitMismatchError
)
from sof_app.core.units import convert_to, parse_quantity
from sof_app.services.aliases import canonicalize
from sof_app.services.matching import to_canonical
from sof_app.version import __version__

VERSION = __version__
_REQUIRED_S_COLS: Sequence[str] = ("nuclide", "value", "unit")
_REQUIRED_L_COLS: Sequence[str] = ("nuclide", "limit_value", "limit_unit")


def _require_columns(df: pd.DataFrame, cols: Sequence[str], name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be a DataFrame")
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required column(s): {missing}")


def _check_names_and_units(df: pd.DataFrame, name: str, unit_col: str) -> None:
    for column in ("nuclide", unit_col):
        if df[column].isna().any() or (df[column].astype(str).str.strip() == "").any():
            raise ValueError(f"{name} contains missing or blank {column}")


def _numbers(df: pd.DataFrame, col: str, *, strictly_positive: bool) -> None:
    try:
        numeric = pd.to_numeric(df[col], errors="raise").astype(float)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{col} contains a nonnumeric value") from exc
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError(f"{col} contains NaN or infinity")
    invalid = (numeric <= 0) if strictly_positive else (numeric < 0)
    if invalid.any():
        requirement = "positive" if strictly_positive else "non-negative"
        raise ValueError(f"{col} must be finite and {requirement}")
    df[col] = numeric


def _validate_samples(samples: pd.DataFrame) -> pd.DataFrame:
    _require_columns(samples, _REQUIRED_S_COLS, "samples")
    if samples.empty:
        raise ValueError("Samples table is empty")
    s = samples.copy()
    _check_names_and_units(s, "samples", "unit")
    _numbers(s, "value", strictly_positive=False)
    if "sigma" in s:
        try:
            sigma = pd.to_numeric(s["sigma"], errors="raise").astype(float)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("sigma contains a nonnumeric value") from exc
        provided = sigma.notna()
        if not np.isfinite(sigma[provided].to_numpy()).all() or (sigma[provided] < 0).any():
            raise ValueError("sigma must be finite and non-negative when provided")
        s["sigma"] = sigma
    else:
        s["sigma"] = np.nan

    if "batch_id" in s:
        names = s["batch_id"].dropna().astype(str).str.strip()
        unique = set(names[names != ""])
        blank_present = s["batch_id"].isna().any() or (names == "").any()
        if len(unique) > 1 or (unique and blank_present):
            raise ValueError(
                "Multiple or ambiguous batch IDs: calculate each inventory separately"
            )
    return s


def _validate_limits(limits: pd.DataFrame, category: Optional[str]) -> pd.DataFrame:
    _require_columns(limits, _REQUIRED_L_COLS, "limits")
    if limits.empty:
        raise ValueError("Limits table is empty")
    l = limits.copy()
    _check_names_and_units(l, "limits", "limit_unit")
    _numbers(l, "limit_value", strictly_positive=True)
    if category:
        if "category" not in l:
            raise ValueError("Category selected but limits table has no category column")
        target = category.strip().casefold()
        l = l[l["category"].astype(str).str.strip().str.casefold() == target].copy()
        if l.empty:
            raise ValueError(f"No limits found for category '{category}'")
    # Multiple named rule sets should not silently become a composite criterion.
    for col in ("category", "rule_name", "rule_rev"):
        if col in l and len(set(l[col].dropna().astype(str).str.strip()) - {""}) > 1:
            raise ValueError(f"Limits table contains multiple {col} values; select one rule set")
    return l


def _align_and_convert(
    samples: pd.DataFrame,
    limits: pd.DataFrame,
    category: Optional[str],
    treat_missing_as_zero: bool,
) -> Tuple[pd.DataFrame, list[str], list[str]]:
    s = _validate_samples(samples)
    l = _validate_limits(limits, category)

    # Count data are not activity without an independently justified efficiency model.
    units = s["unit"].astype(str)
    if units.str.contains(r"count|cpm|cps", case=False, regex=True).any():
        raise CountsUnitDetectedError(
            "Counts or count rates cannot be used as activity without conversion"
        )

    canonical = s["nuclide"].map(lambda x: canonicalize(str(x)))
    s["nuclide_canon"] = canonical.map(lambda x: x[0])
    s["_canon_used_alias"] = canonical.map(lambda x: x[1])
    l["nuclide_canon"] = l["nuclide"].map(lambda x: to_canonical(str(x)))
    if (s["nuclide_canon"] == "").any() or (l["nuclide_canon"] == "").any():
        raise ValueError("Unrecognized or blank nuclide identifiers")

    unmapped_aliases = sorted(set(
        s.loc[
            ~s["_canon_used_alias"] &
            (s["nuclide"].astype(str).str.strip() != s["nuclide_canon"]),
            "nuclide"
        ].astype(str).str.strip()
    ))

    duplicates = l["nuclide_canon"].value_counts()
    duplicates = duplicates[duplicates > 1]
    if not duplicates.empty:
        raise ValueError("Duplicate canonical limits: " + ", ".join(duplicates.index))

    m = pd.merge(s, l, on="nuclide_canon", how="left",
                 suffixes=("_samp", "_lim"), validate="m:1")
    missing = sorted(m.loc[m["limit_value"].isna(), "nuclide_samp"
                           if "nuclide_samp" in m else "nuclide"].astype(str).unique())
    if missing and not treat_missing_as_zero:
        raise NuclideNotFoundError(
            "Missing limits for " + ", ".join(missing) +
            "; no PASS/FAIL determination is possible"
        )
    if missing:
        m = m[m["limit_value"].notna()].copy()
    if m.empty:
        return m, unmapped_aliases, missing

    def convert_row(row: pd.Series) -> pd.Series:
        ident = row["nuclide_canon"]
        sample_unit = str(row["unit"])
        limit_unit = str(row["limit_unit"])
        try:
            q_sample = parse_quantity(float(row["value"]), sample_unit)
            q_limit = parse_quantity(float(row["limit_value"]), limit_unit)
            converted = convert_to(q_sample, str(q_limit.units))
            converted_sigma = (
                convert_to(parse_quantity(float(row["sigma"]), sample_unit),
                           str(q_limit.units)).magnitude
                if pd.notna(row["sigma"]) else np.nan
            )
        except Exception as exc:
            raise UnitMismatchError(
                f"Invalid units or incompatible quantities for {ident}: "
                f"{sample_unit} versus {limit_unit}"
            ) from exc
        value = float(converted.magnitude)
        limit = float(q_limit.magnitude)
        sigma = float(converted_sigma)
        if (not math.isfinite(value) or not math.isfinite(limit) or
            limit <= 0 or not math.isfinite(sigma) and not math.isnan(sigma)):
            raise ValueError(f"Invalid converted value, limit or uncertainty for {ident}")
        return pd.Series({
            "value_conv": value, "limit_value_base": limit,
            "unit_base": str(q_limit.units), "sigma_conv": sigma
        })

    calculated = m.apply(convert_row, axis=1)
    return pd.concat([m, calculated], axis=1), unmapped_aliases, missing


def _combine_duplicates(merged: pd.DataFrame) -> pd.DataFrame:
    if merged.empty:
        return merged
    grouping = {
        "value_conv": "sum",
        "limit_value_base": "first",
        "unit_base": "first",
        "sigma_conv": lambda values: (
            math.sqrt(float(np.square(values.astype(float)).sum()))
            if values.notna().all() else np.nan
        ),
    }
    for col in ("rule_name", "rule_rev", "category", "note", "batch_id"):
        if col in merged:
            grouping[col] = "first"
    return merged.groupby("nuclide_canon", as_index=False).agg(grouping)


def compute_sof(
    samples: pd.DataFrame,
    limits: pd.DataFrame,
    category: Optional[str] = None,
    *,
    combine_duplicates: bool = True,
    treat_missing_as_zero: bool = False,
    display_sigfigs: int = 4,
) -> Tuple[pd.DataFrame, dict]:
    """Compute a single-inventory SOF, rejecting incomplete/invalid inputs by default.

    Explicit opt-in to omit unmatched nuclides yields status INCOMPLETE and
    pass_limit=None; the numerical sum then represents matched nuclides only.
    """
    m, unmapped_aliases, missing = _align_and_convert(
        samples, limits, category, treat_missing_as_zero
    )
    n_sigma_input = int(samples["sigma"].notna().sum()) if "sigma" in samples else 0
    n_samples = len(samples)
    if combine_duplicates:
        m = _combine_duplicates(m)

    if not m.empty:
        m["fraction"] = m["value_conv"] / m["limit_value_base"]
        m["fraction_sigma"] = m["sigma_conv"] / m["limit_value_base"]
    else:
        m = pd.DataFrame(columns=[
            "nuclide_canon", "value_conv", "limit_value_base",
            "unit_base", "sigma_conv", "fraction", "fraction_sigma"
        ])

    sof_total = float(m["fraction"].sum()) if not m.empty else 0.0
    if not math.isfinite(sof_total):
        raise ValueError("Nonfinite SOF total")
    all_sigma = n_sigma_input == n_samples
    no_sigma = n_sigma_input == 0
    uncertainty_status = ("not_provided" if no_sigma else
                          "complete" if all_sigma else "partial")
    # Missing sigma anywhere means a partial uncertainty, not a full uncertainty.
    sof_sigma = (
        float(np.sqrt(np.square(m["fraction_sigma"].to_numpy(dtype=float)).sum()))
        if all_sigma and not missing else None
    )
    if missing:
        status, passed = "INCOMPLETE", None
    elif sof_total <= 1.0:
        status, passed = "PASS", True
    else:
        status, passed = "FAIL", False

    m["allowed_additional_in_limit_units"] = m.apply(
        lambda row: (
            max(0.0, (1 - sof_total) * row["limit_value_base"])
            if status == "PASS" else np.nan
        ), axis=1
    )
    sf = max(1, min(int(display_sigfigs), 12))
    fmt = f"{{:.{sf}g}}"
    m["conc_display"] = m.apply(
        lambda row: f"{fmt.format(row['value_conv'])} {row['unit_base']}", axis=1
    )
    m["limit_display"] = m.apply(
        lambda row: f"{fmt.format(row['limit_value_base'])} {row['unit_base']}", axis=1
    )
    m["fraction_display"] = m["fraction"].map(lambda x: fmt.format(x))
    out = m[[
        "nuclide_canon", "conc_display", "limit_display",
        "value_conv", "limit_value_base", "unit_base", "sigma_conv",
        "fraction", "fraction_display", "fraction_sigma",
        "allowed_additional_in_limit_units"
    ]].rename(columns={"nuclide_canon": "nuclide"})

    def first_or_default(name: str, default=None):
        if name not in m:
            return default
        nonblank = m[name].dropna()
        return nonblank.iloc[0] if not nonblank.empty else default

    batch_id = None
    if "batch_id" in samples:
        unique = samples["batch_id"].dropna().astype(str).str.strip().unique()
        if len(unique):
            batch_id = str(unique[0])

    summary = {
        "rule_name": first_or_default("rule_name", "(unspecified)"),
        "rule_rev": first_or_default("rule_rev"),
        "category": category or first_or_default("category"),
        "batch_id": batch_id,
        "sof_total": sof_total,
        "sof_sigma": sof_sigma,
        "uncertainty_status": uncertainty_status,
        "status": status,
        "pass_limit": passed,
        "margin_to_1": (1.0 - sof_total) if not missing else None,
        "unmapped_aliases": unmapped_aliases,
        "missing_limit_for_samples": missing,
        "rows_total": n_samples,
        "rows_evaluated": len(m),
        "version": __version__,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "assumptions": [
            "Single inventory or batch per calculation.",
            "SOF = sum of converted measurement/limit fractions.",
            "All measurement and limit values must be finite; negatives rejected.",
            "Measurement sigma converted to the same units as measurement before propagation.",
            "Uncertainties are combined assuming independent inputs.",
            "No definitive PASS is returned with unmatched nuclides.",
        ],
    }
    return out, summary
