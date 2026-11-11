import pandas as pd
from sof_app.services.sof import compute_sof

def test_single_nuclide_sof():
    samples = pd.DataFrame({
        "nuclide": ["Cs-137"],
        "value": [1.0],
        "unit": ["Bq/g"],
    })
    limits = pd.DataFrame({
        "nuclide": ["Cs-137"],
        "limit_value": [2.0],
        "limit_unit": ["Bq/g"],
    })
    per, summary = compute_sof(samples, limits)
    assert abs(summary["sof_total"] - 0.5) < 1e-12

def test_mixed_units():
    samples = pd.DataFrame({
        "nuclide": ["Cs-137"],
        "value": [1.0],
        "unit": ["Bq/g"],
    })
    limits = pd.DataFrame({
        "nuclide": ["Cs-137"],
        "limit_value": [2000.0],
        "limit_unit": ["Bq/kg"],
    })
    per, summary = compute_sof(samples, limits)
    assert abs(summary["sof_total"] - 0.5) < 1e-12
