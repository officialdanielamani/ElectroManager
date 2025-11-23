@echo off
setlocal enabledelayedexpansion
color 0A
cls

echo.
echo ==========================================
echo   Inventory Manager - Windows Setup
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python not installed or not in PATH
    pause
    exit /b 1
)
echo [OK] Python found

REM Create virtual environment
if not exist venv (
    echo [*] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        color 0C
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)
echo [OK] Virtual environment ready

REM Activate and upgrade pip
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1

REM Install dependencies
echo [*] Installing Python dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    color 0C
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Python dependencies installed

REM Initialize offline libraries
echo [*] Downloading JavaScript libraries...
python init_libraries.py
if errorlevel 1 (
    color 0C
    echo [WARNING] JavaScript library download failed - Internet may be required
)
echo [OK] JavaScript libraries ready

REM Create .env from example
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul 2>&1
    )
)

REM Create required directories
if not exist uploads mkdir uploads
if not exist uploads\locations mkdir uploads\locations
if not exist instance mkdir instance
echo [OK] Directories created

REM Database initialization
if exist instance\inventory.db (
    echo [OK] Database exists
    goto :startup
)

echo [*] Initializing database...
python init_db.py
if errorlevel 1 (
    color 0C
    echo [ERROR] Database initialization failed
    pause
    exit /b 1
)
echo [OK] Database initialized

:startup
color 0A
echo.
echo ==========================================
echo   Setup Complete
echo ==========================================
echo.
echo Default Login:
echo   Username: admin
echo   Password: admin123
echo.
echo WARNING: Change password immediately!
echo.
echo Starting application...
echo Open browser: http://localhost:5000
echo.

call venv\Scripts\activate.bat
python app.py
pause
