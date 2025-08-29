# IT Validation Playbook — SOF Calculator (Desktop)

**Goal:** Validate supply chain, binary integrity, offline posture, and licensing before distribution.

## SBOM & license (build-time only)
```powershell
python -m cyclonedx_py venv --output-format json -o .\dist\SBOM.json
pip-licenses --with-urls --format=json --output-file .\dist\THIRD_PARTY_LICENSES.json

```
