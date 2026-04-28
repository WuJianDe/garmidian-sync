@echo off
setlocal
cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "FRONTEND_URL=http://127.0.0.1:5173/"
set "API_URL=http://127.0.0.1:8765/"

echo.
echo Garmin Obsidian Sync - development launcher
echo =============================================
echo Project: %PROJECT_ROOT%
echo.

where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Please install Node.js first.
  echo.
  pause
  exit /b 1
)

if not exist "config.local.json" (
  echo config.local.json was not found.
  echo Create it first:
  echo   Copy-Item config.example.json config.local.json
  echo.
  pause
  exit /b 1
)

if not exist "frontend\node_modules\vite" (
  echo Frontend dependencies were not found.
  echo Install them first:
  echo   cd frontend
  echo   npm install
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment was not found at .venv\Scripts\python.exe.
  echo The API launcher will try to use python from PATH.
  echo.
)

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)

echo Checking config...
"%PYTHON_EXE%" -m src.garmin_obsidian_sync.cli --config config.local.json doctor
if errorlevel 1 (
  echo.
  echo Config check failed. Fix the message above, then run this launcher again.
  echo.
  pause
  exit /b 1
)
echo.

if /I "%~1"=="--check" (
  echo Launcher checks passed.
  exit /b 0
)

echo Starting API:      %API_URL%
start "Garmidian API" /D "%PROJECT_ROOT%" cmd /k "npm run dev:api"

echo Starting frontend: %FRONTEND_URL%
start "Garmidian Frontend" /D "%PROJECT_ROOT%" cmd /k "npm run dev:frontend"

echo.
echo Two server windows were opened.
echo Close those windows, or press Ctrl+C inside them, to stop the servers.
echo Opening browser in a few seconds...
timeout /t 4 /nobreak >nul
start "" "%FRONTEND_URL%"

exit /b 0
