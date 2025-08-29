
---

# SOF Calculator — IT Review & Deployment Guide

This document gives InfoSec/IT everything needed to review, validate, and deploy the SOF Calculator desktop app internally.

## 1) What it is

**SOF Calculator (desktop)** is a local PyQt app that computes **Sum of Fractions (SOF)** against a user-provided limits table. It runs entirely offline.

* UI framework: **PyQt6** (falls back to **PySide6** if PyQt6 isn’t present)
* Inputs: CSV/XLSX files chosen by the user
* Outputs: CSV results and an optional JSON audit file (saved where the user picks)
* Platform focus: Windows

---

## 2) Security & data-flow summary

* **No network usage.** No HTTP/S, sockets, telemetry, analytics, or auto-update.
* **Local file I/O only** (user-selected paths).
* **Settings file**: `%USERPROFILE%\.sof_app_settings.json` (UI preferences only).
* **Optional variable**: `SOF_ALIAS_PATH` (path to local alias CSV).
* **No admin rights**, **no registry writes**, **no services**, **no drivers**.

---

## 3) System requirements

* Windows 10/11 (x64)
* Option A (wheel): Python 3.10–3.12 + ability to install dependencies
* Option B (EXE): none (Python bundled into the executable)

---

## 4) Files/directories touched

* **Reads**: user-selected CSV/XLSX
* **Writes**: user-selected output paths + `%USERPROFILE%\.sof_app_settings.json`
* **Note**: Creates a local `.\results\` folder **only if** the user clicks “Open results folder”.

---

## 5) Build provenance & tag verification

Use Git tags to verify the release source.

```powershell
git clone https://github.com/dward239/sof_app.git
cd sof_app
git fetch --tags
# Inspect the release tag (replace v0.1.4 with current)
git show --no-patch --oneline v0.1.4
git rev-parse "v0.1.4^{commit}"
```

---

## 6) Option A — Review & test from source / wheel (Python present)

```powershell
# Fresh venv
python -m venv .venv
. .\.venv\Scripts\Activate.ps1

# Build + tests
pip install --upgrade pip
pip install build pytest
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue
python -m build
pytest -q .\tests
```

**Expected**: all tests pass (e.g., “17 passed”).

**(Optional) Verify license files embedded in wheel**

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$whl = Get-ChildItem .\dist\*.whl | Sort-Object LastWriteTime -Desc | Select-Object -First 1
$zip = [IO.Compression.ZipFile]::OpenRead($whl.FullName)
$zip.Entries | Where-Object { $_.FullName -match 'dist-info/licenses/' } | Select FullName
$zip.Dispose()
```

---

## 7) Option B — Build a **standalone EXE** (no Python required)

```powershell
. .\.venv\Scripts\Activate.ps1
pip install pyinstaller

pyinstaller --noconfirm --clean `
  --name "SOF-Calculator" `
  --windowed `
  --icon .\src\sof_app\assets\icons\sof_trefoil.ico `
  .\src\sof_app\ui_qt.py

# Output: .\dist\SOF-Calculator\SOF-Calculator.exe
Get-FileHash .\dist\SOF-Calculator\SOF-Calculator.exe -Algorithm SHA256
```

**(Recommended) Code signing**

```powershell
# Example: adjust certificate selection to your org
$cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*Your Company*" } | Select-Object -First 1
Set-AuthenticodeSignature -FilePath .\dist\SOF-Calculator\SOF-Calculator.exe -Certificate $cert
```

---

## 8) Security validation (static & dynamic)

**Static scan for network APIs in source**

```powershell
Select-String -Path .\src\**\*.py `
  -Pattern 'requests|urllib|aiohttp|socket|QNetworkAccessManager|http://|https://' `
  -CaseSensitive
# Expect: no results
```

**Dynamic check: no open TCP connections while app runs**

1. Launch the app:

   ```powershell
   python -m sof_app.ui_qt
   ```
2. In another PowerShell:

   ```powershell
   $p = Get-Process python -ErrorAction SilentlyContinue
   if ($p) { Get-NetTCPConnection -OwningProcess $p.Id } else { "App not running" }
   # Expect: no active connections
   ```

**AV/EDR scan**
Scan wheel/EXE with Windows Defender or your EDR suite and archive the scan report.

**(Optional) Firewall hardening**
Create an outbound-block rule for the EXE (should be a no-op given offline design).

---

## 9) SBOM, licenses, and vulnerability report

```powershell
. .\.venv\Scripts\Activate.ps1
pip install cyclonedx-bom pip-licenses pip-audit

# SBOM (CycloneDX)
cyclonedx-py --format json -o SBOM-cyclonedx.json

# Third-party licenses (include license texts)
pip-licenses --format=markdown --with-urls --with-license-file > THIRD_PARTY_LICENSES.md

# Vulnerability scan
pip-audit --format json > pip-audit.json
```

**Project license**: Apache-2.0 (see `LICENSE` and `NOTICE`).
**Wheel** embeds license files under `*.dist-info\licenses\`.

---

## 10) Distribution checklist (internal)

* [ ] Choose delivery: signed EXE **or** wheel/sdist
* [ ] Include artifacts: `EXE` or `wheel + sdist`, `LICENSE`, `NOTICE`, `SBOM-cyclonedx.json`, `THIRD_PARTY_LICENSES.md`, `pip-audit.json`, `hashes.txt`, this `README-IT.md`
* [ ] Provide tag/commit SHA used to build (e.g., `v0.1.4`)
* [ ] Publish via your software center/package repo
* [ ] (If EXE) Apply code signing; (optional) AppLocker allow-list

Create hashes:

```powershell
Get-ChildItem .\dist\* | Get-FileHash -Algorithm SHA256 | Tee-Object hashes.txt
```

---

## 11) Uninstall / cleanup

* **EXE distribution**: delete the app folder under `.\dist\SOF-Calculator\` (or your install location).
* **Wheel distribution**: uninstall via your package tool or `pip uninstall sof-app`.
* Delete settings file (optional): `%USERPROFILE%\.sof_app_settings.json`.

---

## 12) Change management

* Track releases with Git tags and GitHub Releases.
* Each release should attach the artifacts (EXE or wheel/sdist) plus SBOM, license report, vuln report, and hashes.
* CI should run tests on every commit; releases should be cut from passing builds.

---

## 13) Contact / ownership

* **Maintainer**: Dylan Ward
* **Repository**: [https://github.com/dward239/sof\_app](https://github.com/dward239/sof_app)
* **Issue tracking**: GitHub Issues in the repo

---

