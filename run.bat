@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Virtual environment not found: .venv
    echo.
    echo Create it with:
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements-cpu.txt
    pause
    exit /b 1
)

echo Python: %PYTHON%
echo Checking port 8000...

set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
    if not defined PORT_PID set "PORT_PID=%%P"
)

if defined PORT_PID (
    echo Port 8000 is already used by PID !PORT_PID!.
    set /p "STOP_PROCESS=Stop only this process and continue? [Y/N]: "
    if /I not "!STOP_PROCESS!"=="Y" (
        echo Startup cancelled. Port 8000 is still occupied by PID !PORT_PID!.
        pause
        exit /b 1
    )

    taskkill /PID !PORT_PID! /F
    if errorlevel 1 (
        echo Could not stop PID !PORT_PID!. Startup cancelled.
        pause
        exit /b 1
    )
    timeout /t 1 /nobreak >nul
)

for /f %%T in ('powershell.exe -NoProfile -Command "[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()"') do set "CACHE_BUSTER=%%T"
set "APP_URL=http://127.0.0.1:8000/?v=!CACHE_BUSTER!"

echo Opening: !APP_URL!
start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process '!APP_URL!'"
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

endlocal
