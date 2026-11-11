# SOF Calculator — IT Build, Security and Deployment

**Source version:** 0.2.0 | **Platform:** Windows x64 | **Use:** screening software requiring qualified review

This document applies to the *new public repository*. Historical 0.1.x tags and release artifacts belong to a separate private archive, not this repo.

## Operational boundaries

The desktop software is designed to work offline using user-selected CSV/XLSX samples and limits. Verify actual offline behavior independently in the packaged build. No administrator rights or installed service should be required.

- Local preferences may be stored as `.sof_app_settings.json` under the user's home directory.
- An optional `SOF_ALIAS_PATH` explicitly overrides the packaged alias CSV.
- Selected input files, resulting CSVs and JSON audits may contain sensitive operational data. Manage file access and retention according to organizational requirements.
- Desktop audit exports include the per-nuclide results and SHA-256 identifiers for input files.

## Reproducible source and test steps

```powershell
git clone https://github.com/dward239/sof_app.git
Set-Location sof_app
git rev-parse HEAD
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[gui]"
python -m pip install pytest jsonschema build pyinstaller
python -m pytest -q tests
python -m build
```

Record the precise source commit, dependency versions, test outcomes and generated artifact hashes.

## Build the Windows EXE

The optional application icon is omitted if it is not in the checkout; the bundled alias CSV is mandatory.

```powershell
$args = @(
  '--noconfirm', '--clean', '--name', 'SOF-Calculator',
  '--windowed',
  '--add-data', 'src/sof_app/data/nuclide_aliases.csv;sof_app/data'
)
if (Test-Path '.\src\sof_app\assets\icons\sof_trefoil.ico') {
  $args += @('--icon', '.\src\sof_app\assets\icons\sof_trefoil.ico')
}
$args += '.\src\sof_app\ui_qt.py'
pyinstaller @args
Get-FileHash .\dist\SOF-Calculator\SOF-Calculator.exe -Algorithm SHA256
```

Validate the EXE on a clean target system, with antivirus/EDR review and a network-activity check. Do not commit signing certificates, keys, local settings or internal input inventories.

## Independent acceptance checklist

1. Hand-calculate at least one passing inventory, one failing inventory, and the SOF = 1 boundary.
2. Confirm missing limits reject by default and explicitly excluded nuclides give INCOMPLETE rather than PASS.
3. Test negative/nonfinite inputs, incompatible units, uncertainty propagation and multi-batch rejection.
4. Verify a packaged alias database and failure on an invalid override.
5. Verify audit traceability and rejection of an export when a source file changes after calculation.
6. Confirm the rule, category, source and revision of limits are applicable and approved for the use case.
7. Test the actual packaged binary and obtain documented professional sign-off.

Passing GitHub Actions CI is not a regulatory qualification.

## Release management

The current public repository has no published release assets. Only create versioned tags and release packages after the required validation. Record source commit, release hashes, SBOM, third-party licenses, vulnerability scan and signing evidence as applicable. Do not assume archived release assets were produced by this new history.

Review [maintainer security controls](docs/MAINTAINER_SECURITY.md) for branch protection, privacy-sensitive commit identities, and automated dependency alerts.

**Maintainer:** [@dward239](https://github.com/dward239). Do not disclose confidential source material in public issues or PRs.
