@echo off
REM stop_all.bat — stop only this package's owned UI01 bridge process.
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

if defined SKATE_UI01_PYTHON (
  set "PYTHON=%SKATE_UI01_PYTHON%"
) else if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: No Python available to run stop helper.
    exit /b 2
  )
  set "PYTHON=python"
)

"%PYTHON%" "%ROOT%\scripts\local_lifecycle.py" stop %*
exit /b %ERRORLEVEL%
