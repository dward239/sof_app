import math
import numpy as np
import pandas as pd
import pytest

from sof_app.core.exceptions import NuclideNotFoundError
from sof_app.services.sof import compute_sof


def samples(names, values, units, **columns):
    return pd.DataFrame({"nuclide": names, "value": values, "unit": units, **columns})


def limits(names, values, units, **columns):
    return pd.DataFrame({
        "nuclide": names, "limit_value": values, "limit_unit": units, **columns
    })


def test_reference_sof_and_exact_boundary():
    s = samples(["Cs-137", "Co-60"], [0.25, 0.25], ["Ci", "Ci"])
    l = limits(["Cs-137", "Co-60"], [0.5, 0.5], ["Ci", "Ci"])
    _, result = compute_sof(s, l)
    assert result["sof_total"] == pytest.approx(1.0)
    assert result["status"] == "PASS"
    assert result["pass_limit"] is True


def test_unmatched_nuclide_rejected_by_default():
    s = samples(["Cs-137", "Co-60"], [0.5, 0.2], ["Ci", "Ci"])
    l = limits(["Cs-137"], [1.0], ["Ci"])
    with pytest.raises(NuclideNotFoundError):
        compute_sof(s, l)


def test_unmatched_nuclide_explicitly_skipped_is_incomplete_not_pass():
    s = samples(["Cs-137", "Co-60"], [0.5, 0.2], ["Ci", "Ci"])
    l = limits(["Cs-137"], [1.0], ["Ci"])
    out, result = compute_sof(s, l, treat_missing_as_zero=True)
    assert len(out) == 1
    assert result["sof_total"] == pytest.approx(0.5)
    assert result["status"] == "INCOMPLETE"
    assert result["pass_limit"] is None
    assert result["margin_to_1"] is None
    assert result["missing_limit_for_samples"] == ["Co-60"]
    assert np.isnan(out["allowed_additional_in_limit_units"].iloc[0])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -0.1, "bad"])
def test_invalid_sample_measurement_rejected(value):
    with pytest.raises(ValueError):
        compute_sof(samples(["Cs-137"], [value], ["Bq"]),
                    limits(["Cs-137"], [1.0], ["Bq"]))


@pytest.mark.parametrize("value", [0, -5, float("nan"), float("inf")])
def test_invalid_limit_rejected(value):
    with pytest.raises(ValueError):
        compute_sof(samples(["Cs-137"], [0.5], ["Bq"]),
                    limits(["Cs-137"], [value], ["Bq"]))


@pytest.mark.parametrize("sigma", [-1, float("inf"), float("-inf")])
def test_invalid_uncertainty_rejected(sigma):
    with pytest.raises(ValueError):
        compute_sof(samples(["Cs-137"], [1.0], ["Bq"], sigma=[sigma]),
                    limits(["Cs-137"], [10], ["Bq"]))


def test_uncertainty_units_are_converted_with_measurement():
    s = samples(["Cs-137"], [1], ["Bq/g"], sigma=[0.1])
    l = limits(["Cs-137"], [2000], ["Bq/kg"])
    out, summary = compute_sof(s, l)
    assert out.loc[0, "value_conv"] == pytest.approx(1000)
    assert out.loc[0, "sigma_conv"] == pytest.approx(100)
    assert out.loc[0, "fraction"] == pytest.approx(0.5)
    assert out.loc[0, "fraction_sigma"] == pytest.approx(0.05)
    assert summary["sof_sigma"] == pytest.approx(0.05)


def test_duplicate_uncertainties_are_converted_then_quadrature_combined():
    s = samples(["Cs-137", "137Cs"], [1, 1], ["Bq/g", "kBq/kg"],
                sigma=[0.1, 0.2])
    l = limits(["Cs-137"], [4], ["Bq/g"])
    out, summary = compute_sof(s, l)
    assert len(out) == 1
    assert out.loc[0, "value_conv"] == pytest.approx(2)
    assert out.loc[0, "sigma_conv"] == pytest.approx(math.hypot(0.1, 0.2))
    assert summary["sof_sigma"] == pytest.approx(math.hypot(0.1, 0.2) / 4)


def test_partial_uncertainties_are_not_misrepresented_as_complete():
    s = samples(["Cs-137", "Co-60"], [1, 1], ["Bq", "Bq"],
                sigma=[0.1, np.nan])
    l = limits(["Cs-137", "Co-60"], [10, 10], ["Bq", "Bq"])
    _, summary = compute_sof(s, l)
    assert summary["uncertainty_status"] == "partial"
    assert summary["sof_sigma"] is None


def test_different_batches_must_be_evaluated_separately():
    s = samples(["Cs-137", "Cs-137"], [1, 2], ["Bq", "Bq"],
                batch_id=["batch-1", "batch-2"])
    with pytest.raises(ValueError, match="batch"):
        compute_sof(s, limits(["Cs-137"], [10], ["Bq"]))


def test_rule_revisions_cannot_be_silently_combined():
    s = samples(["Cs-137"], [1], ["Bq"])
    l = limits(["Cs-137", "Co-60"], [10, 10], ["Bq", "Bq"],
               rule_rev=["2020", "2025"])
    with pytest.raises(ValueError, match="rule_rev"):
        compute_sof(s, l)


def test_no_matched_nuclides_returns_incomplete_with_opt_in():
    s = samples(["Unknown-999"], [1], ["Bq"])
    l = limits(["Cs-137"], [10], ["Bq"])
    out, summary = compute_sof(s, l, treat_missing_as_zero=True)
    assert out.empty
    assert summary["status"] == "INCOMPLETE"
    assert summary["pass_limit"] is None


def test_mixed_limit_categories_rejected_without_selected_category():
    s = samples(["Cs-137"], [0.1], ["Bq"])
    l = limits(["Cs-137", "Co-60"], [1, 1], ["Bq", "Bq"],
               category=["Transport", "Waste"])
    with pytest.raises(ValueError, match="category"):
        compute_sof(s, l)
    _, result = compute_sof(s, l, category="Transport")
    assert result["status"] == "PASS"


def test_sof_over_one_is_fail_and_margin_negative():
    s = samples(["Cs-137", "Co-60"], [0.6, 0.6], ["Bq", "Bq"])
    l = limits(["Cs-137", "Co-60"], [1.0, 1.0], ["Bq", "Bq"])
    _, result = compute_sof(s, l)
    assert result["sof_total"] == pytest.approx(1.2)
    assert result["status"] == "FAIL"
    assert result["pass_limit"] is False
    assert result["margin_to_1"] == pytest.approx(-0.2)


def test_blank_nuclide_and_infinite_uncertainty_rejected():
    l = limits(["Cs-137"], [1.0], ["Bq"])
    with pytest.raises(ValueError):
        compute_sof(samples([""], [0.1], ["Bq"]), l)
    with pytest.raises(ValueError):
        compute_sof(samples(["Cs-137"], [0.1], ["Bq"],
                            sigma=[float("inf")]), l)
