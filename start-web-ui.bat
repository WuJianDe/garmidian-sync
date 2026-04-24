@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m src.garmin_obsidian_sync.webapp --config config.local.json
) else (
  python -m src.garmin_obsidian_sync.webapp --config config.local.json
)
