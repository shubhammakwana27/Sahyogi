@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start_app.py
) else (
    where py >nul 2>nul
    if errorlevel 1 (
        python start_app.py
    ) else (
        py -3.11 -c "import sys" >nul 2>nul
        if errorlevel 1 (
            py start_app.py
        ) else (
            py -3.11 start_app.py
        )
    )
)
pause
