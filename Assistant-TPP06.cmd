@echo off
rem Keep the complete source package together. No administrator rights needed.
if not exist "%~dp0.venv-assistant\Scripts\python.exe" goto system_python
"%~dp0.venv-assistant\Scripts\python.exe" "%~dp0tools\tpp06_assistant.py"
goto finished
:system_python
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 "%~dp0tools\tpp06_assistant.py"
goto finished
:use_python
python "%~dp0tools\tpp06_assistant.py"
:finished
if errorlevel 1 pause
