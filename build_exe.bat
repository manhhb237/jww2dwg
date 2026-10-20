@echo off
echo Building JWW to DWG Converter...
cd /d "%~dp0"
if exist "..\venv\Scripts\activate.bat" (
    call ..\venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
pip install pyinstaller
pyinstaller --noconfirm JWW2DWG_Light.spec
echo Build complete! Executable is in the 'dist' folder.
pause
