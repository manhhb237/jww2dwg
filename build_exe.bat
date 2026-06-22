@echo off
echo Building JWW to DWG Converter...
call ..\venv\Scripts\activate.bat
pip install pyinstaller
pyinstaller --noconfirm --windowed --onefile --icon=app_icon.ico --name "JwwToDwgConverter" --collect-all sv_ttk --add-data "app_icon.ico;." app.py
echo Build complete! Executable is in the 'dist' folder.
pause
