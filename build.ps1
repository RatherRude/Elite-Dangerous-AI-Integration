#pyi-makespec.exe .\AIGUI.py --noconsole --add-data .\screen\EDAI_logo.png:.\screen
#pyi-makespec.exe .\Chat.py --add-data $env:APPDATA\Python\Python38\site-packages\pysilero_vad\models\silero_vad.onnx:.\pysilero_vad\models --add-data $env:APPDATA\Python\Python38/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll:.
# next merge the two files accoring to https://pyinstaller.org/en/stable/spec-files.html?highlight=spec-files#multipackage-bundles and save as bundle.spec
#pyinstaller.exe bundle.spec


pyinstaller.exe .\AIGUI.py -y --noconsole --add-data .\screen\EDAI_logo.png:.\screen
pyinstaller.exe .\Chat.py -y --console --add-data $env:APPDATA\Python\Python38\site-packages\pysilero_vad\models\silero_vad.onnx:.\pysilero_vad\models --add-data $env:APPDATA\Python\Python38/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll:.
$start=@'
@echo off
start "" .\AIGUI\AIGUI.exe --chat=Chat\Chat.exe
exit
'@
$start | Out-File -Encoding ASCII .\dist\start.bat