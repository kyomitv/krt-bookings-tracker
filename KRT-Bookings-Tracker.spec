# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/SIMON/dev/krt-bookings-tracker/main.py'],
    pathex=[],
    binaries=[],
    datas=[('E:/SIMON/dev/krt-bookings-tracker/assets', 'assets')],
    hiddenimports=['pystray._win32', 'cryptography', 'requests', 'PIL', 'tkinter'],
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
    name='KRT-Bookings-Tracker',
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
    icon=['E:/SIMON/dev/krt-bookings-tracker/assets/app_icon.ico'],
)
