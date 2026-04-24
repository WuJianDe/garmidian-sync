from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
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
    if not base:
        raise ValueError("garmin.command must not be empty")
    command_path = config.garmin_command_path
    if command_path is not None:
        base[0] = str(command_path)
    if base and base[0].lower().endswith(".py"):
        python_cmd = sys.executable
        script_path = Path(base[0])
        if script_path.exists():
            candidate = script_path.with_name("python.exe")
            if candidate.exists():
                python_cmd = str(candidate)
        base = [python_cmd, *base]
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

    attempts = max(config.garmin_retry_attempts, 1)
    delay_seconds = max(config.garmin_retry_initial_delay_seconds, 1)
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    last_result: subprocess.CompletedProcess[str] | None = None

    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run(
                cmd,
                cwd=config.project_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Unable to find GarminDB command: {cmd[0]}. "
                "Update garmin.command in config.local.json or install GarminDB in .venv."
            ) from exc
        last_result = result

        if result.stdout:
            stdout_parts.append(result.stdout.rstrip())
        if result.stderr:
            stderr_parts.append(result.stderr.rstrip())

        if result.returncode == 0 or not _is_rate_limited(result):
            break
        if attempt >= attempts:
            break

        wait_seconds = min(delay_seconds, config.garmin_retry_max_delay_seconds)
        stdout_parts.append(
            f"[garmin-obsidian-sync] Garmin rate limited the login request. "
            f"Retrying in {wait_seconds} seconds (attempt {attempt + 1}/{attempts})."
        )
        time.sleep(wait_seconds)
        delay_seconds = max(int(delay_seconds * config.garmin_retry_backoff_multiplier), wait_seconds + 1)

    assert last_result is not None
    return subprocess.CompletedProcess(
        args=last_result.args,
        returncode=last_result.returncode,
        stdout="\n\n".join(part for part in stdout_parts if part).strip() + ("\n" if stdout_parts else ""),
        stderr="\n\n".join(part for part in stderr_parts if part).strip() + ("\n" if stderr_parts else ""),
    )


def _is_rate_limited(result: subprocess.CompletedProcess[str]) -> bool:
    haystack = "\n".join(filter(None, [result.stdout, result.stderr])).lower()
    return result.returncode != 0 and "429" in haystack and "too many requests" in haystack


def find_sqlite_files(config: AppConfig) -> list[Path]:
    if not config.healthdata_dir.exists():
        return []
    return sorted(config.healthdata_dir.rglob("*.db"))


def get_sync_diagnostics(config: AppConfig) -> dict[str, str]:
    command_path = config.garmin_command_path
    return {
        "config_path": str(config.config_path),
        "credentials_source": config.credentials_source,
        "garmin_command": config.garmin_command,
        "garmin_command_exists": str(command_path.exists()) if command_path is not None else "PATH lookup",
        "healthdata_dir": str(config.healthdata_dir),
        "healthdata_exists": str(config.healthdata_dir.exists()),
        "obsidian_root": str(config.obsidian_root_path),
        "obsidian_root_exists": str(config.obsidian_root_path.exists()),
        "sqlite_db_count": str(len(find_sqlite_files(config))),
    }
