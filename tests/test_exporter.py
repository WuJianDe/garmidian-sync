from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from garmin_obsidian_sync.config import load_config
from garmin_obsidian_sync import exporter


class ExporterHelpersTest(unittest.TestCase):
    def test_safe_filename_part_keeps_chinese(self) -> None:
        self.assertEqual(exporter._safe_filename_part("瑜伽 Flow / Night"), "瑜伽-Flow-Night")

    def test_format_distance(self) -> None:
        self.assertEqual(exporter._format_distance(2847), "2.85 公里")

    def test_format_seconds(self) -> None:
        self.assertEqual(exporter._format_seconds(7800), "2 小時 10 分 0 秒")

    def test_format_milliseconds(self) -> None:
        self.assertEqual(exporter._format_milliseconds(7800335.9375), "2 小時 10 分 0 秒")

    def test_translate_value(self) -> None:
        self.assertEqual(exporter._translate_value("MODERATE"), "中等")
        self.assertEqual(exporter._translate_value("groups"), "群組可見")
        self.assertEqual(exporter._translate_value(True), "是")
        self.assertEqual(exporter._translate_value("GOOD_SLEEP_HISTORY"), "近期睡眠表現良好")
        self.assertEqual(exporter._translate_value("SLEEP_TIME_PASSED_RECOVERING_AND_INACTIVE"), "已過睡眠時段，但仍處於恢復狀態")
        self.assertEqual(exporter._translate_value("NO_ANAEROBIC_BENEFIT_0"), "無明顯無氧訓練效益")

    def test_activity_end_time_local_falls_back_to_duration(self) -> None:
        payload = {
            "startTimeLocal": "2026-04-18 07:20:08",
            "duration": 4317.77587890625,
        }
        self.assertEqual(exporter._activity_end_time_local(payload), "2026-04-18 08:32:05")

    def test_activity_file_sort_key_uses_activity_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "123.json"
            path.write_text('{"activityId":123,"startTimeLocal":"2026-04-24 21:10:00"}', encoding="utf-8")
            self.assertEqual(exporter._activity_file_sort_key(path), ("2026-04-24 21:10:00", "123"))

    def test_render_ai_daily_jsonl_contains_structured_fields(self) -> None:
        payload = {
            "date": "2026-04-25",
            "stats": {"data": {"totalSteps": 12345, "averageStressLevel": 31}},
            "sleep": {"data": {"dailySleepDTO": {"sleepScores": {"overall": {"value": 78}}}}},
        }
        rendered = exporter._render_ai_daily_jsonl([payload])
        self.assertIn('"date": "2026-04-25"', rendered)
        self.assertIn('"steps": 12345', rendered)
        self.assertIn('"stress_avg": 31', rendered)

    def test_write_if_changed_skips_same_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "same.md"
            self.assertTrue(exporter._write_if_changed(path, "hello\n"))
            self.assertFalse(exporter._write_if_changed(path, "hello\n"))

    def test_render_daily_summary_separates_daily_and_activity_totals(self) -> None:
        payload = {
            "stats": {"data": {"totalSteps": 17326, "totalDistanceMeters": 13621, "restingHeartRate": 48}},
            "sleep": {"data": {"dailySleepDTO": {"sleepScores": {"overall": {"value": 71}}}}},
            "training_readiness": {"data": {"score": 67}},
            "body_battery": {"data": {"bodyBatteryMostRecentValue": 25}},
            "hrv": {"data": {"hrvSummary": {"lastNightAvg": 100}}},
            "hydration": {"data": {"valueInML": 0}},
        }
        activities = [
            {"startTimeLocal": "2026-04-25 09:23:02", "distance": 1906.14, "duration": 1051.23, "calories": 142, "activityType": {"typeKey": "running"}},
            {"startTimeLocal": "2026-04-25 07:36:51", "distance": 5005.95, "duration": 2582.11, "calories": 318, "activityType": {"typeKey": "running"}},
        ]
        rendered = exporter._render_daily_summary(payload, activities)
        self.assertIn("## 全天累積", rendered)
        self.assertIn("## 今日活動合計", rendered)
        self.assertIn("**全天距離**：13.62 公里", rendered)
        self.assertIn("**活動總距離**：6.91 公里", rendered)
        self.assertIn("**跑步次數**：2", rendered)

    def test_activity_display_name_prefers_activity_name(self) -> None:
        payload = {"activityName": "大安區 跑步", "activityType": {"typeKey": "running"}}
        self.assertEqual(exporter._activity_display_name(payload), "大安區 跑步")

    def test_is_running_activity_accepts_type_key_or_name(self) -> None:
        self.assertTrue(exporter._is_running_activity({"activityType": {"typeKey": "running"}}))
        self.assertTrue(exporter._is_running_activity({"activityName": "大安區 跑步"}))
        self.assertFalse(exporter._is_running_activity({"activityType": {"typeKey": "yoga"}, "activityName": "晚間瑜伽"}))

    def test_load_last_sync_range_reads_saved_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "config.local.json"
            config_path.write_text(
                """
{
  "garmin": {
    "username_env": "GARMIN_USERNAME",
    "password_env": "GARMIN_PASSWORD"
  },
  "storage": {
    "healthdata_dir": "./data/HealthData"
  },
  "obsidian": {
    "vault_path": "./vault"
  },
  "export": {
    "daily_limit_per_section": 10
  }
}
""".strip(),
                encoding="utf-8",
            )
            config = load_config(config_path)
            config.metadata_dir.mkdir(parents=True, exist_ok=True)
            config.sync_state_path.write_text(
                '{"last_range_start":"2026-04-20","last_range_end":"2026-04-25"}',
                encoding="utf-8",
            )
            self.assertEqual(exporter._load_last_sync_range(config), ("2026-04-20", "2026-04-25"))

    def test_load_activity_payloads_for_range_filters_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            older = root / "1.json"
            in_range = root / "2.json"
            older.write_text('{"activityId":1,"startTimeLocal":"2026-04-18 07:00:00"}', encoding="utf-8")
            in_range.write_text('{"activityId":2,"startTimeLocal":"2026-04-24 07:00:00"}', encoding="utf-8")
            payloads = exporter._load_activity_payloads_for_range(
                [in_range, older],
                "2026-04-20",
                "2026-04-25",
            )
            self.assertEqual([payload["activityId"] for payload in payloads], [2])

    def test_export_ai_views_keeps_history_but_limits_latest_status_to_three_months(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "config.local.json"
            config_path.write_text(
                """
{
  "garmin": {
    "username_env": "GARMIN_USERNAME",
    "password_env": "GARMIN_PASSWORD"
  },
  "storage": {
    "healthdata_dir": "./data/HealthData"
  },
  "obsidian": {
    "vault_path": "./vault"
  },
  "export": {
    "daily_limit_per_section": 10
  }
}
""".strip(),
                encoding="utf-8",
            )
            config = load_config(config_path)
            config.metadata_dir.mkdir(parents=True, exist_ok=True)
            config.sync_state_path.write_text(
                '{"last_range_start":"2026-04-25","last_range_end":"2026-04-27"}',
                encoding="utf-8",
            )

            old_daily = root / "2026-01-26.json"
            edge_daily = root / "2026-01-27.json"
            new_daily = root / "2026-04-27.json"
            old_activity = root / "old-activity.json"
            edge_activity = root / "edge-activity.json"
            new_activity = root / "new-activity.json"
            old_daily.write_text('{"date":"2026-01-26","stats":{"data":{"totalSteps":1000}}}', encoding="utf-8")
            edge_daily.write_text('{"date":"2026-01-27","stats":{"data":{"totalSteps":1270}}}', encoding="utf-8")
            new_daily.write_text('{"date":"2026-04-27","stats":{"data":{"totalSteps":27000}}}', encoding="utf-8")
            old_activity.write_text(
                '{"activityId":1,"startTimeLocal":"2026-01-26 07:00:00","activityName":"舊活動"}',
                encoding="utf-8",
            )
            edge_activity.write_text(
                '{"activityId":3,"startTimeLocal":"2026-01-27 07:00:00","activityName":"邊界活動"}',
                encoding="utf-8",
            )
            new_activity.write_text(
                '{"activityId":2,"startTimeLocal":"2026-04-27 07:00:00","activityName":"新活動"}',
                encoding="utf-8",
            )

            exporter._export_ai_views(config, [old_daily, edge_daily, new_daily], [old_activity, edge_activity, new_activity])

            latest_status = (config.obsidian_ai_path / "latest-status.md").read_text(encoding="utf-8")
            daily_summary = (config.obsidian_ai_path / "daily-summary.md").read_text(encoding="utf-8")
            activity_summary = (config.obsidian_ai_path / "activity-summary.md").read_text(encoding="utf-8")
            self.assertNotIn("2026-01-26", latest_status)
            self.assertNotIn("舊活動", latest_status)
            self.assertIn("2026-01-27", latest_status)
            self.assertIn("邊界活動", latest_status)
            self.assertIn("2026-01-26", daily_summary)
            self.assertIn("2026-01-27", daily_summary)
            self.assertIn("2026-04-27", daily_summary)
            self.assertIn("舊活動", activity_summary)
            self.assertIn("邊界活動", activity_summary)
            self.assertIn("新活動", activity_summary)

    def test_render_ai_latest_status_uses_full_input_range(self) -> None:
        daily_payloads = [{"date": f"2026-04-{day:02d}", "stats": {"data": {}}} for day in range(1, 17)]
        activity_payloads = [{"activityId": day, "startTimeLocal": f"2026-04-{day:02d} 07:00:00"} for day in range(1, 13)]
        rendered = exporter._render_ai_latest_status(daily_payloads, activity_payloads)
        self.assertIn("2026-04-16", rendered)
        self.assertIn("2026-04-01", rendered)
        self.assertIn("ID 12", exporter._render_ai_activity_summary(activity_payloads))


if __name__ == "__main__":
    unittest.main()
