from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from garmin_obsidian_sync import webapp


class WebAppHelpersTest(unittest.TestCase):
    def test_extract_preview_hides_frontmatter(self) -> None:
        note = """---
type: "garmin-activity"
activity_id: "123"
---

# 活動紀錄

第一行摘要
第二行摘要
"""
        preview = webapp._extract_preview(note)
        self.assertNotIn("garmin-activity", preview)
        self.assertNotIn("activity_id", preview)
        self.assertEqual(preview, "第一行摘要 第二行摘要")

    def test_prepare_note_content_for_web_hides_frontmatter(self) -> None:
        note = """---
type: "garmin-activity"
activity_id: "123"
---

# 活動紀錄

內容
"""
        rendered = webapp._prepare_note_content_for_web(note)
        self.assertNotIn('type: "garmin-activity"', rendered)
        self.assertNotIn("# 活動紀錄", rendered)
        self.assertIn("內容", rendered)

    def test_prepare_note_content_for_web_hides_raw_details(self) -> None:
        note = """# 標題

## 區塊

內容

<details>
<summary>原始每日資料</summary>

```json
{"a": 1}
```
</details>
"""
        rendered = webapp._prepare_note_content_for_web(note)
        self.assertNotIn("原始資料", rendered)
        self.assertNotIn("已在網頁閱讀模式中收合", rendered)
        self.assertNotIn('{"a": 1}', rendered)
        self.assertNotIn("# 標題", rendered)
        self.assertIn("## 區塊", rendered)

    def test_list_notes_sorts_by_note_date_descending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            newer = root / "2026" / "2026-04-24-跑步-2.md"
            older = root / "2026" / "2026-04-18-瑜伽-1.md"
            newer.parent.mkdir(parents=True, exist_ok=True)
            older.parent.mkdir(parents=True, exist_ok=True)
            newer.write_text("# 新的紀錄\n\n內容", encoding="utf-8")
            older.write_text("# 舊的紀錄\n\n內容", encoding="utf-8")

            older_timestamp = 1_800_000_000
            newer_timestamp = 1_700_000_000
            older.touch()
            newer.touch()
            import os

            os.utime(older, (older_timestamp, older_timestamp))
            os.utime(newer, (newer_timestamp, newer_timestamp))

            with mock.patch.object(webapp, "_note_root", return_value=root):
                records = webapp._list_notes("unused.json", "activity")

            self.assertEqual(
                [record["id"] for record in records],
                ["2026/2026-04-24-跑步-2.md", "2026/2026-04-18-瑜伽-1.md"],
            )

    def test_list_notes_sorts_activity_by_activity_time_descending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            morning = root / "2026" / "2026-04-24-跑步-1.md"
            evening = root / "2026" / "2026-04-24-跑步-2.md"
            morning.parent.mkdir(parents=True, exist_ok=True)
            morning.write_text(
                '---\nactivity_time: "2026-04-24 07:30:00"\n---\n\n# 早上跑步\n',
                encoding="utf-8",
            )
            evening.write_text(
                '---\nactivity_time: "2026-04-24 21:10:00"\n---\n\n# 晚上跑步\n',
                encoding="utf-8",
            )

            with mock.patch.object(webapp, "_note_root", return_value=root):
                records = webapp._list_notes("unused.json", "activity")

            self.assertEqual(
                [record["id"] for record in records],
                ["2026/2026-04-24-跑步-2.md", "2026/2026-04-24-跑步-1.md"],
            )

    def test_classify_error_maps_rate_limit(self) -> None:
        self.assertEqual(webapp._classify_error("失敗", "Garmin 目前限制登入請求次數，請稍後再試。"), "rate_limit")

    def test_update_progress_updates_state_fields(self) -> None:
        state = webapp.AppState(config_path="config.local.json")
        webapp._update_progress(
            state,
            "daily_progress",
            {"step": "抓取每日快照", "current_day": "2026-04-25", "progress_current": 3, "progress_total": 7},
        )
        self.assertEqual(state.current_step, "抓取每日快照")
        self.assertEqual(state.current_day, "2026-04-25")
        self.assertEqual(state.progress_current, 3)
        self.assertEqual(state.progress_total, 7)

    def test_build_task_runner_returns_callable(self) -> None:
        state = webapp.AppState(config_path="config.local.json")
        runner = webapp._build_task_runner(state, start_date="2026-04-01", end_date="2026-04-07")
        self.assertTrue(callable(runner))

    def test_classify_error_maps_cancelled(self) -> None:
        self.assertEqual(webapp._classify_error("已取消", "使用者取消同步"), "cancelled")


if __name__ == "__main__":
    unittest.main()
