from __future__ import annotations

import unittest

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

    def test_activity_end_time_local_falls_back_to_duration(self) -> None:
        payload = {
            "startTimeLocal": "2026-04-18 07:20:08",
            "duration": 4317.77587890625,
        }
        self.assertEqual(exporter._activity_end_time_local(payload), "2026-04-18 08:32:05")


if __name__ == "__main__":
    unittest.main()
