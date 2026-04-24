from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

from .config import AppConfig


def ensure_runtime_dirs(config: AppConfig) -> None:
    config.runtime_home.mkdir(parents=True, exist_ok=True)
    config.garmindb_config_dir.mkdir(parents=True, exist_ok=True)
    config.healthdata_dir.mkdir(parents=True, exist_ok=True)
    config.obsidian_root_path.mkdir(parents=True, exist_ok=True)
    config.obsidian_daily_path.mkdir(parents=True, exist_ok=True)
    config.obsidian_activity_path.mkdir(parents=True, exist_ok=True)
    config.obsidian_index_path.mkdir(parents=True, exist_ok=True)


def write_garmindb_config(config: AppConfig) -> Path:
    ensure_runtime_dirs(config)
    start_date = _normalize_start_date(config.garmin_initial_start_date)

    payload = {
        "db": {"type": "sqlite"},
        "garmin": {"domain": config.garmin_domain},
        "credentials": {
            "user": config.garmin_username,
            "secure_password": False,
            "password": config.garmin_password,
            "password_file": None,
        },
        "data": {
            "weight_start_date": start_date,
            "sleep_start_date": start_date,
            "rhr_start_date": start_date,
            "monitoring_start_date": start_date,
            "download_latest_activities": config.garmin_download_latest_activities,
            "download_all_activities": config.garmin_download_all_activities,
        },
        "directories": {
            "relative_to_home": False,
            "base_dir": str(config.healthdata_dir),
            "mount_dir": "",
        },
        "enabled_stats": {
            "monitoring": True,
            "steps": True,
            "itime": True,
            "sleep": True,
            "rhr": True,
            "weight": True,
            "activities": True,
        },
        "course_views": {"steps": []},
        "modes": {},
        "activities": {"display": []},
        "settings": {
            "metric": config.garmin_metric,
            "default_display_activities": ["walking", "running", "cycling"],
        },
        "checkup": {"look_back_days": 90},
    }

    with config.garmindb_config_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    return config.garmindb_config_path


def _normalize_start_date(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise ValueError("garmin.initial_start_date must be YYYY-MM-DD or MM/DD/YYYY")


def build_garmindb_command(config: AppConfig, full: bool) -> list[str]:
    base = shlex.split(config.garmin_command, posix=os.name != "nt")
    args = ["--all", "--download", "--import", "--analyze"]
    if not full:
        args.append("--latest")
    return base + args


def run_garmindb_sync(config: AppConfig, full: bool) -> subprocess.CompletedProcess[str]:
    write_garmindb_config(config)
    cmd = build_garmindb_command(config, full=full)

    env = os.environ.copy()
    env["HOME"] = str(config.runtime_home)
    env["USERPROFILE"] = str(config.runtime_home)

    return subprocess.run(
        cmd,
        cwd=config.project_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def find_sqlite_files(config: AppConfig) -> list[Path]:
    if not config.healthdata_dir.exists():
        return []
    return sorted(config.healthdata_dir.rglob("*.db"))
