# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for The Fold.
#
# Build with:
#   Mac:     ./build/build_mac.sh
#   Windows: build\build_windows.bat
#
# Output:
#   Mac:     dist/The Fold.app
#   Windows: dist/The Fold.exe  (onefile)

import sys
from pathlib import Path

ROOT = Path(SPEC).parent.parent  # one level up from build/

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Bundle read-only data directories into the root of _MEIPASS
        (str(ROOT / 'assets'),  'assets'),
        (str(ROOT / 'levels'),  'levels'),
        (str(ROOT / 'src'),     'src'),
    ],
    hiddenimports=[
        'pygame',
        'pygame.font',
        'pygame.mixer',
        'pygame.transform',
        'dataclasses',
        'json',
        'random',
        'pathlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'PIL',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# --- Mac: directory bundle (.app) ---
if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='The Fold',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='The Fold',
    )
    app = BUNDLE(
        coll,
        name='The Fold.app',
        icon=None,
        bundle_identifier='com.thefold.game',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.15.0',
            'CFBundleShortVersionString': '0.1.0',
        },
    )

# --- Windows: single-file .exe ---
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='The Fold',
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
        icon=None,
    )
