@echo off
title Algo Trader - Installation
color 0A

echo ============================================
echo   ALGO TRADER - INSTALLATION
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python nahi mila! Pehle Python install karo.
    echo.
    echo Python download karo: https://www.python.org/downloads/
    echo.
    echo Installation ke time "Add Python to PATH" checkbox check karna mat bhoolna!
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

echo [OK] Python installed hai
echo.

:: Install dependencies
echo Dependencies install ho rahi hain... (2-3 minute lag sakte hain)
echo.
pip install PyQt6 requests aiohttp pandas numpy sqlalchemy websocket-client python-dateutil cryptography pyyaml loguru matplotlib ta

if errorlevel 1 (
    echo.
    echo Kuch dependencies install nahi hui. Internet connection check karo.
    pause
    exit /b 1
)

echo.
echo [OK] Sab dependencies install ho gayi!
echo.

:: Create desktop shortcut
echo Desktop shortcut bana raha hoon...

set SCRIPT_DIR=%~dp0
set SHORTCUT_NAME=Algo Trader.lnk
set DESKTOP=%USERPROFILE%\Desktop

:: Create VBS script to make shortcut
echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%DESKTOP%\%SHORTCUT_NAME%" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "pythonw" >> CreateShortcut.vbs
echo oLink.Arguments = "-m algo_trader.main" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> CreateShortcut.vbs
echo oLink.Description = "Algo Trader - Pine Script Trading" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs

cscript //nologo CreateShortcut.vbs
del CreateShortcut.vbs

echo.
echo ============================================
echo   INSTALLATION COMPLETE!
echo ============================================
echo.
echo Desktop pe "Algo Trader" shortcut ban gaya hai.
echo Us pe double-click karke app start karo.
echo.
echo Koi problem ho toh mujhe message karo.
echo.
pause
