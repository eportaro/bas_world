@echo off
chcp 65001 >nul 2>&1
title BAS World - AI Tractor Head Finder

echo.
echo  ================================================================
echo  ^|                                                              ^|
echo  ^|   ____    _    ____   __        __         _     _           ^|
echo  ^|  ^| __ )  / \  / ___^|  \ \      / /__  _ __^| ^| __^| ^|          ^|
echo  ^|  ^|  _ \ / _ \ \___ \   \ \ /\ / / _ \^| '__^| ^|/ _` ^|          ^|
echo  ^|  ^| ^|_) / ___ \ ___) ^|   \ V  V / (_) ^| ^|  ^| ^| (_^| ^|          ^|
echo  ^|  ^|____/_/   \_\____/     \_/\_/ \___/^|_^|  ^|_^|\__,_^|          ^|
echo  ^|                                                              ^|
echo  ^|     AI-Powered Tractor Head Finder                           ^|
echo  ^|     Agent Tracing: ENABLED                                   ^|
echo  ^|                                                              ^|
echo  ================================================================
echo.

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Creating virtual environment with Python 3.13...
    py -3.13 -m venv venv
    echo [SETUP] Installing dependencies...
    call venv\Scripts\pip install -r requirements.txt -q
)

:: Activate venv
call venv\Scripts\activate.bat

:: Check if dependencies are installed
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing dependencies...
    pip install -r requirements.txt -q
)

:: Check for .env file
if not exist ".env" (
    echo [WARNING] No .env file found!
    echo [WARNING] Create a .env file with OPENROUTER_API_KEY=your_key
    echo.
)

echo.
echo  [*] Agent tracing logs will appear below
echo  [*] Open browser at: http://localhost:8080
echo  [*] Press Ctrl+C to stop the server
echo.
echo  ================================================================
echo   LOG OUTPUT (watch for tool calls, search results, timing)
echo  ================================================================
echo.

:: Run with ANSI color support, proper encoding, and unbuffered output
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
uvicorn app.api.main:app --host 0.0.0.0 --port 8080

pause
