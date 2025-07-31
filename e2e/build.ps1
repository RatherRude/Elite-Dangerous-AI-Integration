$ErrorActionPreference = 'Stop'

# Get VAD model path
$VAD_MODEL = python -c "import os, pysilero_vad; print(os.path.join(os.path.dirname(pysilero_vad.__file__), 'models', 'silero_vad.onnx'))"
# Get VEC extension path
$VEC_EXTENSION = python -c "import os, sqlite_vec; print(os.path.join(os.path.dirname(sqlite_vec.__file__), 'vec0.dll'))"

Write-Host $VAD_MODEL
Write-Host $VEC_EXTENSION

pyinstaller ./src/Chat.py -y --onedir --console --hidden-import=comtypes.stream --add-data ./src:. --add-data ${VAD_MODEL}:./pysilero_vad/models --add-binary ${VEC_EXTENSION}:./sqlite_vec
