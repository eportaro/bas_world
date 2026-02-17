@echo off
title BAS World - AI Tractor Head Finder
echo ============================================
echo   BAS World - AI Tractor Head Finder
echo ============================================
echo.

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment...
    python -m venv venv
    echo [*] Installing dependencies...
    call venv\Scripts\pip install -r requirements.txt -q
)

:: Activate venv
call venv\Scripts\activate.bat

:: Check if dependencies are installed
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [*] Installing dependencies...
    pip install -r requirements.txt -q
)

echo.
echo [OK] Starting server...
echo [OK] Open your browser at: http://localhost:8080
echo.
echo Press Ctrl+C to stop the server.
echo ============================================
echo.

uvicorn app.api.main:app --host 0.0.0.0 --port 8080

pause
