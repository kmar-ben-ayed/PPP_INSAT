@echo off
setlocal

set "PYTHON=%~dp0venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Virtual environment python not found at "%PYTHON%".
    exit /b 1
)

"%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000
