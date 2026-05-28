# -*- mode: python ; coding: utf-8 -*-

tkdnd2_src = '/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/tkinterdnd2'
ctk_src    = '/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/customtkinter'
# Tcl 9.x compatible tkdnd (the bundled one in tkinterdnd2 is Tcl 8.x only)
tkdnd9_src = '/Library/Frameworks/Python.framework/Versions/3.14/lib/tkdnd2.9.5'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (tkdnd2_src, 'tkinterdnd2'),
        (ctk_src,    'customtkinter'),
        (tkdnd9_src, 'tkdnd9'),
    ],
    hiddenimports=['customtkinter', 'tkinterdnd2', 'AppKit', 'objc', 'Foundation'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_tkdnd_tcl9.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AbletonProjectChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='AppIcon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AbletonProjectChecker',
)

app = BUNDLE(
    coll,
    name='AbletonProjectChecker.app',
    icon='AppIcon.icns',
    bundle_identifier='com.psypad.ableton-project-checker',
    info_plist={
        'CFBundleDisplayName': 'Ableton Project Checker',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.14.0',
        'NSRequiresAquaSystemAppearance': False,
    },
)
