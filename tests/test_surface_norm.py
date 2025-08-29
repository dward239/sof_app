from sof_app.core.units import parse_quantity, convert_to

def test_surface_100cm2_to_m2():
    # Example: 600 dpm per 100 cm^2 -> 1000 Bq/m^2
    q = parse_quantity(600, "dpm/100 cm^2")
    out = convert_to(q, "Bq/m^2")
    assert abs(out.magnitude - 1000) < 1e-6
