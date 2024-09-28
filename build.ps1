# To avoid false positives on anti-virus systems, you should compile pyinstaller from scratch
#$Env:PYINSTALLER_COMPILE_BOOTLOADER = "true"
#pip install --force-reinstall --ignore-installed --no-binary :all: pyinstaller

# To run both executables from a single python (saves ~20mb) you can use the following
#pyi-makespec.exe .\src\AIGUI.py --noconsole --add-data .\docs\screen\EDAI_logo.png:.\screen
#pyi-makespec.exe .\src\Chat.py --add-data $env:APPDATA\Python\Python38\site-packages\pysilero_vad\models\silero_vad.onnx:.\pysilero_vad\models --add-data $env:APPDATA\Python\Python38/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll:.
# next merge the two files accoring to https://pyinstaller.org/en/stable/spec-files.html?highlight=spec-files#multipackage-bundles and save as bundle.spec
#pyinstaller.exe bundle.spec

# To create both onedir solutions, you can use the following
pyinstaller.exe .\src\AIGUI.py -y --onedir --clean --noconsole --add-data .\screen\EDAI_logo.png:.\screen
pyinstaller.exe .\src\Chat.py -y --onedir --clean --console --hidden-import=comtypes.stream --add-data $env:APPDATA\Python\Python38\site-packages\pysilero_vad\models\silero_vad.onnx:.\pysilero_vad\models --add-binary $env:APPDATA\Python\Python38/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll:.
pyinstaller.exe .\src\AIServer.py -y --onedir --clean --console --hidden-import=comtypes.stream --add-binary $env:APPDATA\Python\Python38/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll:.
$commitId = git rev-parse HEAD
Write-Output "Current HEAD's commit ID: $commitId"

$start=@"
@echo off
start "" .\AIGUI\AIGUI.exe --chat=Chat\Chat.exe --release=$commitId
exit
"@
$start | Out-File -Encoding ASCII .\dist\start.bat