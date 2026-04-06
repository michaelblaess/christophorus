@echo off
set VENV_PYTHON=%~dp0.venv\Scripts\python.exe
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -m fahrtenbuch_app %*
) else (
    python -m fahrtenbuch_app %*
)
