from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .garmin_connect_sync import ensure_runtime_dirs


def export_obsidian_notes(config: AppConfig) -> dict[str, int]:
    ensure_runtime_dirs(config)
    daily_files = sorted(config.raw_daily_dir.glob("*.json"))
    activity_files = sorted(config.raw_activity_dir.rglob("*.json"))
    if not daily_files and not activity_files:
        raise FileNotFoundError(f"No Garmin JSON snapshot files found under {config.healthdata_dir}")

    daily_count = _export_daily_notes(config, daily_files)
    activity_count = _export_activity_notes(config, activity_files)
    _write_schema_note(config, daily_files)
    return {"daily_notes": daily_count, "activity_notes": activity_count}


def _export_daily_notes(config: AppConfig, daily_files: list[Path]) -> int:
    written = 0
    daily_links: list[str] = []

    for daily_file in sorted(daily_files, reverse=True):
        payload = _read_json(daily_file)
        day = str(payload.get("date", daily_file.stem))
        dt = datetime.strptime(day, "%Y-%m-%d")
        note_dir = config.obsidian_daily_path / dt.strftime("%Y") / dt.strftime("%m")
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / f"{day}.md"

        sections: list[str] = []
        for section_name in (
            "stats",
            "sleep",
            "body_battery",
            "hrv",
            "training_readiness",
            "stress",
            "heart_rates",
            "daily_steps",
            "hydration",
        ):
            block = payload.get(section_name)
            if not isinstance(block, dict):
                continue
            sections.append(_render_section(section_name, block))

        if not sections:
            sections.append("## Raw Data\n\n- No structured daily sections found.")

        frontmatter = _render_frontmatter({"type": "garmin-daily", "date": day})
        body = "\n\n".join(
            [
                frontmatter,
                f"# Garmin Daily Summary - {day}",
                _render_daily_summary(payload),
                *sections,
            ]
        )
        note_path.write_text(body + "\n", encoding="utf-8")
        rel = note_path.relative_to(config.obsidian_vault_path).as_posix()
        daily_links.append(f"- [[{rel[:-3]}|{day}]]")
        written += 1

    index_body = "\n".join(["# Garmin Daily Index", "", f"Total notes: {written}", "", *daily_links])
    (config.obsidian_index_path / "Daily Index.md").write_text(index_body + "\n", encoding="utf-8")
    return written


def _export_activity_notes(config: AppConfig, activity_files: list[Path]) -> int:
    written = 0
    activity_links: list[str] = []
    for activity_file in sorted(activity_files, reverse=True)[: config.activity_limit]:
        payload = _read_json(activity_file)
        activity_id = str(payload.get("activityId") or activity_file.stem)
        activity_type = str(payload.get("activityType", {}).get("typeKey") or payload.get("activityName") or "activity")
        raw_time = str(payload.get("startTimeLocal") or payload.get("startTimeGMT") or "unknown")
        activity_date = raw_time[:10] if len(raw_time) >= 10 else "unknown-date"
        year = activity_date[:4] if len(activity_date) >= 4 else "unknown"
        slug_type = activity_type.lower().replace(" ", "-")
        note_dir = config.obsidian_activity_path / year
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / f"{activity_date}-{slug_type}-{activity_id}.md"

        frontmatter = _render_frontmatter(
            {
                "type": "garmin-activity",
                "activity_id": activity_id,
                "activity_type": activity_type,
                "activity_time": raw_time,
            }
        )
        body = "\n\n".join(
            [
                frontmatter,
                f"# Garmin Activity - {activity_type}",
                _render_activity_summary(payload),
                "## Raw Data",
                _render_key_values(payload),
            ]
        )
        note_path.write_text(body + "\n", encoding="utf-8")
        rel = note_path.relative_to(config.obsidian_vault_path).as_posix()
        activity_links.append(f"- [[{rel[:-3]}|{activity_date} {activity_type} #{activity_id}]]")
        written += 1

    index_body = "\n".join(["# Garmin Activity Index", "", f"Total notes: {written}", "", *activity_links])
    (config.obsidian_index_path / "Activity Index.md").write_text(index_body + "\n", encoding="utf-8")
    return written


def _render_section(name: str, payload: dict[str, Any]) -> str:
    pretty_name = name.replace("_", " ").title()
    if payload.get("ok") is False:
        return f"## {pretty_name}\n\n- Error: {payload.get('error', 'unknown error')}"
    data = payload.get("data")
    if isinstance(data, dict):
        return f"## {pretty_name}\n\n{_render_key_values(data)}"
    if isinstance(data, list):
        items = "\n".join(f"- {json.dumps(item, ensure_ascii=False)}" for item in data[:50])
        return f"## {pretty_name}\n\n{items or '- No data'}"
    return f"## {pretty_name}\n\n- {_stringify(data) or 'No data'}"


def _render_daily_summary(payload: dict[str, Any]) -> str:
    metrics: list[str] = []
    stats_data = _extract_data(payload.get("stats"))
    sleep_data = _extract_data(payload.get("sleep"))
    readiness_data = _extract_data(payload.get("training_readiness"))
    body_battery = _extract_data(payload.get("body_battery"))

    _append_if_found(metrics, stats_data, ("steps", "totalSteps"), "Steps")
    _append_if_found(metrics, stats_data, ("floorClimbed",), "Floors")
    _append_if_found(metrics, sleep_data, ("overallSleepScore", "sleepScores", "overall"), "Sleep Score")
    _append_if_found(metrics, readiness_data, ("score", "trainingReadinessScore"), "Training Readiness")
    _append_if_found(metrics, body_battery, ("chargedValue", "bodyBatteryMostRecentValue"), "Body Battery")

    if not metrics:
        return "Daily metrics are available in the sections below."
    return "\n".join(f"- **{label}**: {value}" for label, value in metrics)


def _render_activity_summary(payload: dict[str, Any]) -> str:
    metrics: list[tuple[str, str]] = []
    for label, keys in (
        ("Distance", ("distance",)),
        ("Duration", ("duration", "movingDuration")),
        ("Calories", ("calories",)),
        ("Average HR", ("averageHR",)),
        ("Max HR", ("maxHR",)),
    ):
        value = _find_nested_value(payload, keys)
        if value not in (None, ""):
            metrics.append((label, _stringify(value)))
    if not metrics:
        return "- Activity details are listed below."
    return "\n".join(f"- **{label}**: {value}" for label, value in metrics)


def _append_if_found(metrics: list[tuple[str, str]], data: Any, keys: tuple[str, ...], label: str) -> None:
    value = _find_nested_value(data, keys)
    if value not in (None, ""):
        metrics.append((label, _stringify(value)))


def _extract_data(block: Any) -> Any:
    if isinstance(block, dict):
        return block.get("data")
    return None


def _find_nested_value(data: Any, keys: tuple[str, ...]) -> Any:
    if data is None:
        return None
    if isinstance(data, dict):
        for key in keys:
            if key in data:
                return data[key]
        for value in data.values():
            found = _find_nested_value(value, keys)
            if found not in (None, ""):
                return found
    if isinstance(data, list):
        for item in data:
            found = _find_nested_value(item, keys)
            if found not in (None, ""):
                return found
    return None


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _render_frontmatter(pairs: dict[str, str]) -> str:
    lines = ["---"]
    for key, value in pairs.items():
        escaped = value.replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def _render_key_values(payload: Any, prefix: str = "") -> str:
    lines: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            current = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                lines.append(f"- **{current}**:")
                nested = _render_key_values(value, current)
                if nested:
                    lines.append(nested)
            elif isinstance(value, list):
                lines.append(f"- **{current}**: {json.dumps(value[:20], ensure_ascii=False)}")
            else:
                text = _stringify(value)
                if text != "":
                    lines.append(f"- **{current}**: {text}")
    return "\n".join(lines) if lines else "- No data"


def _write_schema_note(config: AppConfig, daily_files: list[Path]) -> None:
    parts = ["# Garmin Schema Snapshot", ""]
    for daily_file in sorted(daily_files, reverse=True)[:20]:
        payload = _read_json(daily_file)
        parts.append(f"## {daily_file.name}")
        parts.append("")
        for key, value in payload.items():
            parts.append(f"- {key}: {type(value).__name__}")
        parts.append("")
    (config.obsidian_index_path / "Schema Snapshot.md").write_text("\n".join(parts) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
