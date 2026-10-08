@echo off
rem One-time setup: virtual environment, dependencies, offline renderers.
setlocal
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv || goto :fail
)
call .venv\Scripts\python.exe -m pip install --upgrade pip || goto :fail
call .venv\Scripts\python.exe -m pip install -e ".[gui,dev]" || goto :fail
call .venv\Scripts\python.exe -m md2doc setup || goto :fail
call .venv\Scripts\python.exe -m md2doc doctor
echo.
echo Done. Start the app with md2doc-gui.bat  (or: .venv\Scripts\md2doc.exe notes.md)
exit /b 0
:fail
echo.
echo Setup failed - see the messages above.
exit /b 1
