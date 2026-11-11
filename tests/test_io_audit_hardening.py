import json
from pathlib import Path

import pytest

from sof_app.services.audit import build_audit_record, file_identity, write_audit
from sof_app.io.excel_loader import load_samples, load_limits
from sof_app.core.exceptions import SchemaError
from sof_app.services.aliases import alias_source_path, canonicalize


def test_alias_table_packaged_or_checked_out():
    path = alias_source_path()
    assert path.is_file()
    assert canonicalize("137Cs")[0] == "Cs-137"


def test_invalid_explicit_alias_override_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("SOF_ALIAS_PATH", str(tmp_path / "missing.csv"))
    with pytest.raises(FileNotFoundError):
        canonicalize("Cs-137")


def test_csv_samples_and_limits(tmp_path):
    samples = tmp_path / "samples.csv"
    limits = tmp_path / "limits.csv"
    samples.write_text("Nuclide,Value,Unit\nCs-137,1,Bq\n", encoding="utf-8")
    limits.write_text("nuclide,limit_value,limit_unit\nCs-137,2,Bq\n", encoding="utf-8")
    assert load_samples(samples)["value"].iloc[0] == 1
    assert load_limits(limits)["limit_value"].iloc[0] == 2


def test_unknown_file_type_and_old_xls_rejected(tmp_path):
    for extension in (".dat", ".xls"):
        path = tmp_path / ("samples" + extension)
        path.write_text("nuclide,value,unit\nCs-137,1,Bq\n")
        with pytest.raises(SchemaError):
            load_samples(path)


def test_audit_integrity_catches_mutated_inputs(tmp_path):
    source = tmp_path / "samples.csv"
    source.write_text("alpha", encoding="utf-8")
    identity = {"samples": file_identity(source),
                "limits": file_identity(None),
                "alias": file_identity(None)}
    inputs = {"samples_path": str(source)}
    results = {"summary": {"sof_total": 0.5,
                           "status": "PASS", "pass_limit": True},
               "per_nuclide": [{"nuclide": "Cs-137", "fraction": 0.5}]}
    output = tmp_path / "audit.json"
    write_audit(output, inputs, results, input_integrity=identity)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["file_integrity"]["samples"]["sha256"] == identity["samples"]["sha256"]
    assert saved["results"]["per_nuclide"][0]["fraction"] == 0.5
    source.write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="changed since calculation"):
        build_audit_record(inputs, results, input_integrity=identity)
