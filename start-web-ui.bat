@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)

if not exist "frontend\dist\index.html" (
  echo.
  echo Frontend build not found. If this is your first run, build it once:
  echo   cd frontend
  echo   npm install
  echo   npm run build
  echo.
)

"%PYTHON_EXE%" -m src.garmin_obsidian_sync.webapp --config config.local.json
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Startup failed. Check config.local.json, .env, and the Obsidian path.
  pause
)

exit /b %EXIT_CODE%
