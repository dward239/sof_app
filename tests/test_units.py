import math
import pytest

from sof_app.core.units import Q_, parse_quantity, convert_to, list_units

RTOL = 1e-12

# -----------------------
# Original tests
# -----------------------
def test_surface_unit_parsing():
    q = parse_quantity(600, "dpm/100 cm^2")
    q2 = convert_to(q, "becquerel / meter**2")
    assert abs(q2.magnitude - q.magnitude) < 1e-9

def test_mass_concentration():
    q = parse_quantity(1.0, "Bq/g")
    qkg = convert_to(q, "Bq/kg")
    assert abs(qkg.magnitude - 1000.0) < 1e-12

# -----------------------
# Added coverage
# -----------------------
@pytest.mark.parametrize(
    "value,unit,expected_bq_per_m2",
    [
        (600, "dpm/100 cm^2", 1000.0),          # 600 dpm = 10 Bq; /0.01 m^2 = 1000
        (1.0, "MBq/100cm^2", 1.0e8),            # 1e6 / 0.01
        (2.0, "mCi/100cm^2", 7.4e9),            # 2 mCi = 7.4e7 Bq; /0.01 = 7.4e9
        (3.0, "kBq/100cm**2", 3.0e3 / 0.01),    # caret/asterisk variants
    ],
)
def test_per_100cm2_variants(value, unit, expected_bq_per_m2):
    q = parse_quantity(value, unit)
    got = convert_to(q, "Bq/m^2").magnitude
    assert math.isclose(got, expected_bq_per_m2, rel_tol=RTOL)

def test_activity_curie_to_bq_and_prefixes():
    assert math.isclose(convert_to(Q_(1, "Ci"), "Bq").magnitude, 3.7e10, rel_tol=RTOL)
    assert math.isclose(convert_to(Q_(10, "mCi"), "Bq").magnitude, 3.7e8, rel_tol=RTOL)
    assert math.isclose(convert_to(Q_(1, "TBq"), "Ci").magnitude, 1e12/3.7e10, rel_tol=RTOL)

def test_dose_and_dose_rate_conversions():
    assert math.isclose(convert_to(Q_(1, "rem"), "Sv").magnitude, 0.01, rel_tol=RTOL)
    assert math.isclose(convert_to(Q_(10, "mrem"), "mSv").magnitude, 0.1, rel_tol=RTOL)
    assert math.isclose(convert_to(Q_(100, "uSv/h"), "mrem/h").magnitude, 10.0, rel_tol=RTOL)
    assert math.isclose(convert_to(Q_(100, "µSv/h"), "mrem/h").magnitude, 10.0, rel_tol=RTOL)

def test_time_year_to_hours():
    assert math.isclose(convert_to(Q_(1, "yr"), "h").magnitude, 8766.0, rel_tol=RTOL)

def test_unit_string_normalization_micro_and_caret():
    q1 = parse_quantity(123.0, "uSv/h")
    q2 = parse_quantity(123.0, "µSv/h")
    assert math.isclose(convert_to(q1, "Sv/h").magnitude, convert_to(q2, "Sv/h").magnitude, rel_tol=RTOL)
    q3 = parse_quantity(1.0, "Bq/cm^2")
    q4 = parse_quantity(1.0, "Bq/cm**2")
    assert math.isclose(convert_to(q3, "Bq/m^2").magnitude, convert_to(q4, "Bq/m^2").magnitude, rel_tol=RTOL)

def test_dps_alias_equals_bq():
    q = parse_quantity(5.0, "dps")
    assert math.isclose(convert_to(q, "Bq").magnitude, 5.0, rel_tol=RTOL)

def test_block_counts_on_parse():
    with pytest.raises(ValueError):
        parse_quantity(1000.0, "cpm")
    with pytest.raises(ValueError):
        parse_quantity(1.0, "count/s")

def test_block_counts_on_convert_target():
    with pytest.raises(ValueError):
        convert_to(Q_(1.0, "Bq"), "counts")
    with pytest.raises(ValueError):
        convert_to(Q_(1.0, "Bq"), "count/s")

def test_list_units_categories_have_expected_members():
    assert "uCi" in list_units("activity")
    assert "mrem" in list_units("dose")
    assert "uSv/h" in list_units("dose_rate")
    assert "yr" in list_units("time")
