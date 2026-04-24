from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


@dataclass(slots=True)
class AppConfig:
    project_root: Path
    config_path: Path
    garmin_username: str
    garmin_password: str
    garmin_domain: str
    garmin_initial_start_date: str
    garmin_metric: bool
    garmin_download_latest_activities: int
    garmin_download_all_activities: int
    garmin_command: str
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
    def garmindb_config_dir(self) -> Path:
        return self.runtime_home / ".GarminDb"

    @property
    def garmindb_config_path(self) -> Path:
        return self.garmindb_config_dir / "GarminConnectConfig.json"

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


def load_config(config_path: str | Path) -> AppConfig:
    resolved = Path(config_path).resolve()
    project_root = resolved.parent
    with resolved.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    garmin = raw.get("garmin", {})
    storage = raw.get("storage", {})
    obsidian = raw.get("obsidian", {})
    export = raw.get("export", {})

    return AppConfig(
        project_root=project_root,
        config_path=resolved,
        garmin_username=str(garmin.get("username", "")),
        garmin_password=str(garmin.get("password", "")),
        garmin_domain=str(garmin.get("domain", "garmin.com")),
        garmin_initial_start_date=str(garmin.get("initial_start_date", "2025-01-01")),
        garmin_metric=bool(garmin.get("metric", True)),
        garmin_download_latest_activities=int(garmin.get("download_latest_activities", 50)),
        garmin_download_all_activities=int(garmin.get("download_all_activities", 1000)),
        garmin_command=str(garmin.get("command", "garmindb_cli.py")),
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
        missing.append("garmin.username")
    if not config.garmin_password:
        missing.append("garmin.password")
    if not config.obsidian_vault_path:
        missing.append("obsidian.vault_path")
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(missing)}")

