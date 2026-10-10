# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'sounddevice', 'soundfile', 'noisereduce', 'scipy.signal', 'rapidfuzz', 'ddgs', 'html2text', 'trafilatura', 'playwright', 'keyboard', 'pycaw', 'comtypes', 'openai', 'yaml', 'PIL', 'faster_whisper']
hiddenimports += collect_submodules('PySide6')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('modes.yaml', '.'), ('config/config.example.yaml', 'config')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pandas', 'IPython', 'jupyter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='COMPUTER_Companion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='COMPUTER_Companion',
)
