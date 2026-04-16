@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo   Inventory Manager - Windows Setup
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python is not installed or not in PATH
    pause
    exit /b 1
)

echo [OK] Python found

REM Create virtual environment
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
)
echo [OK] Virtual environment ready

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
pip install --upgrade pip -q

REM Install dependencies
echo [*] Installing Python dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [!] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM Initialize
echo [*] Running startup...
python startup\init.py
if errorlevel 1 (
    echo [!] Startup failed
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Setup Complete
echo ==========================================
echo Default Login:
echo   Username: admin
echo   Password: admin123
echo.
echo To start: python app.py
echo Access: http://localhost:5000
echo.
pause
