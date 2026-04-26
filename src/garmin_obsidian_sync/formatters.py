from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .translations import translate_value


def format_distance(value: Any) -> str:
    try:
        meters = float(value)
    except (TypeError, ValueError):
        return translate_value(value)
    return f"{meters / 1000:.2f} 公里"


def format_number(value: Any) -> str:
    if value in (None, "", "null"):
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def format_ratio(value: Any, goal: Any) -> str:
    try:
        current = float(value)
        target = float(goal)
    except (TypeError, ValueError):
        return ""
    if target <= 0:
        return ""
    return f"{(current / target) * 100:.0f}%"


def format_seconds(value: Any) -> str:
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return translate_value(value)
    if seconds <= 0:
        return "0 分 0 秒"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} 小時 {minutes} 分 {secs} 秒"
    return f"{minutes} 分 {secs} 秒"


def format_milliseconds(value: Any) -> str:
    try:
        milliseconds = float(value)
    except (TypeError, ValueError):
        return translate_value(value)
    return format_seconds(milliseconds / 1000)


def format_calories(value: Any) -> str:
    text = translate_value(value)
    return f"{text} 大卡" if text else ""


def format_ml(value: Any) -> str:
    text = translate_value(value)
    return f"{text} ml" if text else ""


def format_pace(distance_m: Any, duration_s: Any) -> str:
    try:
        meters = float(distance_m)
        seconds = float(duration_s)
    except (TypeError, ValueError):
        return ""
    if meters <= 0 or seconds <= 0:
        return ""
    pace_per_km = seconds / (meters / 1000)
    minutes = int(pace_per_km // 60)
    secs = int(round(pace_per_km % 60))
    if secs == 60:
        minutes += 1
        secs = 0
    return f"{minutes}:{secs:02d} /公里"


def timestamp_to_local_text(value: Any) -> str:
    try:
        timestamp = int(float(value))
    except (TypeError, ValueError):
        return format_datetime_text(value)
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def format_datetime_text(value: Any) -> str:
    if value in (None, "", "null"):
        return ""
    if isinstance(value, (int, float)):
        return timestamp_to_local_text(value)
    text = str(value).replace("T", " ")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def translate_bool(value: Any) -> str:
    return "是" if value is True else "否" if value is False else translate_value(value)


def activity_end_time_local(payload: dict[str, Any]) -> str:
    end_local = format_datetime_text(payload.get("endTimeLocal"))
    if end_local:
        return end_local
    start_local = str(payload.get("startTimeLocal") or "")
    if start_local:
        try:
            start_dt = datetime.strptime(start_local, "%Y-%m-%d %H:%M:%S")
            duration_seconds = float(payload.get("elapsedDuration") or payload.get("duration") or 0)
            if duration_seconds > 0:
                return (start_dt + timedelta(seconds=duration_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return format_datetime_text(payload.get("endTimeGMT"))
