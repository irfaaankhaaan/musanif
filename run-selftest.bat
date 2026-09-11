@echo off
REM Double-click this file to run the offline checks.
REM The window stays open at the end so you can actually read the result.

cd /d "%~dp0"

echo Running the offline checks. Nothing connects, nothing is spent.
echo.

python selftest.py
if errorlevel 9009 goto nopython

echo.
echo ============================================================
echo Finished. Read the result above, then press any key to close.
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
