# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import uiautomation


uiautomation_root = Path(uiautomation.__file__).resolve().parent
uiautomation_binaries = [
    (str(uiautomation_root / "bin" / "UIAutomationClient_VC140_X64.dll"), "uiautomation/bin"),
    (str(uiautomation_root / "bin" / "UIAutomationClient_VC140_X86.dll"), "uiautomation/bin"),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=uiautomation_binaries,
    datas=[("assets/app.ico", "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="YouTubeEndlessScrollBlocker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/app.ico"],
)
