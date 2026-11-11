import pytest
from sof_app.core.units import parse_quantity, convert_to, Q_

def test_counts_units_blocked_parse():
    for u in ("cpm", "cps", "counts"):
        with pytest.raises(Exception):
            parse_quantity(1000, u)

def test_counts_units_blocked_convert():
    with pytest.raises(Exception):
        convert_to(Q_(1, "Bq"), "counts")
