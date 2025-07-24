#!/bin/bash

set -e

#export ONNXRUNTIME_DLL=$(python -c 'import os, onnxruntime; print(os.path.join(os.path.dirname(onnxruntime.__file__), "capi", "libonnxruntime_providers_shared.so"))')
#export LLAMACPP_DLL=$(python -c 'import os, llama_cpp; print(os.path.join(os.path.dirname(llama_cpp.__file__), "lib", "libllama.so"))')
export VAD_MODEL=$(python3 -c 'import os, pysilero_vad; print(os.path.join(os.path.dirname(pysilero_vad.__file__), "models", "silero_vad.onnx"))')
export VEC_EXTENSION=$(python3 -c 'import os, sqlite_vec; print(os.path.join(os.path.dirname(sqlite_vec.__file__), "vec0.so"))')

#echo $ONNXRUNTIME_DLL
#echo $LLAMACPP_DLL
echo $VAD_MODEL
echo $VEC_EXTENSION

#pyinstaller ./src/AIGUI.py -y --onedir --noconsole --add-data ./docs/screen/EDAI_logo.png:./screen
pyinstaller ./src/Chat.py -y --onedir --console --hidden-import=comtypes.stream --add-data ./src:. --add-data $VAD_MODEL:./pysilero_vad/models --add-binary $VEC_EXTENSION:./sqlite_vec

#cd dist
#./Chat/Chat