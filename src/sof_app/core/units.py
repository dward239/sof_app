from __future__ import annotations
from pint import UnitRegistry

ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = ureg.Quantity

ureg.define("dpm = 1/60 * becquerel = disintegrations_per_minute")
ureg.define("count = []")

SURFACE_AREA_BUNDLE = Q_(100, "centimeter**2")

def parse_quantity(value: float, unit: str):
    unit = unit.strip().replace(" ", "")
    if "/100cm^2" in unit.lower():
        base_unit = unit.lower().replace("/100cm^2", "")
        q = Q_(value, base_unit) / SURFACE_AREA_BUNDLE
        return q.to("becquerel / meter**2")
    else:
        q = Q_(value, unit)
        return q

def convert_to(qty: Q_, target_unit: str) -> Q_:
    return qty.to(target_unit)
