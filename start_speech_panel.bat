@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %ERRORLEVEL% == 0 (
    start "" pythonw "speech_panel.py"
) else (
    start "" python "speech_panel.py"
)
