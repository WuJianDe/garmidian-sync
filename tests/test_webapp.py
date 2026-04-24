from __future__ import annotations

import unittest

from garmin_obsidian_sync import webapp


class WebAppHelpersTest(unittest.TestCase):
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
        self.assertIn("已在網頁閱讀模式中收合", rendered)
        self.assertNotIn('{"a": 1}', rendered)


if __name__ == "__main__":
    unittest.main()
