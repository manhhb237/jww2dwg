@echo off
cd /d "%~dp0"
echo Starting JWW to DWG Batch Converter...
start "" "..\venv\Scripts\pythonw.exe" app.py
