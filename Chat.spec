# -*- mode: python ; coding: utf-8 -*-

import os
import platform
from pathlib import Path

import pysilero_vad
import samplerate
import sqlite_vec


def get_sqlite_vec_binary() -> tuple[str, str]:
    sqlite_vec_dir = Path(sqlite_vec.__file__).resolve().parent
    system = platform.system()
    if system == 'Windows':
        filename = 'vec0.dll'
    elif system == 'Darwin':
        filename = 'vec0.dylib'
    else:
        filename = 'vec0.so'
    return (str(sqlite_vec_dir / filename), './sqlite_vec')


def get_audiostretchy_binary() -> tuple[str, str]:
    import audiostretchy

    audiostretchy_dir = Path(audiostretchy.__file__).resolve().parent
    system = platform.system()
    if system == 'Windows':
        subdir = 'win'
        filename = '_stretch.dll'
    elif system == 'Darwin':
        subdir = 'mac'
        filename = '_stretch.dylib'
    else:
        subdir = 'linux'
        filename = '_stretch.so'
    return (
        str(audiostretchy_dir / 'interface' / subdir / filename),
        os.path.join('audiostretchy', 'interface', subdir),
    )


def get_samplerate_binary() -> tuple[str, str]:
    return (str(Path(samplerate.__file__).resolve()), '.')


a = Analysis(
    ['src/Chat.py'],
    pathex=[],
    binaries=[
        get_sqlite_vec_binary(),
        get_audiostretchy_binary(),
        get_samplerate_binary(),
    ],
    datas=[('./src', '.'), (str(Path(pysilero_vad.__file__).resolve().parent / 'models' / 'silero_vad.onnx'), './pysilero_vad/models')],
    hiddenimports=['comtypes.stream', 'audiostretchy.stretch', 'audiostretchy.interface.tdhs', 'samplerate'],
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
    exclude_binaries=True,
    name='Chat',
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
    name='Chat',
)
