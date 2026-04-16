@echo off
setlocal enabledelayedexpansion

REM Get script directory
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR:~0,-9%

REM Change to project root
cd /d "%PROJECT_ROOT%"

REM Run Python initialization
python "%SCRIPT_DIR%init.py"
if errorlevel 1 (
    echo Startup failed
    exit /b 1
)

echo.
echo Starting Flask application...
echo Access: http://localhost:5000
echo.

python app.py
