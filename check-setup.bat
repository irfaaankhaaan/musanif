@echo off
REM Double-click this whenever something is not working.
REM It checks every part of the setup and tells you what to fix, then waits
REM so you can read it.

cd /d "%~dp0"

python -u checkup.py
if errorlevel 9009 goto nopython

echo.
echo ============================================================
echo Press any key to close.
echo ============================================================
pause >nul
exit /b

:nopython
echo.
echo I could not find Python on this computer.
echo Install it from https://python.org/downloads and tick
echo "Add python.exe to PATH" during setup.
echo.
pause >nul
