@echo off
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -c "import sys; assert sys.version_info >= (3, 11); import tkinter"
if errorlevel 1 goto failed
py -3 -m venv "%~dp0.venv-assistant"
goto install
:use_python
python -c "import sys; assert sys.version_info >= (3, 11); import tkinter"
if errorlevel 1 goto failed
python -m venv "%~dp0.venv-assistant"
:install
if errorlevel 1 goto failed
"%~dp0.venv-assistant\Scripts\python.exe" -m pip install -r "%~dp0requirements-assistant.txt"
if errorlevel 1 goto failed
echo Dependencies installed on this PC. No panel connection.
pause
exit /b 0
:failed
echo Installation failed. Check Python 3.11 or newer with Tcl/Tk and network access.
pause
exit /b 1
