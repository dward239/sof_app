import os, json, pytest
try:
    from jsonschema import Draft7Validator, validate
except Exception:  # pragma: no cover
    pytest.skip("jsonschema not installed; run `pip install jsonschema` to enable", allow_module_level=True)

SCHEMA_PATH = os.path.join("data", "schema", "audit_schema.json")

def test_audit_schema_is_valid():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    Draft7Validator.check_schema(schema)

def test_validate_user_audit_json_if_present():
    p = os.getenv("SOF_TEST_AUDIT")
    if not p or not os.path.exists(p):
        pytest.skip("Set SOF_TEST_AUDIT to path of an audit JSON to validate")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    with open(p, "r", encoding="utf-8") as f:
        doc = json.load(f)
    Draft7Validator.check_schema(schema)
    validate(doc, schema)
