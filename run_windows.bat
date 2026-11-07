@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
    pause
    exit /b
)
where py >nul 2>nul
if %errorlevel% equ 0 (
    py app.py
) else (
    python app.py
)
pause
