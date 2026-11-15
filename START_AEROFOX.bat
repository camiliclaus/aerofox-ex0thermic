@echo off
REM AeroFox local launcher for Windows. Double-click this file.
setlocal
cd /d "%~dp0"
title AeroFox
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\launch.py %*
  goto :end
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\launch.py %*
  goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
  python scripts\launch.py %*
  goto :end
)
echo [AeroFox] ERROR: Python was not found.
echo [AeroFox] Install Python 3.10 or newer from https://www.python.org/downloads/
echo [AeroFox] and tick "Add python.exe to PATH" during installation, then double-click this file again.
:end
echo.
pause
