@echo off
cd /d "%~dp0"
echo Starting JWW to DWG Batch Converter...
if exist "..\venv\Scripts\pythonw.exe" (
    start "" "..\venv\Scripts\pythonw.exe" app.py
) else if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" app.py
) else (
    start "" pythonw app.py
)
