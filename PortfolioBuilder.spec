# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import fitz 

block_cipher = None

# --- LA CORRECTION EST ICI ---
# Au lieu de chercher __file__, on prend le premier chemin du dossier d'installation
fitz_dir = fitz.__path__[0]
# -----------------------------

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    hiddenimports=[
        'fitz', 
        'pymupdf', 
        'python-multipart',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on'
    ],
    datas=[
        ('static', 'static'),
        (fitz_dir, 'fitz'), # On inclut tout le dossier fitz
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
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
    name='PortfolioBuilder',
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
)