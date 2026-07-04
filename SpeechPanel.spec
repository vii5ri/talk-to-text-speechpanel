# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import os

# ── Collect assets ────────────────────────────────────────────────────────────
added_datas = collect_data_files('customtkinter')
added_datas += [('speech_panel.ico', '.')]

added_binaries = collect_dynamic_libs('sounddevice')

a = Analysis(
    ['speech_panel.py'],
    pathex=[],
    binaries=added_binaries,
    datas=added_datas,
    hiddenimports=[
        # GUI
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        # Audio / STT
        'speech_recognition',
        'sounddevice',
        '_sounddevice_data',
        'soundfile',
        'numpy',
        'numpy.core._multiarray_umath',
        # Translation / clipboard
        'deep_translator',
        'pyperclip',
        'keyboard',
        # Google Cloud STT (optional)
        'google.cloud.speech',
        'google.cloud.speech_v1',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.grpc',
        'google.auth.transport.requests',
        'google.api_core',
        'grpc',
        'grpc._channel',
        'proto.marshal',
        # Misc
        'pkg_resources.py2_warn',
    ],
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
    [],
    exclude_binaries=True,   # one-folder build (faster startup, more compatible)
    name='SpeechPanel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='speech_panel.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SpeechPanel',
)
