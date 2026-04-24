from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass(slots=True)
class AppConfig:
    project_root: Path
    config_path: Path
    garmin_username: str
    garmin_password: str
    garmin_username_env: str
    garmin_password_env: str
    garmin_domain: str
    garmin_initial_start_date: str
    garmin_metric: bool
    garmin_download_latest_activities: int
    garmin_download_all_activities: int
    garmin_latest_lookback_days: int
    garmin_retry_attempts: int
    garmin_retry_initial_delay_seconds: int
    garmin_retry_backoff_multiplier: float
    garmin_retry_max_delay_seconds: int
    healthdata_dir: Path
    obsidian_vault_path: Path
    obsidian_root_folder: str
    obsidian_daily_folder: str
    obsidian_activity_folder: str
    daily_limit_per_section: int
    activity_limit: int

    @property
    def runtime_home(self) -> Path:
        return self.project_root / ".runtime" / "home"

    @property
    def garmin_tokenstore_path(self) -> Path:
        return self.runtime_home / "garminconnect_tokens"

    @property
    def raw_daily_dir(self) -> Path:
        return self.healthdata_dir / "raw" / "daily"

    @property
    def raw_activity_dir(self) -> Path:
        return self.healthdata_dir / "raw" / "activities"

    @property
    def metadata_dir(self) -> Path:
        return self.healthdata_dir / "metadata"

    @property
    def sync_state_path(self) -> Path:
        return self.metadata_dir / "sync_state.json"

    @property
    def obsidian_root_path(self) -> Path:
        return self.obsidian_vault_path / Path(self.obsidian_root_folder)

    @property
    def obsidian_daily_path(self) -> Path:
        return self.obsidian_root_path / Path(self.obsidian_daily_folder)

    @property
    def obsidian_activity_path(self) -> Path:
        return self.obsidian_root_path / Path(self.obsidian_activity_folder)

    @property
    def obsidian_index_path(self) -> Path:
        return self.obsidian_root_path / "_Indexes"

    @property
    def credentials_source(self) -> str:
        if not (self.garmin_username and self.garmin_password):
            return "missing"
        return "config file" if self._uses_inline_credentials else ".env or process env"

    @property
    def _uses_inline_credentials(self) -> bool:
        with self.config_path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] = json.load(fh)
        garmin = raw.get("garmin", {})
        return bool(str(garmin.get("username", "")) or str(garmin.get("password", "")))

def load_config(config_path: str | Path) -> AppConfig:
    resolved = Path(config_path).resolve()
    project_root = resolved.parent
    _load_dotenv_file(project_root / ".env")
    with resolved.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    garmin = raw.get("garmin", {})
    storage = raw.get("storage", {})
    obsidian = raw.get("obsidian", {})
    export = raw.get("export", {})
    retry = raw.get("retry", {})

    garmin_username_env = str(garmin.get("username_env", "GARMIN_USERNAME"))
    garmin_password_env = str(garmin.get("password_env", "GARMIN_PASSWORD"))
    garmin_username = str(garmin.get("username", "")) or os.environ.get(garmin_username_env, "")
    garmin_password = str(garmin.get("password", "")) or os.environ.get(garmin_password_env, "")

    return AppConfig(
        project_root=project_root,
        config_path=resolved,
        garmin_username=garmin_username,
        garmin_password=garmin_password,
        garmin_username_env=garmin_username_env,
        garmin_password_env=garmin_password_env,
        garmin_domain=str(garmin.get("domain", "garmin.com")),
        garmin_initial_start_date=str(garmin.get("initial_start_date", "2025-01-01")),
        garmin_metric=bool(garmin.get("metric", True)),
        garmin_download_latest_activities=int(garmin.get("download_latest_activities", 50)),
        garmin_download_all_activities=int(garmin.get("download_all_activities", 1000)),
        garmin_latest_lookback_days=int(garmin.get("latest_lookback_days", 7)),
        garmin_retry_attempts=int(retry.get("attempts", 4)),
        garmin_retry_initial_delay_seconds=int(retry.get("initial_delay_seconds", 60)),
        garmin_retry_backoff_multiplier=float(retry.get("backoff_multiplier", 2.0)),
        garmin_retry_max_delay_seconds=int(retry.get("max_delay_seconds", 900)),
        healthdata_dir=_resolve_path(project_root, str(storage.get("healthdata_dir", "./data/HealthData"))),
        obsidian_vault_path=_resolve_path(project_root, str(obsidian.get("vault_path", "./exports/ObsidianVault"))),
        obsidian_root_folder=str(obsidian.get("root_folder", "Health/Garmin")),
        obsidian_daily_folder=str(obsidian.get("daily_folder", "Daily")),
        obsidian_activity_folder=str(obsidian.get("activity_folder", "Activities")),
        daily_limit_per_section=int(export.get("daily_limit_per_section", 10)),
        activity_limit=int(export.get("activity_limit", 200)),
    )


def validate_config(config: AppConfig) -> None:
    missing = []
    if not config.garmin_username:
        missing.append(f"garmin.username or env:{config.garmin_username_env}")
    if not config.garmin_password:
        missing.append(f"garmin.password or env:{config.garmin_password_env}")
    if not config.obsidian_vault_path:
        missing.append("obsidian.vault_path")
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(missing)}")
    if config.garmin_retry_attempts < 1:
        raise ValueError("retry.attempts must be >= 1")
    if config.garmin_latest_lookback_days < 1:
        raise ValueError("garmin.latest_lookback_days must be >= 1")
    if config.garmin_retry_initial_delay_seconds < 1:
        raise ValueError("retry.initial_delay_seconds must be >= 1")
    if config.garmin_retry_backoff_multiplier < 1:
        raise ValueError("retry.backoff_multiplier must be >= 1")
    if config.garmin_retry_max_delay_seconds < 1:
        raise ValueError("retry.max_delay_seconds must be >= 1")
