@echo off
echo Starting Algo Trader...
cd /d "%~dp0"
python -m algo_trader.main
pause
