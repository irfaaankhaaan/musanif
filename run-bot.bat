@echo off
REM Double-click this file to start the bot.
REM Leave the window open while you use it. Closing the window stops the bot.

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo Starting the content agent.
echo Leave this window open. Close it, or press Ctrl+C, to stop the bot.
echo.

"%PY%" app.py
if errorlevel 9009 goto nosetup

echo.
echo ============================================================
echo The bot has stopped. Read any message above, then press a key.
echo ============================================================
pause >nul
exit /b

:nosetup
echo.
echo I could not find Python on this computer.
echo.
echo Double-click setup.bat first. It installs everything for you.
echo.
pause >nul
