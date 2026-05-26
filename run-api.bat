@echo off
REM Start the HTTP query API (for Docker-style / cloud testing).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Double-click setup.bat first.
    pause
    exit /b 1
)

echo API docs: http://127.0.0.1:8000/docs
echo Health:   http://127.0.0.1:8000/health
echo.
.venv\Scripts\python.exe -m uvicorn rag_agent.api:app --host 127.0.0.1 --port 8000
pause
