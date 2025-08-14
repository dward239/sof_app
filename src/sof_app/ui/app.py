from __future__ import annotations
import streamlit as st
from sof_app.io.excel_loader import load_samples, load_limits
from sof_app.services.sof import compute_sof
from sof_app.io.exporters import export_csv
from sof_app.services.audit import write_audit

st.set_page_config(page_title="SOF Calculator", layout="wide")
st.title("Sum of Fractions (SOF) Calculator")

with st.sidebar:
    st.header("Inputs")
    samples_file = st.file_uploader("Samples (Excel/CSV)", type=["xlsx", "xls", "csv"])
    limits_file = st.file_uploader("Limits (Excel/CSV)", type=["xlsx", "xls", "csv"])
    category = st.text_input("Category filter (optional)")
    run_btn = st.button("Compute SOF", type="primary")

assumptions = {
    "treat_missing_as_zero": True,
    "combine_duplicates": True,
    "rounding_display_sigfigs": 4,
}

if run_btn:
    if not samples_file or not limits_file:
        st.error("Please upload both samples and limits files.")
        st.stop()
    try:
        samples = load_samples(samples_file)
        limits = load_limits(limits_file)
        per_nuclide, summary = compute_sof(samples, limits, category or None)
    except Exception as e:
        st.exception(e)
        st.stop()

    st.subheader("Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SOF total", f"{summary['sof_total']:.4g}")
    col2.metric("Pass (â‰¤1)", "Yes" if summary["pass_limit"] else "No")
    col3.metric("Margin to 1", f"{summary['margin_to_1']:.4g}")
    col4.metric("Rule", summary.get("rule_name", ""))

    st.subheader("Per-nuclide contributions")
    st.dataframe(per_nuclide.rename(columns={
        "allowed_additional_in_limit_units": "Allowed additional (limit units)",
    }))

    st.subheader("Export")
    exp_col1, exp_col2 = st.columns(2)
    if exp_col1.button("Download CSV"):
        export_csv(per_nuclide, "results/per_nuclide.csv")
        st.success("Saved to results/per_nuclide.csv")
    if exp_col2.button("Write audit JSON"):
        write_audit("results/audit.json", inputs={"assumptions": assumptions}, results={"summary": summary})
        st.success("Saved to results/audit.json")

    st.caption("Assumptions are recorded in audit JSON. Review units, categories, and rule provenance before use.")
