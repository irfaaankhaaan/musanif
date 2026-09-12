@echo off
REM ===========================================================================
REM  Double-click this ONCE, the first time you use the bot.
REM
REM  It finds Python, installs everything into a .venv folder that lives right
REM  here (nothing is installed into the rest of your computer), creates your
REM  .env secrets file, and then checks the whole setup.
REM ===========================================================================

cd /d "%~dp0"
title Content Engine - first time setup

echo ============================================================
echo   CONTENT ENGINE - FIRST TIME SETUP
echo ============================================================
echo.
echo This takes two or three minutes. Leave the window open.
echo.


REM --- 1. Find Python ------------------------------------------------------
REM The "py" launcher ships with the official installer and is the reliable
REM one. Plain "python" on Windows can be a Microsoft Store stub that does
REM nothing useful, so it is only the fallback.

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"

if not defined PY (
    echo [X] Python is not installed on this computer.
    echo.
    echo     Get it from https://python.org/downloads
    echo.
    echo     IMPORTANT: on the first screen of the installer, tick the box
    echo     that says "Add python.exe to PATH". It is easy to miss and
    echo     nothing works without it.
    echo.
    echo     Install it, then double-click this file again.
    goto fail
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [X] Your Python is too old. This needs Python 3.10 or newer.
    echo.
    %PY% --version
    echo.
    echo     Get a current one from https://python.org/downloads
    echo     and tick "Add python.exe to PATH" during setup.
    goto fail
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo [1/4] Found %%v


REM --- 2. Build the private package folder ---------------------------------
if exist ".venv\Scripts\python.exe" (
    echo [2/4] Package folder already exists, reusing it.
) else (
    echo [2/4] Making a private package folder ^(.venv^)...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo.
        echo [X] Could not create the .venv folder.
        echo     If this folder is inside OneDrive or Dropbox, try moving the
        echo     whole thing to C:\musanif and running setup again.
        goto fail
    )
)

set "VPY=%~dp0.venv\Scripts\python.exe"


REM --- 3. Install the packages ---------------------------------------------
echo [3/4] Installing the packages it needs. This is the slow part...
echo.
"%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VPY%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo [X] The install failed. The usual cause is no internet connection,
    echo     or a company firewall blocking it. Scroll up for the real error.
    goto fail
)
echo.
echo       Done.


REM --- 4. Secrets -----------------------------------------------------------
echo [4/4] Your secrets file.
echo.
if exist ".env" (
    echo       You already have a .env file, so it has been left alone.
) else (
    copy ".env.example" ".env" >nul
    echo       Created .env from the example.
    echo.
    echo       Notepad is about to open. Replace every "..." with a real key,
    echo       then SAVE ^(Ctrl+S^) and close Notepad to carry on.
    echo.
    pause
    notepad ".env"
)


REM --- Check it all ---------------------------------------------------------
echo.
echo ============================================================
echo   CHECKING EVERYTHING
echo ============================================================
echo.
"%VPY%" -u checkup.py

echo.
echo ============================================================
echo   Setup finished.
echo.
echo   Anything marked [X] above needs fixing before the bot will
echo   run. Use edit-secrets.bat to correct a key, then double-
echo   click check-setup.bat to test again.
echo.
echo   When it is all clear, start the bot with run-bot.bat
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   Setup did not finish. Read the message above.
echo ============================================================
echo.
pause
exit /b 1
