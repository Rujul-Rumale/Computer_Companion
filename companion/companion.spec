# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for COMPUTER Companion
# Build: pyinstaller companion.spec
#

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("modes.yaml", "."),
        ("config/config.example.yaml", "config"),
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "sounddevice",
        "soundfile",
        "noisereduce",
        "scipy.signal",
        "numpy",
        "rapidfuzz",
        "ddgs",
        "html2text",
        "trafilatura",
        "playwright",
        "keyboard",
        "pycaw",
        "comtypes",
        "openai",
        "yaml",
        "PIL",
        "faster_whisper",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pandas",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="COMPUTER_Companion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,             # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
