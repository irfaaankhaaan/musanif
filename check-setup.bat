@echo off
REM Double-click this whenever something is not working.
REM It checks every part of the setup and tells you what to fix, then waits
REM so you can read it.

cd /d "%~dp0"

REM Prefer the packages setup.bat installed into .venv. Fall back to whatever
REM Python is on the machine, for anyone who installed them the manual way.
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -u checkup.py
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
echo.
echo Double-click setup.bat first. It installs everything for you.
echo.
pause >nul
