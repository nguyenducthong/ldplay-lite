# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["main_compat.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("config", "config"),
        ("templates", "templates"),
        ("PORTABLE-COMPAT-README.txt", "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LDPlayerLiteManager-Dark",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
collect = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LDPlayerLiteManager-Dark",
)
