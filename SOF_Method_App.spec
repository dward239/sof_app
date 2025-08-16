# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
block_cipher = None

BASE = Path(r"C:\Users\dylan\Documents\SOF_Calculator\sof_app")
ENTRY = BASE / "src" / "sof_app" / "ui_qt.py"
ICON  = BASE / "src" / "sof_app" / "assets" / "icons" / "sof_trefoil.ico"

# Bundle the runtime icon so _resource_path("assets","icons","sof_trefoil.ico") works when frozen
datas = [(str(ICON), "sof_app/assets/icons")]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(BASE)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# one-file build: EXE only (no COLLECT block)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SOF_Method_App",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed app
    icon=str(ICON),         # EXE file icon
)
