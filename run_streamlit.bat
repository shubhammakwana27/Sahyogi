@echo off
cd /d "%~dp0"
if not exist .venv_streamlit\Scripts\python.exe (
    py -3.11 -m venv .venv_streamlit
    if errorlevel 1 exit /b 1
)
.venv_streamlit\Scripts\python.exe -m pip install -r requirements_streamlit.txt
if errorlevel 1 exit /b 1
.venv_streamlit\Scripts\python.exe manage_users.py setup
if errorlevel 1 exit /b 1
.venv_streamlit\Scripts\python.exe -m streamlit run streamlit_app.py
