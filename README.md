# SOF Method App

This repository provides a small, auditable application that computes **Sum of Fractions (SOF)** for mixtures of radionuclides against a selected limits table.

## Quick start
PowerShell:
    python -m venv .venv
    . .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    streamlit run .\src\sof_app\ui\app.py

Run tests:
    pytest -q

Disclaimer: Results are for planning/compliance screening and require professional review before operational use or regulatory submittal.
