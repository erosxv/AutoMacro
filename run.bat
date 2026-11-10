@echo off
rem Abre o AutoMacro. Se o ambiente ainda nao existir, prepara tudo automaticamente.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto :setup
".venv\Scripts\python.exe" -c "import automacro, PySide6, pynput" >nul 2>&1
if errorlevel 1 goto :setup
goto :run

:setup
call setup.bat
if errorlevel 1 (
  pause
  exit /b 1
)

:run
start "" ".venv\Scripts\pythonw.exe" -m automacro %*
