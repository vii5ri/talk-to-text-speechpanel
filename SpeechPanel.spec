# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import os, glob, site

# ── Collect assets ────────────────────────────────────────────────────────────
added_datas = collect_data_files('customtkinter')
added_datas += [('speech_panel.ico', '.')]

# faster_whisper ships a few data files (e.g. assets)
try:
    added_datas += collect_data_files('faster_whisper')
except Exception:
    pass
try:
    added_datas += collect_data_files('ctranslate2')
except Exception:
    pass

# ── Collect binaries ──────────────────────────────────────────────────────────
added_binaries = collect_dynamic_libs('sounddevice')

# CTranslate2 native DLLs (Whisper GPU backend)
try:
    added_binaries += collect_dynamic_libs('ctranslate2')
except Exception:
    pass

# Bundle NVIDIA CUDA DLLs so Whisper GPU works in the .exe
for _sp in site.getsitepackages():
    for _pkg in ('cublas', 'cudnn', 'cuda_runtime', 'cuda_nvrtc', 'cusolver', 'cusparse'):
        _dll_dir = os.path.join(_sp, 'nvidia', _pkg, 'bin')
        if os.path.isdir(_dll_dir):
            for _dll in glob.glob(os.path.join(_dll_dir, '*.dll')):
                added_binaries.append((_dll, '.'))

# ── Analysis ──────────────────────────────────────────────────────────────────
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
        # System tray
        'pystray',
        'pystray._win32',
        # Audio / STT
        'speech_recognition',
        'sounddevice',
        '_sounddevice_data',
        'soundfile',
        'numpy',
        'numpy.core._multiarray_umath',
        # Whisper GPU
        'faster_whisper',
        'ctranslate2',
        'tokenizers',
        'huggingface_hub',
        'huggingface_hub.utils',
        'tqdm',
        'av',
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
