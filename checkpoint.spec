# -*- mode: python ; coding: utf-8 -*-
import os

_assets_dir = os.path.join('src', 'checkpoint', 'assets')
_icon = os.path.join(_assets_dir, 'icon.ico')

a = Analysis(
    ['src\\checkpoint\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[(_assets_dir, 'checkpoint/assets')] if os.path.isdir(_assets_dir) and os.listdir(_assets_dir) else [],
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
    name='checkpoint',
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
    icon=_icon if os.path.exists(_icon) else None,
)
