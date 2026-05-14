@echo off
python -m venv "%~dp0.venv"

REM SSL-Workaround: pip.ini fuer ALLE pip-Aufrufe (auch Build-Subprocesses)
set PIP_TRUSTED=--trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
if not exist "%~dp0.venv\pip.ini" (
    echo [global]> "%~dp0.venv\pip.ini"
    echo trusted-host = pypi.org pypi.python.org files.pythonhosted.org>> "%~dp0.venv\pip.ini"
)

"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet %PIP_TRUSTED%
"%~dp0.venv\Scripts\pip.exe" install -e "%~dp0." --quiet %PIP_TRUSTED%

REM Git-VCS-Dependencies werden von pip gecached und bei "pip install -e ."
REM nicht automatisch aktualisiert. textual-themes daher explizit frisch
REM ziehen, damit neue Themes (Superman, Batman, ...) ankommen.
"%~dp0.venv\Scripts\pip.exe" install --force-reinstall --no-deps --quiet %PIP_TRUSTED% "git+https://github.com/michaelblaess/textual-themes.git"

echo.
echo Setup abgeschlossen. Starte mit: run.bat
