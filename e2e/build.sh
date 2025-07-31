#!/bin/bash

set -e

export VAD_MODEL=$(python3 -c 'import os, pysilero_vad; print(os.path.join(os.path.dirname(pysilero_vad.__file__), "models", "silero_vad.onnx"))')
export VEC_EXTENSION=$(python3 -c 'import os, sqlite_vec; print(os.path.join(os.path.dirname(sqlite_vec.__file__), "vec0.so"))')

echo $VAD_MODEL
echo $VEC_EXTENSION

pyinstaller ./src/Chat.py -y --onedir --console --hidden-import=comtypes.stream --add-data ./src:. --add-data $VAD_MODEL:./pysilero_vad/models --add-binary $VEC_EXTENSION:./sqlite_vec
