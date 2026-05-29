# -*- mode: python ; coding: utf-8 -*-
import importlib.util, os
_tkdnd = os.path.dirname(importlib.util.find_spec('tkinterdnd2').origin)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(_tkdnd, 'tkinterdnd2')],
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
    name='AbletonProjectChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    icon='AppIcon.ico',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
