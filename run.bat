@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found: .venv
    echo Create it with: py -3.11 -m venv .venv
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

start "" "http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

endlocal
