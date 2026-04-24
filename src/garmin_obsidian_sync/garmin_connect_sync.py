from __future__ import annotations

import json
import time
import contextlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .config import AppConfig


@dataclass(slots=True)
class SyncResult:
    daily_files: int
    activity_files: int
    start_date: str
    end_date: str


def ensure_runtime_dirs(config: AppConfig) -> None:
    config.runtime_home.mkdir(parents=True, exist_ok=True)
    config.healthdata_dir.mkdir(parents=True, exist_ok=True)
    config.raw_daily_dir.mkdir(parents=True, exist_ok=True)
    config.raw_activity_dir.mkdir(parents=True, exist_ok=True)
    config.metadata_dir.mkdir(parents=True, exist_ok=True)
    config.obsidian_root_path.mkdir(parents=True, exist_ok=True)
    config.obsidian_daily_path.mkdir(parents=True, exist_ok=True)
    config.obsidian_activity_path.mkdir(parents=True, exist_ok=True)
    config.obsidian_index_path.mkdir(parents=True, exist_ok=True)


def initialize_storage(config: AppConfig) -> None:
    ensure_runtime_dirs(config)
    config.garmin_tokenstore_path.mkdir(parents=True, exist_ok=True)
    if not config.sync_state_path.exists():
        _write_json(
            config.sync_state_path,
            {
                "last_sync_at": None,
                "last_sync_mode": None,
                "last_daily_date": None,
                "last_activity_count": 0,
            },
        )


def run_garmin_sync(config: AppConfig, full: bool) -> SyncResult:
    initialize_storage(config)
    client = _login(config)

    start_day, end_day = _resolve_sync_range(config, full)
    activities = client.get_activities_by_date(
        start_day.isoformat(),
        end_day.isoformat(),
    )
    activity_count = _write_activities(config, activities)

    daily_count = 0
    for day in _iter_days(start_day, end_day):
        payload = _collect_day_payload(client, day)
        _write_json(config.raw_daily_dir / f"{day.isoformat()}.json", payload)
        daily_count += 1

    _write_json(
        config.sync_state_path,
        {
            "last_sync_at": datetime.now().isoformat(timespec="seconds"),
            "last_sync_mode": "full" if full else "latest",
            "last_daily_date": end_day.isoformat(),
            "last_activity_count": activity_count,
            "last_range_start": start_day.isoformat(),
            "last_range_end": end_day.isoformat(),
        },
    )

    return SyncResult(
        daily_files=daily_count,
        activity_files=activity_count,
        start_date=start_day.isoformat(),
        end_date=end_day.isoformat(),
    )


def get_sync_diagnostics(config: AppConfig) -> dict[str, str]:
    state = _read_json(config.sync_state_path) if config.sync_state_path.exists() else {}
    return {
        "config_path": str(config.config_path),
        "credentials_source": config.credentials_source,
        "token_store_path": str(config.garmin_tokenstore_path),
        "token_store_exists": str(config.garmin_tokenstore_path.exists()),
        "healthdata_dir": str(config.healthdata_dir),
        "raw_daily_dir": str(config.raw_daily_dir),
        "raw_activity_dir": str(config.raw_activity_dir),
        "daily_json_count": str(len(list(config.raw_daily_dir.glob("*.json")))) if config.raw_daily_dir.exists() else "0",
        "activity_json_count": str(len(list(config.raw_activity_dir.rglob("*.json")))) if config.raw_activity_dir.exists() else "0",
        "obsidian_root": str(config.obsidian_root_path),
        "obsidian_root_exists": str(config.obsidian_root_path.exists()),
        "last_sync_at": str(state.get("last_sync_at", "")),
        "last_sync_mode": str(state.get("last_sync_mode", "")),
    }


def _login(config: AppConfig) -> Garmin:
    attempts = max(config.garmin_retry_attempts, 1)
    delay_seconds = max(config.garmin_retry_initial_delay_seconds, 1)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            client = Garmin(config.garmin_username, config.garmin_password)
            tokenstore_path = str(config.garmin_tokenstore_path)
            if _tokenstore_ready(config.garmin_tokenstore_path):
                client.login(tokenstore=tokenstore_path)
            else:
                client.login()
                with contextlib.suppress(Exception):
                    client.client.dump(tokenstore_path)
            return client
        except GarminConnectTooManyRequestsError as exc:
            last_error = exc
            if attempt >= attempts:
                break
            wait_seconds = min(delay_seconds, config.garmin_retry_max_delay_seconds)
            print(
                f"[garmin-obsidian-sync] Garmin rate limited the login request. "
                f"Retrying in {wait_seconds} seconds (attempt {attempt + 1}/{attempts})."
            )
            time.sleep(wait_seconds)
            delay_seconds = max(int(delay_seconds * config.garmin_retry_backoff_multiplier), wait_seconds + 1)
        except GarminConnectAuthenticationError:
            raise
        except GarminConnectConnectionError as exc:
            last_error = exc
            if attempt >= attempts:
                break
            wait_seconds = min(delay_seconds, config.garmin_retry_max_delay_seconds)
            print(
                f"[garmin-obsidian-sync] Garmin connection error. "
                f"Retrying in {wait_seconds} seconds (attempt {attempt + 1}/{attempts})."
            )
            time.sleep(wait_seconds)
            delay_seconds = max(int(delay_seconds * config.garmin_retry_backoff_multiplier), wait_seconds + 1)

    assert last_error is not None
    raise last_error


def _tokenstore_ready(path: Path) -> bool:
    return (path / "oauth1_token.json").exists() and (path / "oauth2_token.json").exists()


def _resolve_sync_range(config: AppConfig, full: bool) -> tuple[date, date]:
    end_day = date.today()
    if full:
        return _parse_date(config.garmin_initial_start_date), end_day

    state = _read_json(config.sync_state_path) if config.sync_state_path.exists() else {}
    last_daily_date = state.get("last_daily_date")
    if isinstance(last_daily_date, str) and last_daily_date:
        candidate = _parse_date(last_daily_date) - timedelta(days=1)
        floor = end_day - timedelta(days=config.garmin_latest_lookback_days - 1)
        return max(candidate, floor), end_day
    return end_day - timedelta(days=config.garmin_latest_lookback_days - 1), end_day


def _collect_day_payload(client: Garmin, day: date) -> dict[str, Any]:
    day_text = day.isoformat()
    return {
        "date": day_text,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stats": _safe_call(lambda: client.get_stats(day_text)),
        "heart_rates": _safe_call(lambda: client.get_heart_rates(day_text)),
        "sleep": _safe_call(lambda: client.get_sleep_data(day_text)),
        "stress": _safe_call(lambda: client.get_stress_data(day_text)),
        "body_battery": _safe_call(lambda: client.get_body_battery(day_text)),
        "hrv": _safe_call(lambda: client.get_hrv_data(day_text)),
        "training_readiness": _safe_call(lambda: client.get_training_readiness(day_text)),
        "daily_steps": _safe_call(lambda: client.get_daily_steps(day_text)),
        "hydration": _safe_call(lambda: client.get_hydration_data(day_text)),
    }


def _write_activities(config: AppConfig, activities: list[dict[str, Any]]) -> int:
    count = 0
    for activity in activities:
        activity_id = str(activity.get("activityId") or activity.get("activity_id") or f"activity-{count + 1}")
        start = str(activity.get("startTimeLocal") or activity.get("startTimeGMT") or "")
        year = start[:4] if len(start) >= 4 else "unknown"
        target_dir = config.raw_activity_dir / year
        target_dir.mkdir(parents=True, exist_ok=True)
        _write_json(target_dir / f"{activity_id}.json", activity)
        count += 1
    return count


def _safe_call(fn: Any) -> dict[str, Any]:
    try:
        data = fn()
        return {"ok": True, "data": data}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _iter_days(start_day: date, end_day: date) -> list[date]:
    days: list[date] = []
    cursor = start_day
    while cursor <= end_day:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
