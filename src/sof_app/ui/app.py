"""Optional Streamlit UI for SOF screening; conservative status semantics."""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from sof_app.io.excel_loader import load_limits, load_samples
from sof_app.services.audit import build_audit_record, file_identity
from sof_app.services.aliases import alias_source_path
from sof_app.services.sof import compute_sof


st.set_page_config(page_title="SOF Calculator", layout="wide")
st.title("Sum of Fractions (SOF) Calculator")
st.caption("Screening only. An incomplete result is never a PASS.")

with st.sidebar:
    st.header("Inputs")
    samples_file = st.file_uploader("Samples (CSV/XLSX)", type=["csv", "xlsx"])
    limits_file = st.file_uploader("Limits (CSV/XLSX)", type=["csv", "xlsx"])
    category = st.text_input("Category filter (optional)")
    combine = st.checkbox("Combine duplicate nuclides (single inventory)", value=True)
    skip_missing = st.checkbox(
        "Exclude missing limits (result INCOMPLETE)", value=False
    )
    run = st.button("Compute SOF", type="primary")

# Invalidate old results whenever file data or selected options change.
current_inputs = None
if samples_file is not None and limits_file is not None:
    current_inputs = {
        "sample_digest": hashlib.sha256(samples_file.getvalue()).hexdigest(),
        "limit_digest": hashlib.sha256(limits_file.getvalue()).hexdigest(),
        "category": category or None,
        "combine": combine,
        "skip_missing": skip_missing,
    }
if ("sof_result" in st.session_state and
        current_inputs != st.session_state["sof_result"]["input_fingerprint"]):
    st.session_state.pop("sof_result", None)
    st.info("Input selections changed. Recompute before exporting.")

if run:
    if samples_file is None or limits_file is None:
        st.error("Upload both sample and limit files.")
    else:
        try:
            samples_blob = samples_file.getvalue()
            limits_blob = limits_file.getvalue()
            alias_identity = file_identity(alias_source_path())
            samples = load_samples(samples_file)
            limits = load_limits(limits_file)
            table, summary = compute_sof(
                samples, limits, category or None,
                combine_duplicates=combine,
                treat_missing_as_zero=skip_missing,
            )
            st.session_state["sof_result"] = {
                "table": table, "summary": summary,
                "input_fingerprint": current_inputs,
                "alias_identity": alias_identity,
                "category": category or None,
                "options": {
                    "combine_duplicates": combine,
                    "treat_missing_as_zero": skip_missing,
                    "display_sigfigs": 4,
                },
                "files": [
                    {
                        "name": samples_file.name,
                        "sha256": hashlib.sha256(samples_blob).hexdigest(),
                        "size_bytes": len(samples_blob),
                    },
                    {
                        "name": limits_file.name,
                        "sha256": hashlib.sha256(limits_blob).hexdigest(),
                        "size_bytes": len(limits_blob),
                    },
                ],
            }
        except Exception as error:
            st.session_state.pop("sof_result", None)
            st.error(f"Calculation rejected: {error}")

if "sof_result" in st.session_state:
    result = st.session_state["sof_result"]
    summary = result["summary"]
    status = summary["status"]
    if status == "PASS":
        st.success("PASS — all input nuclides matched limits")
    elif status == "FAIL":
        st.error("FAIL — computed SOF exceeds 1.0")
    else:
        st.warning(
            "INCOMPLETE — missing limits. This is not a definitive pass or fail."
        )
    c1, c2, c3 = st.columns(3)
    c1.metric("SOF (matched components)", f"{summary['sof_total']:.5g}")
    c2.metric("Status", status)
    c3.metric(
        "Margin to 1",
        "N/A" if summary["margin_to_1"] is None
        else f"{summary['margin_to_1']:.5g}"
    )
    if summary["missing_limit_for_samples"]:
        st.warning("Unmatched: " + ", ".join(summary["missing_limit_for_samples"]))
    st.dataframe(result["table"], use_container_width=True)
    csv = result["table"].to_csv(index=False)
    st.download_button("Download SOF CSV", csv, "per_nuclide.csv", "text/csv")
    inputs = {
        "samples_path": result["files"][0]["name"],
        "limits_path": result["files"][1]["name"],
        "category": result["category"],
        "options": result["options"],
    }
    file_integrity = {
        "samples": {
            "path": result["files"][0]["name"], "exists": False,
            "size_bytes": result["files"][0]["size_bytes"],
            "sha256": result["files"][0]["sha256"],
        },
        "limits": {
            "path": result["files"][1]["name"], "exists": False,
            "size_bytes": result["files"][1]["size_bytes"],
            "sha256": result["files"][1]["sha256"],
        },
        "alias": result["alias_identity"],
    }
    rows = json.loads(result["table"].to_json(orient="records"))
    record = build_audit_record(
        inputs, {"summary": summary, "per_nuclide": rows},
        input_integrity=file_integrity,
    )
    st.download_button(
        "Download audit JSON", json.dumps(record, indent=2),
        "audit.json", "application/json"
    )
