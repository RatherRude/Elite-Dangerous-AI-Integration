# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Chat.py'],
    pathex=[],
    binaries=[('C:\\Users\\shame\\AppData\\Roaming\\Python\\Python38/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll', '.')],
    datas=[('C:\\Users\\shame\\AppData\\Roaming\\Python\\Python38\\site-packages\\pysilero_vad\\models\\silero_vad.onnx', '.\\pysilero_vad\\models')],
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
