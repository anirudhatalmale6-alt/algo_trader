@echo off
title MUKESH ALGO - Starting...
echo ============================================
echo        MUKESH ALGO - Trading Platform
echo ============================================
echo.
echo Starting server... Please wait...
echo.

cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b
)

:: Install requirements silently
echo Installing dependencies...
pip install flask flask-socketio flask-cors loguru >nul 2>&1

:: Open browser after 3 seconds
echo Opening browser in 3 seconds...
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"

:: Start the server
echo.
echo ============================================
echo   Server running at http://127.0.0.1:5000
echo   Browser will open automatically
echo   Press Ctrl+C to stop the server
echo ============================================
echo.
python app.py

pause
