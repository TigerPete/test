@echo off
REM Start the Document Q&A web app (no terminal commands needed after setup).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Double-click setup.bat first.
    pause
    exit /b 1
)

echo Starting Document Q&A in your browser...
echo Close this window to stop the app.
echo.
.venv\Scripts\python.exe -m streamlit run app.py
pause
