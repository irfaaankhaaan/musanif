@echo off
REM Double-click this file to start the bot.
REM Leave the window open while you use it. Closing the window stops the bot.

cd /d "%~dp0"

echo Starting the content agent.
echo Leave this window open. Close it, or press Ctrl+C, to stop the bot.
echo.

python app.py
if errorlevel 9009 goto nopython

echo.
echo ============================================================
echo The bot has stopped. Read any message above, then press a key.
echo ============================================================
pause >nul
exit /b

:nopython
echo.
echo I could not find Python on this computer.
echo.
echo Install it from https://python.org/downloads and tick the box that says
echo "Add python.exe to PATH" during setup. Then run this file again.
echo.
pause >nul
