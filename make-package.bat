@echo off
REM Double-click this to build the zip file you send to the next person.
REM Your keys and your saved sessions are left out of it.

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo Building the handover zip.
echo.

"%PY%" package.py
if errorlevel 9009 goto nosetup

echo.
echo ============================================================
echo Press any key to close.
echo ============================================================
pause >nul
exit /b

:nosetup
echo.
echo I could not find Python on this computer.
echo Double-click setup.bat first.
echo.
pause >nul
