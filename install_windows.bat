@echo off
title MUKESH ALGO - Web App Installation
color 0A

echo ============================================
echo   MUKESH ALGO - WEB APP INSTALLATION
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

:: Install web app dependencies
echo Web App dependencies install ho rahi hain... (2-3 minute lag sakte hain)
echo.
pip install flask flask-socketio requests aiohttp pandas numpy sqlalchemy websocket-client python-dateutil cryptography pyyaml loguru

if errorlevel 1 (
    echo.
    echo Kuch dependencies install nahi hui. Internet connection check karo.
    pause
    exit /b 1
)

echo.
echo [OK] Sab dependencies install ho gayi!
echo.

:: Create start script
echo Start script bana raha hoon...

set SCRIPT_DIR=%~dp0

:: Create start_app.bat
echo @echo off > "%SCRIPT_DIR%start_app.bat"
echo title MUKESH ALGO - Web Server >> "%SCRIPT_DIR%start_app.bat"
echo color 0B >> "%SCRIPT_DIR%start_app.bat"
echo echo ============================================ >> "%SCRIPT_DIR%start_app.bat"
echo echo   MUKESH ALGO - Starting Web Server... >> "%SCRIPT_DIR%start_app.bat"
echo echo ============================================ >> "%SCRIPT_DIR%start_app.bat"
echo echo. >> "%SCRIPT_DIR%start_app.bat"
echo echo Browser will open automatically >> "%SCRIPT_DIR%start_app.bat"
echo echo Press Ctrl+C to stop the server >> "%SCRIPT_DIR%start_app.bat"
echo echo ============================================ >> "%SCRIPT_DIR%start_app.bat"
echo echo. >> "%SCRIPT_DIR%start_app.bat"
echo cd /d "%SCRIPT_DIR%" >> "%SCRIPT_DIR%start_app.bat"
echo python web_app\app.py >> "%SCRIPT_DIR%start_app.bat"
echo pause >> "%SCRIPT_DIR%start_app.bat"

:: Create desktop shortcut
echo Desktop shortcut bana raha hoon...

set SHORTCUT_NAME=MUKESH ALGO.lnk
set DESKTOP=%USERPROFILE%\Desktop

echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%DESKTOP%\%SHORTCUT_NAME%" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "%SCRIPT_DIR%start_app.bat" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> CreateShortcut.vbs
echo oLink.Description = "MUKESH ALGO - Web Trading App" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs

cscript //nologo CreateShortcut.vbs
del CreateShortcut.vbs

echo.
echo ============================================
echo   INSTALLATION COMPLETE!
echo ============================================
echo.
echo Desktop pe "MUKESH ALGO" shortcut ban gaya hai.
echo.
echo APP CHALANE KE LIYE:
echo   1. Desktop pe "MUKESH ALGO" pe double-click karo
echo   2. Ya "start_app.bat" pe double-click karo
echo   3. Browser mein http://127.0.0.1:5000 khulega
echo.
echo Koi problem ho toh mujhe message karo.
echo.
pause
