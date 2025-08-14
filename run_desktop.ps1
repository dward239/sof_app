Set-Location $PSScriptRoot
Set-ExecutionPolicy -Scope Process Bypass
$env:SOF_ALIAS_PATH = (Resolve-Path "$PSScriptRoot\data\nuclide_aliases.csv").Path
. .\.venv\Scripts\Activate.ps1
# comment next line if you already created the .pth file earlier
$env:PYTHONPATH = (Resolve-Path .\src).Path
python .\src\sof_app\ui_qt.py
