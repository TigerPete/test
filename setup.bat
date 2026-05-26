@echo off
REM One-time setup: create virtual environment and install dependencies.
cd /d "%~dp0"

echo Creating Python virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo Failed to create venv. Install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo Installing packages (may take a few minutes)...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo pip install failed.
    pause
    exit /b 1
)

echo.
echo Setup complete. Next steps:
echo   1. Install and open Ollama from https://ollama.com
echo   2. In Ollama, download models: llama3.2:3b and nomic-embed-text
echo   3. Double-click run.bat to open the app
echo.
pause
