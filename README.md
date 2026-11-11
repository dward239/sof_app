# SOF Calculator

[![Windows CI](https://github.com/dward239/sof_app/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dward239/sof_app/actions/workflows/ci.yml)
[![Privacy scan](https://github.com/dward239/sof_app/actions/workflows/privacy-scan.yml/badge.svg?branch=main)](https://github.com/dward239/sof_app/actions/workflows/privacy-scan.yml)

**Version 0.2.0** — an auditable radionuclide Sum of Fractions (SOF) screening application with a Qt desktop interface and Python calculation engine. The limits table is supplied by the user; this project does not establish that a particular set of limits is applicable.

> **Engineering limitation:** This tool is for screening only. Qualified professional review, validated reference limits, and independent result verification are required before operational use or regulatory submittal.

## Calculation integrity

| Status | Meaning |
|---|---|
| **PASS** | Complete inventory, valid inputs, calculated SOF at or below 1.0 |
| **FAIL** | Complete inventory, valid inputs, SOF above 1.0 |
| **INCOMPLETE** | Missing-limit nuclides explicitly excluded; the partial SOF is **not a PASS** |

Missing limits raise an error by default. The legacy API parameter `treat_missing_as_zero=True` indicates *explicit exclusion with INCOMPLETE status*; it does not mean an unknown nuclide has zero activity. Invalid or nonfinite inputs, negative values, and mixed sample batches are rejected. Supplied one-sigma uncertainties are converted to consistent units and combined in quadrature under an independence assumption. Counts, cpm, and cps cannot be converted directly to activity.

The desktop audit provides SHA-256 fingerprints and per-nuclide numeric results. A changed input file invalidates pending audit export.

## Install and run on Windows

Requires **Python 3.10–3.12**. All commands are relative to a new checkout, without developer-specific installation paths.

```powershell
git clone https://github.com/dward239/sof_app.git
Set-Location sof_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[gui]"
python -m sof_app.ui_qt
```

The `gui` optional dependency installs PySide6, the default Qt binding. An alternative PyQt6 binding is supported through an explicit `SOF_QT_BINDING=pyqt6` setting. Review applicable Qt licensing terms before redistribution. The provided `run_desktop.ps1` helper assumes a repository-local `.venv`.

## Inputs and outputs

- UTF-8 CSV and XLSX files are supported. Legacy XLS must be converted before loading.
- Sample and limit files must describe matching nuclides and convertible units. Check the rule, category and revision used for limits.
- Example inputs are in [data/](data/). The alias database is packaged with the application, or explicitly overridden with `SOF_ALIAS_PATH`.
- The desktop app saves per-nuclide CSV results and optional JSON audit files to user-selected locations.

Do not combine distinct sample inventories or incompatible limit revisions without proper engineering justification.

## Tests and build

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install pytest jsonschema build
python -m pytest -q tests
python -m build
```

The [Windows CI workflow](.github/workflows/ci.yml) tests Python 3.10, 3.11, and 3.12 and builds packages/EXE on Python 3.12. The [privacy workflow](.github/workflows/privacy-scan.yml) screens current repository text for common workstation identifiers. Successful automation does **not** establish regulatory or engineering validation.

## Releases and provenance

This public repository was initialized with cleaned source and **fresh Git history**. The older history and release packages are retained in a separate private archive. **No releases are yet published from this new repository.** New distributions should originate from reviewed commits on this repository, with validation records, reproducible build provenance and file hashes. See [Releases](https://github.com/dward239/sof_app/releases).

## Source layout

- [Calculation engine](src/sof_app/services/sof.py)
- [Units and models](src/sof_app/core/)
- [Input loaders](src/sof_app/io/)
- [Qt desktop UI](src/sof_app/ui_qt.py)
- [Optional Streamlit UI](src/sof_app/ui/app.py)
- [Regression tests](tests/)
- [IT deployment and validation guide](README-IT.md)
- [Maintainer security checklist](docs/MAINTAINER_SECURITY.md)

## License

Apache-2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). This software does not replace qualified engineering procedures or applicable regulatory requirements.
