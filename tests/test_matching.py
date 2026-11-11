from sof_app.services.matching import to_canonical

def test_canonical_forms():
    assert to_canonical("137Cs") == "Cs-137"
    assert to_canonical("cs137") == "Cs-137"
    assert to_canonical("Cs-137") == "Cs-137"
    assert to_canonical("99mTc") == "Tc-99m"
    assert to_canonical("TC99M") == "Tc-99m"
