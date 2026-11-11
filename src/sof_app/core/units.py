from __future__ import annotations
import re
from typing import Iterable
from pint import UnitRegistry

# -------------------------------
# Registry & quantity factory
# -------------------------------
ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = ureg.Quantity

# -------------------------------
# Safe unit definitions (idempotent)
# -------------------------------
def _safe_define(defn: str) -> None:
    try:
        ureg.define(defn)
    except Exception:
        # Ignore if already defined or alias collision
        pass

# Activity: curie + prefixes
_safe_define("curie = 3.7e10 * becquerel = Ci")
_safe_define("millicurie = 1e-3 curie = mCi")
_safe_define("microcurie = 1e-6 curie = uCi = µCi")
_safe_define("nanocurie = 1e-9 curie = nCi")
_safe_define("picocurie = 1e-12 curie = pCi")

# Common lab convenience
_safe_define("dpm = 1/60 * becquerel = disintegrations_per_minute")
_safe_define("dps = becquerel = disintegrations_per_second")

# Dose: rem + mrem (Sv is built-in)
_safe_define("rem = 0.01 sievert = rem")
_safe_define("millirem = 1e-3 rem = mrem")
# Ensure micro-sievert alias convenience
_safe_define("microsievert = 1e-6 sievert = uSv = µSv")

# Time: add yr alias
_safe_define("year = 365.25 * day = yr")

# Keep your dimensionless count (allowed to exist), but we'll block its use in conversion helpers.
_safe_define("count = []")

# -------------------------------
# “Per 100 cm^2” bundle handling
# -------------------------------
SURFACE_AREA_BUNDLE = Q_(100, "centimeter**2")

# Robust detector for a trailing “per 100 cm^2” token in compacted unit strings
# Accepts variants like "/100cm^2", "/100cm**2" (we normalize ^→** earlier)
_BUNDLE_RE = re.compile(r"/100cm(\^?2|\*\*2)$", flags=re.IGNORECASE)

# -------------------------------
# Safety: block counts/cpm/cps in conversions
# -------------------------------
_BLOCKED_TOKENS = {"count", "counts", "cpm", "cps"}

def _normalize_unit_text(s: str) -> str:
    """Normalize user unit text for parsing."""
    if not s:
        return ""
    # remove spaces, standardize micro and power syntax
    t = s.strip().replace(" ", "")
    t = t.replace("µ", "u")        # allow micro sign
    t = t.replace("^", "**")       # allow caret powers
    return t

def _guard_counts(unit_text: str) -> None:
    t = unit_text.lower()
    # Check tokens either as whole unit or as part of compound like "count/s", "cpm"
    if any(tok in t for tok in _BLOCKED_TOKENS):
        raise ValueError(
            "Counts/cpm/cps are blocked in unit conversion. "
            "Convert counts → activity first using an efficiency (and geometry) model."
        )

# -------------------------------
# Public helpers
# -------------------------------
def parse_quantity(value: float, unit: str):
    """
    Parse a numeric value + unit string into a pint Quantity.
    - Accepts 'µ' and '^' power notation.
    - Recognizes trailing '/100cm^2' or '/100cm**2' and converts to per m^2 using SURFACE_AREA_BUNDLE.
    - Blocks counts/cpm/cps for safety (convert counts→activity separately).
    """
    unit_norm = _normalize_unit_text(unit)

    _guard_counts(unit_norm)

    if _BUNDLE_RE.search(unit_norm):
        base_unit = _BUNDLE_RE.sub("", unit_norm)  # remove the trailing bundle suffix
        q = Q_(value, base_unit) / SURFACE_AREA_BUNDLE
        # Preserve your original behavior: coerce to Bq/m^2
        return q.to("becquerel / meter**2")
    else:
        return Q_(value, unit_norm)

def convert_to(qty: Q_, target_unit: str) -> Q_:
    """
    Convert a Quantity to a target unit while enforcing safety on counts.
    """
    target_norm = _normalize_unit_text(target_unit)
    _guard_counts(str(qty.units))
    _guard_counts(target_norm)
    return qty.to(target_norm)

# --------------- Optional: convenience lists for UIs/tests ----------------
# These are safe, curated unit menus by category (you can import in your UIs).
ACTIVITY_UNITS: list[str]   = ["Bq", "kBq", "MBq", "GBq", "TBq", "Ci", "mCi", "uCi", "nCi", "pCi", "dpm"]
DOSE_UNITS: list[str]       = ["Sv", "mSv", "uSv", "rem", "mrem"]
DOSE_RATE_UNITS: list[str]  = ["Sv/h", "mSv/h", "uSv/h", "rem/h", "mrem/h"]
TIME_UNITS: list[str]       = ["s", "min", "h", "d", "yr"]

def list_units(category: str) -> list[str]:
    cats = {
        "activity": ACTIVITY_UNITS,
        "dose": DOSE_UNITS,
        "dose_rate": DOSE_RATE_UNITS,
        "time": TIME_UNITS,
    }
    if category not in cats:
        raise ValueError(f"Unknown category '{category}'. Choose from {list(cats)}")
    return list(cats[category])
