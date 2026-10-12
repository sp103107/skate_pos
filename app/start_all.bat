@echo off
REM start_all.bat — daily start for UI01 local bridge (frontend + Core API).
setlocal
set "ROOT=%~dp0"
REM strip trailing backslash for clarity in messages
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

if defined SKATE_UI01_PYTHON (
  set "PYTHON=%SKATE_UI01_PYTHON%"
) else if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
) else (
  echo ERROR: No project interpreter. See LOCAL_RUN.md ^(setup^) or set SKATE_UI01_PYTHON.
  exit /b 2
)

"%PYTHON%" "%ROOT%\scripts\local_lifecycle.py" start %*
exit /b %ERRORLEVEL%
