@echo off
set VENV_PYTHON=%~dp0.venv\Scripts\python.exe
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -m death_proof %*
) else (
    python -m death_proof %*
)
