from __future__ import annotations

import json
import re
from typing import Any

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
    "CALM_AWAKE": "清醒且平穩",
    "ACTIVITY": "活動",
    "READY_FOR_THE_DAY": "已準備好開始今天",
    "GOOD_SLEEP_HISTORY": "近期睡眠表現良好",
    "SLEEP_PREPARATION_RECOVERING_AND_INACTIVE": "恢復中，適合準備睡眠",
    "SLEEP_PREPARATION_RECOVERING_AND_EXERCISE": "恢復中且有運動，適合準備睡眠",
    "SLEEP_TIME_PASSED_STRESSFUL_AND_INACTIVE": "已過睡眠時段，身體偏疲勞",
    "SLEEP_TIME_PASSED_RECOVERING_AND_INACTIVE": "已過睡眠時段，但仍處於恢復狀態",
    "SLEEP_TIME_PASSED_RECOVERING_AND_EXERCISE": "已過睡眠時段，但仍在恢復且有運動",
    "BALANCE_STRESS_AND_RECOVERY": "恢復與壓力大致平衡",
    "WELL_RECOVERED": "恢復良好",
    "DAY_STRESSFUL_AND_EXERCISE": "白天壓力偏高且有運動",
    "AFTER_WAKEUP_RESET": "起床後更新",
    "AFTER_POST_EXERCISE_RESET": "運動後重新評估",
    "UPDATE_REALTIME_VARIABLES": "即時狀態更新",
    "NO_CHANGE_SLEEP": "睡眠後恢復時間無明顯變化",
    "EASY_AEROBIC": "輕鬆有氧",
    "EASY_RECOVERY": "輕鬆恢復",
}


def translate_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return ", ".join(translate_value(item) for item in value[:10])
    if isinstance(value, dict):
        if "typeKey" in value:
            return translate_value(value["typeKey"])
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    if text in VALUE_TRANSLATIONS:
        return VALUE_TRANSLATIONS[text]
    return translate_code_text(text)


def translate_code_text(text: str) -> str:
    if re.fullmatch(r"RECOVERY_\d+", text):
        return "恢復效果"
    if re.fullmatch(r"NO_ANAEROBIC_BENEFIT_\d+", text):
        return "無明顯無氧訓練效益"
    if re.fullmatch(r"MINOR_AEROBIC_BENEFIT_\d+", text):
        return "輕微有氧訓練效益"
    if re.fullmatch(r"EXERCISE_TRAINING_EFFECT_\d+", text):
        return "運動帶來訓練效果"
    if text == "EXERCISE_TRAINING_EFFECT_BELOW_2":
        return "運動帶來輕度訓練效果"
    if re.fullmatch(r"[A-Z0-9]+(?:_[A-Z0-9]+)+", text):
        pretty = text.replace("_", " ").strip()
        if pretty:
            return pretty
    return text


def stringify(value: Any) -> str:
    return translate_value(value)


def activity_type_key(payload: dict[str, Any]) -> str:
    return stringify(payload.get("activityType", {}).get("typeKey")).lower()


def activity_display_name(payload: dict[str, Any]) -> str:
    name = translate_value(payload.get("activityName"))
    if name:
        return name
    type_key = activity_type_key(payload)
    return ACTIVITY_TYPE_LABELS.get(type_key, translate_value(type_key or "活動"))


def is_running_activity(payload: dict[str, Any]) -> bool:
    return activity_type_key(payload) == "running" or "跑步" in activity_display_name(payload)
