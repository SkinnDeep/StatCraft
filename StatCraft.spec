# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launch_modern.py'],
    pathex=['C:/Users/funny/Documents/Codex/2026-10-12/us/work/statcraft'],
    binaries=[],
    datas=[('C:/Users/funny/Documents/Codex/2026-10-12/us/work/statcraft/notices', 'notices'), ('C:/Users/funny/Documents/Codex/2026-10-12/us/work/statcraft/StatCraft.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'pandas', 'matplotlib', 'IPython', 'pytest'],
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
    name='StatCraft',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/funny/Documents/Codex/2026-10-12/us/work/statcraft/StatCraft.ico'],
)
