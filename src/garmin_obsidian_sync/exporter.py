from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import AppConfig
from .garmin_connect_sync import ensure_runtime_dirs

SECTION_TITLES = {
    "stats": "每日總覽",
    "sleep": "睡眠",
    "body_battery": "身體電量",
    "hrv": "HRV",
    "training_readiness": "訓練準備度",
    "stress": "壓力",
    "heart_rates": "心率",
    "daily_steps": "步數明細",
    "hydration": "補水",
}

ACTIVITY_TYPE_LABELS = {
    "running": "跑步",
    "walking": "步行",
    "cycling": "騎車",
    "road_biking": "公路騎車",
    "mountain_biking": "登山車",
    "yoga": "瑜伽",
    "strength_training": "肌力訓練",
    "traditional_strength_training": "重量訓練",
    "cardio_training": "有氧訓練",
    "pilates": "皮拉提斯",
    "swimming": "游泳",
    "treadmill_running": "跑步機",
}

VALUE_TRANSLATIONS = {
    "BALANCED": "平衡",
    "LOW": "偏低",
    "MODERATE": "中等",
    "HIGH": "高",
    "VERY_GOOD": "很好",
    "GOOD": "良好",
    "FAIR": "普通",
    "POOR": "較差",
    "NONE": "無",
    "UNKNOWN": "未知",
    "groups": "群組可見",
    "private": "私人",
    "public": "公開",
    "uncategorized": "未分類",
    "yoga": "瑜伽",
    "running": "跑步",
    "walking": "步行",
    "cycling": "騎車",
    "traditional_strength_training": "重量訓練",
    "strength_training": "肌力訓練",
    "cardio_training": "有氧訓練",
    "SLEEP": "睡眠",
    "NAP": "小睡",
    "RECOVERY": "恢復",
    "GARMIN": "Garmin",
    "RESTFUL_PERIOD": "放鬆時段",
    "SLEEP_PREPARATION_RECOVERING_AND_INACTIVE": "恢復中，適合準備睡眠",
    "SLEEP_TIME_PASSED_STRESSFUL_AND_INACTIVE": "已過睡眠時段，身體偏疲勞",
    "BALANCE_STRESS_AND_RECOVERY": "恢復與壓力大致平衡",
    "WELL_RECOVERED": "恢復良好",
    "AFTER_WAKEUP_RESET": "起床後更新",
    "UPDATE_REALTIME_VARIABLES": "即時狀態更新",
    "NO_CHANGE_SLEEP": "睡眠後恢復時間無明顯變化",
}


def export_obsidian_notes(config: AppConfig) -> dict[str, int]:
    ensure_runtime_dirs(config)
    daily_files = sorted(config.raw_daily_dir.glob("*.json"))
    activity_files = sorted(config.raw_activity_dir.rglob("*.json"))
    if not daily_files and not activity_files:
        raise FileNotFoundError(f"No Garmin JSON snapshot files found under {config.healthdata_dir}")

    daily_count = _export_daily_notes(config, daily_files)
    activity_count = _export_activity_notes(config, activity_files)
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
            if isinstance(block, dict):
                sections.append(_render_section(section_name, block, payload))

        body = "\n\n".join(
            [
                _render_frontmatter({"type": "garmin-daily", "date": day}),
                f"# 每日健康摘要 - {day}",
                _render_daily_summary(payload),
                *sections,
                _render_collapsible_raw_data("原始每日資料", payload),
            ]
        )
        note_path.write_text(body + "\n", encoding="utf-8")
        rel = note_path.relative_to(config.obsidian_vault_path).as_posix()
        daily_links.append(f"- [[{rel[:-3]}|{day}]]")
        written += 1

    index_body = "\n".join(["# 每日健康索引", "", f"總筆記數：{written}", "", *daily_links])
    (config.obsidian_index_path / "Daily Index.md").write_text(index_body + "\n", encoding="utf-8")
    return written


def _export_activity_notes(config: AppConfig, activity_files: list[Path]) -> int:
    written = 0
    activity_links: list[str] = []
    for activity_file in sorted(activity_files, reverse=True)[: config.activity_limit]:
        payload = _read_json(activity_file)
        activity_id = str(payload.get("activityId") or activity_file.stem)
        activity_type = _activity_type_label(payload)
        raw_time = str(payload.get("startTimeLocal") or payload.get("startTimeGMT") or "unknown")
        activity_date = raw_time[:10] if len(raw_time) >= 10 else "unknown-date"
        year = activity_date[:4] if len(activity_date) >= 4 else "unknown"
        filename_label = _safe_filename_part(activity_type)
        note_dir = config.obsidian_activity_path / year
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / f"{activity_date}-{filename_label}-{activity_id}.md"
        _remove_stale_activity_notes(note_dir, activity_id, note_path)

        body = "\n\n".join(
            [
                _render_frontmatter(
                    {
                        "type": "garmin-activity",
                        "activity_id": activity_id,
                        "activity_type": activity_type,
                        "activity_time": raw_time,
                    }
                ),
                f"# 活動紀錄 - {activity_type}",
                _render_activity_summary(payload),
                _render_activity_details(payload),
                _render_collapsible_raw_data("原始活動資料", payload),
            ]
        )
        note_path.write_text(body + "\n", encoding="utf-8")
        rel = note_path.relative_to(config.obsidian_vault_path).as_posix()
        activity_links.append(f"- [[{rel[:-3]}|{activity_date} {activity_type} #{activity_id}]]")
        written += 1

    index_body = "\n".join(["# 活動紀錄索引", "", f"總筆記數：{written}", "", *activity_links])
    (config.obsidian_index_path / "Activity Index.md").write_text(index_body + "\n", encoding="utf-8")
    return written


def _render_section(name: str, payload: dict[str, Any], daily_payload: dict[str, Any] | None = None) -> str:
    title = SECTION_TITLES.get(name, name)
    if payload.get("ok") is False:
        return f"## {title}\n\n- 讀取失敗：{_translate_value(payload.get('error', 'unknown error'))}"
    data = payload.get("data")
    renderer = {
        "stats": _render_stats_section,
        "sleep": _render_sleep_section,
        "body_battery": lambda block: _render_body_battery_section(block, daily_payload),
        "hrv": _render_hrv_section,
        "training_readiness": _render_training_readiness_section,
        "stress": lambda block: _render_stress_section(block, daily_payload),
        "heart_rates": _render_heart_rate_section,
        "daily_steps": lambda block: _render_daily_steps_section(block, daily_payload),
        "hydration": _render_hydration_section,
    }.get(name, _render_generic_section)
    return f"## {title}\n\n{renderer(data)}"


def _render_daily_summary(payload: dict[str, Any]) -> str:
    stats_data = _extract_data(payload.get("stats"))
    sleep_data = _extract_data(payload.get("sleep"))
    readiness_data = _extract_data(payload.get("training_readiness"))
    body_battery = _extract_data(payload.get("body_battery"))
    hrv_data = _extract_data(payload.get("hrv"))
    hydration_data = _extract_data(payload.get("hydration"))

    items = [
        ("步數", _find_nested_value(stats_data, ("totalSteps",))),
        ("距離", _format_distance(_find_nested_value(stats_data, ("totalDistanceMeters",)))),
        ("靜止心率", _find_nested_value(stats_data, ("restingHeartRate",))),
        ("睡眠分數", _find_nested_value(sleep_data, ("dailySleepDTO", "sleepScores", "overall", "value"))),
        ("訓練準備度", _pick_training_readiness(readiness_data, "score")),
        ("目前身體電量", _pick_body_battery(body_battery, "bodyBatteryMostRecentValue") or _find_nested_value(stats_data, ("bodyBatteryMostRecentValue",))),
        ("平均壓力", _find_nested_value(stats_data, ("averageStressLevel",))),
        ("昨晚 HRV", _find_nested_value(hrv_data, ("hrvSummary", "lastNightAvg"))),
        ("今日補水量", _format_ml(_find_nested_value(hydration_data, ("valueInML",)))),
    ]
    return "\n".join(["## 今日摘要", "", _render_label_value_list(items)])


def _render_activity_summary(payload: dict[str, Any]) -> str:
    items = [
        ("活動類型", _activity_type_label(payload)),
        ("開始時間", payload.get("startTimeLocal")),
        ("距離", _format_distance(payload.get("distance"))),
        ("時長", _format_seconds(payload.get("duration") or payload.get("movingDuration"))),
        ("卡路里", _format_calories(payload.get("calories"))),
        ("平均心率", payload.get("averageHR")),
        ("最高心率", payload.get("maxHR")),
        ("平均呼吸率", payload.get("avgRespirationRate")),
        ("壓力變化", payload.get("differenceStress")),
    ]
    return "\n".join(["## 活動摘要", "", _render_label_value_list(items)])


def _render_activity_details(payload: dict[str, Any]) -> str:
    activity_type_key = _stringify(payload.get("activityType", {}).get("typeKey")).lower()
    sections: list[tuple[str, str]] = [
        ("## 主要資訊", _render_label_value_list(_activity_overview_metrics(payload))),
        ("## 訓練與生理指標", _render_label_value_list(_activity_training_metrics(payload))),
        ("## 壓力與恢復", _render_label_value_list(_activity_stress_metrics(payload))),
        ("## 時間與裝置", _render_label_value_list(_activity_context_metrics(payload))),
    ]

    if activity_type_key in {"running", "walking", "cycling", "road_biking", "mountain_biking", "treadmill_running"}:
        sections.insert(2, ("## 配速與移動表現", _render_label_value_list(_activity_endurance_metrics(payload))))
        sections.insert(3, ("## 心率與呼吸", _render_label_value_list(_activity_respiration_metrics(payload))))
    elif activity_type_key in {"yoga", "pilates"}:
        sections.insert(2, ("## 呼吸與放鬆", _render_label_value_list(_activity_respiration_metrics(payload))))
        sections.insert(3, ("## 恢復觀察", _render_label_value_list(_activity_recovery_metrics(payload))))
    elif activity_type_key in {"strength_training", "traditional_strength_training"}:
        sections.insert(2, ("## 組數與訓練摘要", _render_activity_set_metrics(payload)))
        sections.insert(3, ("## 呼吸與恢復", _render_label_value_list(_activity_recovery_metrics(payload))))
    else:
        sections.insert(2, ("## 呼吸與心率區間", _render_label_value_list(_activity_respiration_metrics(payload))))
        sections.insert(3, ("## 組數與附加摘要", _render_activity_set_metrics(payload)))

    parts: list[str] = []
    for title, content in sections:
        parts.extend([title, "", content, ""])
    return "\n".join(parts).strip()


def _activity_overview_metrics(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("活動名稱", payload.get("activityName")),
        ("活動類型", _activity_type_label(payload)),
        ("開始時間", payload.get("startTimeLocal")),
        ("結束時間", _activity_end_time_local(payload)),
        ("卡路里", _format_calories(payload.get("calories"))),
        ("平均心率", payload.get("averageHR")),
        ("最高心率", payload.get("maxHR")),
        ("訓練負荷", payload.get("activityTrainingLoad")),
        ("中等強度分鐘", payload.get("moderateIntensityMinutes")),
        ("高強度分鐘", payload.get("vigorousIntensityMinutes")),
        ("身體電量變化", payload.get("differenceBodyBattery")),
        ("壓力變化", payload.get("differenceStress")),
    ]


def _activity_training_metrics(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("訓練效果（有氧）", payload.get("aerobicTrainingEffect")),
        ("訓練效果（無氧）", payload.get("anaerobicTrainingEffect")),
        ("訓練效果標籤", _translate_value(payload.get("trainingEffectLabel"))),
        ("有氧訓練說明", _translate_value(payload.get("aerobicTrainingEffectMessage"))),
        ("無氧訓練說明", _translate_value(payload.get("anaerobicTrainingEffectMessage"))),
        ("總組數", payload.get("totalSets")),
        ("有效組數", payload.get("activeSets")),
        ("總次數", payload.get("totalReps")),
        ("總步數", payload.get("steps")),
        ("耗水估計", _format_ml(payload.get("waterEstimated"))),
    ]


def _activity_stress_metrics(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("平均壓力", payload.get("avgStress")),
        ("開始壓力", payload.get("startStress")),
        ("結束壓力", payload.get("endStress")),
        ("最大壓力", payload.get("maxStress")),
        ("壓力變化", payload.get("differenceStress")),
        ("身體電量變化", payload.get("differenceBodyBattery")),
    ]


def _activity_respiration_metrics(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("平均呼吸率", payload.get("avgRespirationRate")),
        ("最低呼吸率", payload.get("minRespirationRate")),
        ("最高呼吸率", payload.get("maxRespirationRate")),
        ("心率區間 1", _format_seconds(payload.get("hrTimeInZone_1"))),
        ("心率區間 2", _format_seconds(payload.get("hrTimeInZone_2"))),
        ("心率區間 3", _format_seconds(payload.get("hrTimeInZone_3"))),
        ("心率區間 4", _format_seconds(payload.get("hrTimeInZone_4"))),
        ("心率區間 5", _format_seconds(payload.get("hrTimeInZone_5"))),
    ]


def _activity_endurance_metrics(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    distance_m = payload.get("distance")
    duration_s = payload.get("duration") or payload.get("movingDuration")
    return [
        ("距離", _format_distance(distance_m)),
        ("活動時長", _format_seconds(duration_s)),
        ("平均配速", _format_pace(distance_m, duration_s)),
        ("移動時長", _format_seconds(payload.get("movingDuration"))),
        ("總爬升樓層", payload.get("floorsAscended")),
        ("總下降樓層", payload.get("floorsDescended")),
        ("圈數", payload.get("lapCount")),
    ]


def _activity_recovery_metrics(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("平均心率", payload.get("averageHR")),
        ("最高心率", payload.get("maxHR")),
        ("平均呼吸率", payload.get("avgRespirationRate")),
        ("身體電量變化", payload.get("differenceBodyBattery")),
        ("平均壓力", payload.get("avgStress")),
        ("結束壓力", payload.get("endStress")),
    ]


def _activity_context_metrics(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("活動 ID", payload.get("activityId")),
        ("活動 UUID", payload.get("activityUUID")),
        ("事件類型", _translate_value(payload.get("eventType", {}).get("typeKey"))),
        ("裝置 ID", payload.get("deviceId")),
        ("裝置製造商", _translate_value(payload.get("manufacturer"))),
        ("建立者", payload.get("ownerFullName")),
        ("隱私設定", _translate_value(payload.get("privacy", {}).get("typeKey"))),
        ("手動活動", _translate_bool(payload.get("manualActivity"))),
        ("最愛活動", _translate_bool(payload.get("favorite"))),
        ("是否 PR", _translate_bool(payload.get("pr"))),
    ]


def _render_activity_set_metrics(payload: dict[str, Any]) -> str:
    sets = payload.get("summarizedExerciseSets")
    if not isinstance(sets, list) or not sets:
        return "- 沒有組數摘要。"
    lines: list[str] = []
    for index, item in enumerate(sets, start=1):
        lines.append(f"### 第 {index} 組")
        lines.append("")
        lines.append(
            _render_label_value_list(
                [
                    ("分類", _translate_value(item.get("category"))),
                    ("組數", item.get("sets")),
                    ("次數", item.get("reps")),
                    ("持續時間", _format_milliseconds(item.get("duration"))),
                    ("總量", item.get("volume")),
                    ("最大重量", item.get("maxWeight")),
                ]
            )
        )
        lines.append("")
    return "\n".join(lines).strip()


def _render_stats_section(data: Any) -> str:
    if not isinstance(data, dict):
        return "- 沒有資料。"
    return _render_label_value_list(
        [
            ("總步數", data.get("totalSteps")),
            ("步數目標", data.get("dailyStepGoal")),
            ("步數達成率", _format_ratio(data.get("totalSteps"), data.get("dailyStepGoal"))),
            ("總距離", _format_distance(data.get("totalDistanceMeters"))),
            ("活動熱量", _format_calories(data.get("activeKilocalories"))),
            ("總消耗熱量", _format_calories(data.get("totalKilocalories"))),
            ("剩餘熱量", _format_calories(data.get("remainingKilocalories"))),
            ("靜止心率", data.get("restingHeartRate")),
            ("最低心率", data.get("minHeartRate")),
            ("最高心率", data.get("maxHeartRate")),
            ("平均壓力", data.get("averageStressLevel")),
            ("最高壓力", data.get("maxStressLevel")),
            ("壓力狀態", _translate_value(data.get("stressQualifier"))),
            ("中等強度分鐘", data.get("moderateIntensityMinutes")),
            ("高強度分鐘", data.get("vigorousIntensityMinutes")),
            ("上樓層數", _format_number(data.get("floorsAscended"))),
            ("下樓層數", _format_number(data.get("floorsDescended"))),
            ("平均血氧", _format_number(data.get("averageSpo2"))),
            ("目前血氧", data.get("latestSpo2")),
        ]
    )


def _render_sleep_section(data: Any) -> str:
    if not isinstance(data, dict):
        return "- 沒有資料。"
    daily_sleep = data.get("dailySleepDTO", {})
    spo2 = data.get("wellnessSpO2SleepSummaryDTO", {})
    return _render_label_value_list(
        [
            ("睡眠開始", _timestamp_to_local_text(daily_sleep.get("sleepStartTimestampLocal"))),
            ("睡眠結束", _timestamp_to_local_text(daily_sleep.get("sleepEndTimestampLocal"))),
            ("總睡眠時間", _format_seconds(daily_sleep.get("sleepTimeSeconds"))),
            ("小睡時間", _format_seconds(daily_sleep.get("napTimeSeconds"))),
            ("睡眠分數", _find_nested_value(daily_sleep, ("sleepScores", "overall", "value"))),
            ("清醒時間", _format_seconds(daily_sleep.get("awakeSleepSeconds"))),
            ("深層睡眠", _format_seconds(daily_sleep.get("deepSleepSeconds"))),
            ("淺眠", _format_seconds(daily_sleep.get("lightSleepSeconds"))),
            ("快速動眼期", _format_seconds(daily_sleep.get("remSleepSeconds"))),
            ("睡眠平均血氧", _format_number(spo2.get("averageSPO2") or daily_sleep.get("averageSpO2Value"))),
            ("睡眠最低血氧", _format_number(spo2.get("lowestSPO2") or daily_sleep.get("lowestSpO2Value"))),
            ("睡眠平均呼吸率", _format_number(daily_sleep.get("averageRespirationValue"))),
            ("睡眠最低呼吸率", _format_number(daily_sleep.get("lowestRespirationValue"))),
            ("睡眠最高呼吸率", _format_number(daily_sleep.get("highestRespirationValue"))),
            ("昨夜 HRV", _format_number(data.get("avgOvernightHrv"))),
            ("睡眠中身體電量變化", _format_number(data.get("bodyBatteryChange"))),
        ]
    )


def _render_body_battery_section(data: Any, daily_payload: dict[str, Any] | None = None) -> str:
    latest = data[-1] if isinstance(data, list) and data else {}
    if not isinstance(latest, dict):
        return "- 沒有資料。"
    stats_data = _extract_data((daily_payload or {}).get("stats"))
    values = latest.get("bodyBatteryValuesArray")
    current_value = _find_nested_value(stats_data, ("bodyBatteryMostRecentValue",)) or latest.get("endValue") or _pick_series_value(values, last=True)
    lowest_value = _series_min(values, positive_only=True) or _find_nested_value(stats_data, ("bodyBatteryLowestValue",))
    highest_value = _series_max(values) or _find_nested_value(stats_data, ("bodyBatteryHighestValue",))
    feedback = latest.get("bodyBatteryDynamicFeedbackEvent", {})
    end_feedback = latest.get("endOfDayBodyBatteryDynamicFeedbackEvent", {})
    events = latest.get("bodyBatteryActivityEvent")
    event_summary = _summarize_body_battery_events(events)
    return _render_label_value_list(
        [
            ("目前身體電量", current_value),
            ("今日最高", highest_value),
            ("今日最低", lowest_value),
            ("睡眠回充", latest.get("charged") or _find_nested_value(stats_data, ("bodyBatteryChargedValue",))),
            ("今日消耗", latest.get("drained") or _find_nested_value(stats_data, ("bodyBatteryDrainedValue",))),
            ("起床時電量", _find_nested_value(stats_data, ("bodyBatteryAtWakeTime",))),
            ("資料開始", _format_datetime_text(latest.get("startTimestampLocal"))),
            ("資料結束", _format_datetime_text(latest.get("endTimestampLocal"))),
            ("目前狀態", _translate_value(feedback.get("bodyBatteryLevel"))),
            ("近期提醒", _translate_value(feedback.get("feedbackShortType"))),
            ("日末提醒", _translate_value(end_feedback.get("feedbackShortType"))),
            ("主要事件", event_summary),
        ]
    )


def _render_hrv_section(data: Any) -> str:
    if not isinstance(data, dict):
        return "- 沒有資料。"
    summary = data.get("hrvSummary", {})
    baseline = summary.get("baseline", {})
    return _render_label_value_list(
        [
            ("昨晚平均 HRV", summary.get("lastNightAvg")),
            ("近一週平均 HRV", summary.get("weeklyAvg")),
            ("狀態", _translate_value(summary.get("status"))),
            ("平衡區間下緣", baseline.get("balancedLow")),
            ("平衡區間上緣", baseline.get("balancedUpper")),
            ("偏低警戒", baseline.get("lowUpper")),
        ]
    )


def _render_training_readiness_section(data: Any) -> str:
    latest = data[0] if isinstance(data, list) and data else {}
    if not isinstance(latest, dict):
        return "- 沒有資料。"
    return _render_label_value_list(
        [
            ("訓練準備度", latest.get("score")),
            ("等級", _translate_value(latest.get("level"))),
            ("狀態摘要", _translate_value(latest.get("feedbackShort"))),
            ("睡眠分數", latest.get("sleepScore")),
            ("恢復時間", f"{_stringify(latest.get('recoveryTime'))} 小時" if latest.get("recoveryTime") is not None else None),
            ("急性負荷", latest.get("acuteLoad")),
            ("HRV 因子", _translate_value(latest.get("hrvFactorFeedback"))),
            ("壓力因子", _translate_value(latest.get("stressHistoryFactorFeedback"))),
            ("睡眠歷史因子", _translate_value(latest.get("sleepHistoryFactorFeedback"))),
            ("更新時間", _format_datetime_text(latest.get("timestampLocal"))),
            ("更新情境", _translate_value(latest.get("inputContext"))),
        ]
    )


def _render_stress_section(data: Any, daily_payload: dict[str, Any] | None = None) -> str:
    if not isinstance(data, dict):
        return "- 沒有資料。"
    stats_data = _extract_data((daily_payload or {}).get("stats"))
    series = data.get("stressValuesArray")
    return _render_label_value_list(
        [
            ("平均壓力", data.get("avgStressLevel") or _find_nested_value(stats_data, ("averageStressLevel",))),
            ("最高壓力", data.get("maxStressLevel") or _find_nested_value(stats_data, ("maxStressLevel",))),
            ("最新壓力", _pick_series_value(series, last=True)),
            ("資料開始", _format_datetime_text(data.get("startTimestampLocal"))),
            ("資料結束", _format_datetime_text(data.get("endTimestampLocal"))),
            ("休息時長", _format_seconds(_find_nested_value(stats_data, ("restStressDuration",)))),
            ("低壓力時長", _format_seconds(_find_nested_value(stats_data, ("lowStressDuration",)))),
            ("中壓力時長", _format_seconds(_find_nested_value(stats_data, ("mediumStressDuration",)))),
            ("高壓力時長", _format_seconds(_find_nested_value(stats_data, ("highStressDuration",)))),
            ("未分類時長", _format_seconds(_find_nested_value(stats_data, ("uncategorizedStressDuration",)))),
        ]
    )


def _render_heart_rate_section(data: Any) -> str:
    if not isinstance(data, dict):
        return "- 沒有資料。"
    return _render_label_value_list(
        [
            ("最低心率", data.get("minHeartRate")),
            ("最高心率", data.get("maxHeartRate")),
            ("靜止心率", data.get("restingHeartRate")),
            ("近七天平均靜止心率", data.get("lastSevenDaysAvgRestingHeartRate")),
        ]
    )


def _render_daily_steps_section(data: Any, daily_payload: dict[str, Any] | None = None) -> str:
    latest = data[-1] if isinstance(data, list) and data else {}
    stats_data = _extract_data((daily_payload or {}).get("stats"))
    if not isinstance(latest, dict):
        latest = {}
    return _render_label_value_list(
        [
            ("日期", latest.get("calendarDate") or _find_nested_value(stats_data, ("calendarDate",))),
            ("步數", latest.get("totalSteps") or _find_nested_value(stats_data, ("totalSteps",))),
            ("距離", _format_distance(latest.get("totalDistanceMeters") or latest.get("totalDistance") or _find_nested_value(stats_data, ("totalDistanceMeters",)))),
            ("步數目標", latest.get("stepGoal") or _find_nested_value(stats_data, ("dailyStepGoal",))),
            (
                "步數達成率",
                _format_ratio(
                    latest.get("totalSteps") or _find_nested_value(stats_data, ("totalSteps",)),
                    latest.get("stepGoal") or _find_nested_value(stats_data, ("dailyStepGoal",)),
                ),
            ),
        ]
    )


def _render_hydration_section(data: Any) -> str:
    if not isinstance(data, dict):
        return "- 沒有資料。"
    return _render_label_value_list(
        [
            ("今日補水量", _format_ml(data.get("valueInML"))),
            ("補水目標", _format_ml(data.get("goalInML"))),
            ("目標達成率", _format_ratio(data.get("valueInML"), data.get("goalInML"))),
            ("活動額外補水", _format_ml(data.get("activityIntakeInML"))),
            ("流汗估計", _format_ml(data.get("sweatLossInML"))),
            ("最近記錄時間", data.get("lastEntryTimestampLocal")),
        ]
    )


def _render_generic_section(data: Any) -> str:
    if isinstance(data, dict):
        return _render_key_values(data)
    if isinstance(data, list):
        return "\n".join(f"- {_translate_value(item)}" for item in data[:20]) or "- 沒有資料。"
    return f"- {_translate_value(data) or '沒有資料。'}"


def _render_collapsible_raw_data(title: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    return "\n".join(
        [
            "<details>",
            f"<summary>{title}</summary>",
            "",
            "```json",
            raw,
            "```",
            "</details>",
        ]
    )


def _render_label_value_list(items: list[tuple[str, Any]]) -> str:
    lines = []
    for label, value in items:
        if value in (None, "", "null"):
            continue
        lines.append(f"- **{label}**：{_translate_value(value)}")
    return "\n".join(lines) if lines else "- 沒有資料。"


def _extract_data(block: Any) -> Any:
    return block.get("data") if isinstance(block, dict) else None


def _find_nested_value(data: Any, keys: tuple[str, ...]) -> Any:
    if data is None:
        return None
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            current = None
            break
    if current not in (None, ""):
        return current
    if isinstance(data, dict):
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


def _pick_training_readiness(data: Any, field: str) -> Any:
    if isinstance(data, list) and data:
        return data[0].get(field)
    return None


def _pick_body_battery(data: Any, field: str) -> Any:
    if isinstance(data, list) and data:
        latest = data[-1]
        if isinstance(latest, dict):
            if field in latest:
                return latest.get(field)
            if field == "bodyBatteryMostRecentValue":
                return _pick_series_value(latest.get("bodyBatteryValuesArray"), last=True)
    return None


def _pick_series_value(values: Any, *, last: bool) -> Any:
    if not isinstance(values, list) or not values:
        return None
    iterable = reversed(values) if last else values
    for item in iterable:
        if isinstance(item, list) and len(item) >= 2 and item[1] not in (None, ""):
            return item[1]
    return None


def _series_min(values: Any, *, positive_only: bool = False) -> Any:
    if not isinstance(values, list):
        return None
    numbers = []
    for item in values:
        if isinstance(item, list) and len(item) >= 2 and item[1] is not None:
            if positive_only and item[1] <= 0:
                continue
            numbers.append(item[1])
    return min(numbers) if numbers else None


def _series_max(values: Any) -> Any:
    if not isinstance(values, list):
        return None
    numbers = [item[1] for item in values if isinstance(item, list) and len(item) >= 2 and item[1] is not None]
    return max(numbers) if numbers else None


def _summarize_body_battery_events(events: Any) -> str:
    if not isinstance(events, list) or not events:
        return ""
    parts = []
    for item in events[:3]:
        if not isinstance(item, dict):
            continue
        label = _translate_value(item.get("eventType"))
        impact = item.get("bodyBatteryImpact")
        duration = _format_milliseconds(item.get("durationInMilliseconds"))
        text = label
        if impact not in (None, ""):
            text += f"（變化 {impact}）"
        if duration:
            text += f" {duration}"
        parts.append(text)
    return "、".join(parts)


def _translate_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return ", ".join(_translate_value(item) for item in value[:10])
    if isinstance(value, dict):
        if "typeKey" in value:
            return _translate_value(value["typeKey"])
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    return VALUE_TRANSLATIONS.get(text, text)


def _stringify(value: Any) -> str:
    return _translate_value(value)


def _format_distance(value: Any) -> str:
    try:
        meters = float(value)
    except (TypeError, ValueError):
        return _translate_value(value)
    return f"{meters / 1000:.2f} 公里"


def _format_number(value: Any) -> str:
    if value in (None, "", "null"):
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _format_ratio(value: Any, goal: Any) -> str:
    try:
        current = float(value)
        target = float(goal)
    except (TypeError, ValueError):
        return ""
    if target <= 0:
        return ""
    return f"{(current / target) * 100:.0f}%"


def _format_seconds(value: Any) -> str:
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return _translate_value(value)
    if seconds <= 0:
        return "0 分 0 秒"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} 小時 {minutes} 分 {secs} 秒"
    return f"{minutes} 分 {secs} 秒"


def _format_milliseconds(value: Any) -> str:
    try:
        milliseconds = float(value)
    except (TypeError, ValueError):
        return _translate_value(value)
    return _format_seconds(milliseconds / 1000)


def _format_calories(value: Any) -> str:
    text = _translate_value(value)
    return f"{text} 大卡" if text else ""


def _format_ml(value: Any) -> str:
    text = _translate_value(value)
    return f"{text} ml" if text else ""


def _format_pace(distance_m: Any, duration_s: Any) -> str:
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


def _timestamp_to_local_text(value: Any) -> str:
    try:
        timestamp = int(float(value))
    except (TypeError, ValueError):
        return _format_datetime_text(value)
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _format_datetime_text(value: Any) -> str:
    if value in (None, "", "null"):
        return ""
    if isinstance(value, (int, float)):
        return _timestamp_to_local_text(value)
    text = str(value).replace("T", " ")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _translate_bool(value: Any) -> str:
    return "是" if value is True else "否" if value is False else _translate_value(value)


def _activity_end_time_local(payload: dict[str, Any]) -> str:
    end_local = _format_datetime_text(payload.get("endTimeLocal"))
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
    return _format_datetime_text(payload.get("endTimeGMT"))


def _activity_type_label(payload: dict[str, Any]) -> str:
    name = _translate_value(payload.get("activityName"))
    if name:
        return name
    type_key = _stringify(payload.get("activityType", {}).get("typeKey")).lower()
    return ACTIVITY_TYPE_LABELS.get(type_key, _translate_value(type_key or "活動"))


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "-", value, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned or "活動"


def _remove_stale_activity_notes(note_dir: Path, activity_id: str, keep_path: Path) -> None:
    for existing in note_dir.glob(f"*-{activity_id}.md"):
        if existing != keep_path:
            existing.unlink(missing_ok=True)


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
                lines.append(f"- **{current}**：")
                nested = _render_key_values(value, current)
                if nested:
                    lines.append(nested)
            elif isinstance(value, list):
                lines.append(f"- **{current}**：{json.dumps(value[:20], ensure_ascii=False)}")
            else:
                text = _translate_value(value)
                if text != "":
                    lines.append(f"- **{current}**：{text}")
    return "\n".join(lines) if lines else "- 沒有資料。"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
