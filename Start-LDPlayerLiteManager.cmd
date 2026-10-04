@echo off
setlocal
set "PATH=%~dp0_internal\PySide6;%~dp0_internal\shiboken6;%~dp0_internal;%SystemRoot%\System32;%SystemRoot%"
set "QT_PLUGIN_PATH=%~dp0_internal\PySide6\plugins"
"%~dp0LDPlayerLiteManager.exe"
endlocal
