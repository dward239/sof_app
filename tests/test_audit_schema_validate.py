import json
from pathlib import Path

import pytest
from sof_app.services.audit import build_audit_record

try:
    from jsonschema import Draft202012Validator
except ImportError:
    pytest.skip("Install jsonschema to validate audit output", allow_module_level=True)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "data" / "schema" / "audit_schema.json"


def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))


def test_schema_is_valid():
    Draft202012Validator.check_schema(schema())


def test_generated_audit_matches_schema():
    record = build_audit_record(
        {"samples_path": None, "limits_path": None, "options": {}},
        {
            "summary": {"sof_total": 0.5, "status": "PASS",
                        "pass_limit": True, "margin_to_1": 0.5},
            "per_nuclide": [{"nuclide": "Cs-137", "fraction": 0.5}],
        },
    )
    Draft202012Validator(schema()).validate(record)


def test_validate_external_audit_if_present(monkeypatch):
    import os
    path = os.getenv("SOF_TEST_AUDIT")
    if not path or not Path(path).is_file():
        pytest.skip("SOF_TEST_AUDIT not set to a JSON file")
    Draft202012Validator(schema()).validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )
