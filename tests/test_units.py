from sof_app.core.units import parse_quantity, convert_to

def test_surface_unit_parsing():
    q = parse_quantity(600, "dpm/100 cm^2")
    q2 = convert_to(q, "becquerel / meter**2")
    assert abs(q2.magnitude - q.magnitude) < 1e-9

def test_mass_concentration():
    q = parse_quantity(1.0, "Bq/g")
    qkg = convert_to(q, "Bq/kg")
    assert abs(qkg.magnitude - 1000.0) < 1e-12
