@echo off
setlocal enabledelayedexpansion
color 0A
cls

echo.
echo ===== Inventory Manager - Windows Setup =====
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python not installed or not in PATH
    echo Install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Python found

REM Create venv
if not exist venv (
    python -m venv venv
    if errorlevel 1 (
        color 0C
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)
echo [OK] Virtual environment ready

REM Install dependencies
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 (
    pip install -q -r requirements-minimal.txt
)
echo [OK] Dependencies installed

REM Create .env if needed
if not exist .env (
    copy .env.example .env >nul 2>&1
)

REM Ask for demo mode
echo.
set /p demo_choice="Set as Demo Mode? (Y/N): "
if /i "!demo_choice!"=="Y" (
    setx DEMO_MODE true
    set DEMO_MODE=true
    echo [OK] Demo mode enabled
) else (
    setx DEMO_MODE false
    set DEMO_MODE=false
    echo [OK] Demo mode disabled
)

REM Database check and init
if exist instance\inventory.db (
    echo [OK] Database exists, skipping init
    goto :startup
)

echo [OK] First-time setup - initializing database...

python init_db.py

if errorlevel 1 (
    color 0C
    echo.
    echo [ERROR] Database initialization failed
    echo.
    set /p choice="Delete database and retry? (1=Yes, 2=Exit): "
    
    if "!choice!"=="1" (
        del /f instance\inventory.db >nul 2>&1
        echo Database deleted. Run setup again.
        pause
        exit /b 0
    )
    pause
    exit /b 1
)

:startup
color 0A
echo.
echo ===== Setup Complete! =====
echo.
if "!DEMO_MODE!"=="true" (
    echo DEMO MODE: Enabled
    echo Demo credentials will be shown on login page
    echo Admin profile is locked for editing
) else (
    echo DEMO MODE: Disabled
)
echo.
echo Default Login:
echo   Username: admin
echo   Password: admin123
echo.
echo Starting application...
echo Open browser: http://localhost:5000
echo.

call venv\Scripts\activate.bat
python app.py
pause
