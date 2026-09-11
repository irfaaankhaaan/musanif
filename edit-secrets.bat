@echo off
REM Double-click this to open your .env secrets file in Notepad.
REM Windows hides files that start with a dot, which is why .env is awkward
REM to open by hand.

cd /d "%~dp0"

if not exist ".env" copy ".env.example" ".env" >nul

echo Opening .env in Notepad.
echo.
echo Paste your real keys in, replacing the ... placeholders.
echo Then SAVE the file (Ctrl+S) and close Notepad.
echo.
notepad ".env"

echo Saved. Now run run-bot.bat.
echo.
pause >nul
