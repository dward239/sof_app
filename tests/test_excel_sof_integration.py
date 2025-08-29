import os, pytest
from sof_app.io.excel_loader import load_samples, load_limits
from sof_app.services.sof import compute_sof

@pytest.mark.integration
def test_sof_from_excel_env_paths():
    samp = os.getenv("SOF_TEST_SAMPLES")
    lims = os.getenv("SOF_TEST_LIMITS")
    if not samp or not lims or not os.path.exists(samp) or not os.path.exists(lims):
        pytest.skip("Set SOF_TEST_SAMPLES and SOF_TEST_LIMITS to valid .csv/.xlsx paths")
    samples = load_samples(samp)
    limits  = load_limits(lims)
    per_nuclide, summary = compute_sof(samples, limits,
                                       category=None,
                                       combine_duplicates=True,
                                       treat_missing_as_zero=True,
                                       display_sigfigs=4)
    assert "sof_total" in summary
    assert isinstance(summary["pass_limit"], (bool,)) or summary["pass_limit"] in (True, False)
    assert per_nuclide.shape[0] >= 0
