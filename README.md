# SOF Method App

![CI](https://github.com/dward239/sof_app/actions/workflows/ci.yml/badge.svg?branch=main)


An auditable **desktop (PyQt6)** application that computes **Sum of Fractions (SOF)** for mixtures of radionuclides against a selected limits table. Designed for screening/engineering use with clear assumptions, unit rigor, and an audit trail.

> **Safety**: This tool is for planning/compliance screening. **All outputs require qualified professional review** before operational use or regulatory submittal.
> **Counts (`counts`, `cpm`, `cps`) are intentionally blocked in conversions** — convert counts → activity via a dedicated efficiency/geometry method before using SOF.

---

## Local repository path

```
C:\sof_app
```

---

## Features (v0.1.1 locked)

* **SOF compute** vs. limits table with unit conversion.
* Optional **combine duplicates**; **treat missing as zero**.
* **Display significant figures** (internal precision 6; display 3–4).
* **Nuclide alias map** loaded from `SOF_ALIAS_PATH` (10 CFR 71 App A-based + lab aliases).
* **Canonicalization** of names (e.g., `Cs137` → `Cs-137`).
* **Audit JSON** includes app version & inputs for reproducibility.
* **Desktop UI (PyQt6)** with drag–drop file paths, options, and a **big summary banner** (SOF / Pass / Margin; green/red).
* **Units library** with curated radiological conversions:

  * Activity: `Bq`, `kBq`, `MBq`, `GBq`, `TBq`, `Ci`, `mCi`, `uCi`, `nCi`, `pCi`, `dpm`
  * Dose: `Sv`, `mSv`, `uSv`, `rem`, `mrem`
  * Dose rate: `Sv/h`, `mSv/h`, `uSv/h`, `rem/h`, `mrem/h`
  * Time: `s`, `min`, `h`, `d`, `yr`
  * **Surface contamination**: inputs like `MBq/100 cm^2` auto-normalized to **Bq/m²**
* **Counts/cpm/cps blocked** in parse/convert (safety).

> Working copy may be `0.1.2-dev` if you’ve bumped locally.

---

## Repository layout

```
C:\sof_app
  src\sof_app\...
    core\                # units, exceptions
    io\                  # excel_loader, exporters
    services\            # sof.py (engine), matching.py (canon), aliases.py, audit.py
    ui_qt.py             # desktop UI (big summary banner)
  data\                  # example CSVs + nuclide_aliases.csv
  tests\                 # unit tests (units, matching, sof)
  run_desktop.ps1        # sets SOF_ALIAS_PATH and launches desktop UI
  .venv\                 # local virtual environment
  .github\workflows\ci.yml
  .gitignore             # ignores release/, dist/, *.zip, *.exe, results/
```

---

## Prerequisites

* **Python 3.10–3.12**
* **Windows PowerShell** (commands below use full paths)

---

## Setup (Windows PowerShell)

```powershell
# 1) Create and activate a virtual environment
python -m venv C:\sof_app\.venv
. C:\sof_app\.venv\Scripts\Activate.ps1

# 2) Editable install (uses pyproject.toml)
pip install -e C:\sof_app
```

---

## Run the desktop app (PyQt6)

**Option A — Direct**

```powershell
. C:\sof_app\.venv\Scripts\Activate.ps1
python C:\sof_app\src\sof_app\ui_qt.py
```

**Option B — Helper script (sets `SOF_ALIAS_PATH`)**

```powershell
. C:\sof_app\.venv\Scripts\Activate.ps1
Set-ExecutionPolicy -Scope Process Bypass
powershell -ExecutionPolicy Bypass -File C:\sof_app\run_desktop.ps1
```

> **Alias file path** (default):
> `C:\sof_app\data\nuclide_aliases.csv`
> `run_desktop.ps1` sets:
>
> ```powershell
> $env:SOF_ALIAS_PATH = "C:\sof_app\data\nuclide_aliases.csv"
> ```

---

## Using the app

1. Launch the desktop UI.
2. **Drag & drop** input file paths (e.g., measurement CSVs).
3. Choose options:

   * Combine duplicates
   * Treat missing as zero
   * Display significant figures
4. Click **Compute SOF**. The **banner** shows SOF value, **Pass/Fail**, and **Margin** (green/red).
5. Save outputs:

   * **CSV results** (to your chosen `results\` path)
   * **Audit JSON** (includes app version, inputs, assumptions)

---

## Units & conversions (library usage)

Core file:

```
C:\sof_app\src\sof_app\core\units.py
```

Examples (Python):

```python
from sof_app.core.units import Q_, parse_quantity, convert_to

# Activity: Ci ↔ Bq (prefixes supported)
convert_to(Q_(1, "Ci"), "Bq")             # 3.7e10 Bq
convert_to(Q_(10, "mCi"), "MBq")          # 0.37 MBq

# Dose & dose-rate
convert_to(Q_(10, "mrem"), "mSv")         # 0.1 mSv
convert_to(Q_(100, "uSv/h"), "mrem/h")    # 10 mrem/h
convert_to(Q_(100, "µSv/h"), "mrem/h")    # 10 mrem/h (µ recognized)

# Surface contamination: “per 100 cm^2” auto-normalized to Bq/m^2
q = parse_quantity(600, "dpm/100 cm^2")   # → 1000 Bq/m^2
convert_to(q, "Bq/m^2")

# Safety: counts are blocked in conversions
# parse_quantity(1000, "cpm")               # raises ValueError
# convert_to(Q_(1, "Bq"), "counts")         # raises ValueError
```

---

## Tests

Test suite path:

```
C:\sof_app\tests
```

Run:

```powershell
. C:\sof_app\.venv\Scripts\Activate.ps1
pytest -q C:\sof_app\tests\test_units.py
```

The suite covers:

* Surface unit parsing (`/100 cm^2` → `Bq/m^2`)
* Bq ↔ Ci (with prefixes), Sv ↔ rem, dose-rate, time
* `µ` vs `u` and `^` vs `**` normalization
* Blocking of `count(s)`, `cpm`, `cps` in parse/convert
* Curated unit lists per category

> **Tip**: ensure this exists for imports without installing a wheel:
> `C:\sof_app\tests\conftest.py` adds `src` to `PYTHONPATH`.

---

## Continuous Integration (GitHub Actions)

Workflow file:

```
C:\sof_app\.github\workflows\ci.yml
```

* Runs on **Windows** for Python **3.10–3.12**
* Installs package and runs **pytest** on every push/PR

Push a change to trigger CI:

```powershell
cd C:\sof_app
git add .
git commit -m "Trigger CI"
git push
```

---

## Data & aliases

* Example data and the nuclide alias map live in: `C:\sof_app\data`
* Alias CSV: `C:\sof_app\data\nuclide_aliases.csv`
* To refresh aliases within a session, restart the app

---

## Versioning & releases

* **Locked version:** `v0.1.1 (Revision 1)`
* **Working copy:** may be `0.1.2-dev`
* **Releases/EXEs are not committed** — upload installers to **GitHub Releases** instead.
  `.gitignore` excludes `release\`, `dist\`, `*.zip`, `*.exe`, `results\`.

> If you build an EXE (e.g., with PyInstaller), store it under `release\` locally and attach it to a GitHub Release. Keep the repo clean.

---

## Configuration

* **Environment variable**: `SOF_ALIAS_PATH`
  Default (set by `run_desktop.ps1`): `C:\sof_app\data\nuclide_aliases.csv`
* **Significant figures**: internal precision 6; display 3–4.
* **Units**: SI defaults; activity in **Bq** (also **Ci**), dose-rate in **µSv/h** (also **mrem/h**).

---

## Troubleshooting

**`pyproject.toml: Invalid statement (line 1, col 1)`**
Save `C:\sof_app\pyproject.toml` as **UTF-8 (no BOM)** or **ASCII**. Minimal known-good content:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sof-app"
version = "0.1.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

**Imports fail in tests**
Ensure `C:\sof_app\tests\conftest.py` adds `src` to `PYTHONPATH`.

**Counts data**
Counts (`counts`, `cpm`, `cps`) cannot be converted directly — use an explicit efficiency/geometry conversion to activity (outside this converter), then feed activity values to SOF.

---

## Roadmap / open ideas

* “Reload aliases” button + popup listing unmapped names.
* Table header & row font size tweaks for readability.
* “Top contributors” bar chart and row color by fraction.
* Optional helper: **counts → activity** (asks for efficiency; writes converted CSV).
* GitHub Actions: add Ubuntu/macOS matrix and coverage artifact.

---

## License

SOF Method App

Copyright 2025 Dylan Ward

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

**Disclaimer**: This is a screening-level engineering tool. **Professional review is required** before operational use or regulatory submittal.
## Responsible Use

This tool is intended for screening-level engineering/compliance workflows.
Results require qualified professional review before operational or regulatory use.
Counts units (counts/cpm/cps) must be converted to activity using an appropriate
efficiency/geometry method outside this app.

