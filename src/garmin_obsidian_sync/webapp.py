from __future__ import annotations

import argparse
import json
import mimetypes
import re
import threading
import time
import webbrowser
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

from .cli import command_run
from .config import load_config, validate_config
from .garmin_connect_sync import initialize_storage
from .runtime import classify_error


FALLBACK_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Garmin 健康紀錄中心</title>
  <style>
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft JhengHei", sans-serif;
      background: linear-gradient(180deg, #ecf0e8 0%, #f6f2ea 100%);
      color: #1f2924;
    }
    .shell {
      max-width: 840px;
      margin: 0 auto;
      padding: 42px 20px;
    }
    .card {
      background: rgba(255, 252, 247, 0.92);
      border: 1px solid #d9cfbf;
      border-radius: 24px;
      box-shadow: 0 20px 50px rgba(31, 41, 36, 0.1);
      padding: 28px;
    }
    h1 {
      margin: 0 0 12px;
      font-size: 40px;
    }
    p, li {
      line-height: 1.75;
      color: #55625a;
    }
    code {
      background: #f3eee5;
      padding: 2px 6px;
      border-radius: 8px;
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="card">
      <h1>Garmin 健康紀錄中心</h1>
      <p>後端 API 已啟動，但前端建置檔尚未就緒。</p>
      <p>請在專案根目錄執行以下其中一種方式：</p>
      <ul>
        <li>開發模式：在 <code>frontend/</code> 執行 <code>npm install</code>，再執行 <code>npm run dev</code></li>
        <li>正式模式：在 <code>frontend/</code> 執行 <code>npm run build</code>，之後重新啟動這個服務</li>
      </ul>
      <p>API 仍可使用：<code>/api/status</code>、<code>/api/records</code>、<code>/api/note</code></p>
    </div>
  </div>
</body>
</html>
"""


@dataclass
class AppState:
    config_path: str
    running: bool = False
    task_name: str = ""
    last_exit_code: int | None = None
    last_result: str = "尚未執行任何動作。"
    log: str = "尚未執行任何動作。"
    progress_current: int = 0
    progress_total: int = 0
    current_step: str = ""
    current_day: str = ""
    error_category: str = ""
    cancel_requested: bool = False
    updated_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, object]:
        config = load_config(self.config_path)
        sync_state = {}
        if config.sync_state_path.exists():
            sync_state = json.loads(config.sync_state_path.read_text(encoding="utf-8"))
        return {
            "running": self.running,
            "task_name": self.task_name,
            "last_exit_code": self.last_exit_code,
            "last_result": self.last_result,
            "log": self.log,
            "last_sync_at": str(sync_state.get("last_sync_at", "")),
            "daily_count": len(list(config.obsidian_daily_path.rglob("*.md"))) if config.obsidian_daily_path.exists() else 0,
            "activity_count": len(list(config.obsidian_activity_path.rglob("*.md"))) if config.obsidian_activity_path.exists() else 0,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "current_step": self.current_step,
            "current_day": self.current_day,
            "error_category": self.error_category,
            "cancel_requested": self.cancel_requested,
        }


class _StreamingBuffer(StringIO):
    def __init__(self, state: AppState, *, is_stderr: bool = False) -> None:
        super().__init__()
        self._state = state
        self._is_stderr = is_stderr

    def write(self, text: str) -> int:  # type: ignore[override]
        written = super().write(text)
        with self._state.lock:
            stdout_text = getattr(self._state, "_stdout_capture", "")
            stderr_text = getattr(self._state, "_stderr_capture", "")
            if self._is_stderr:
                stderr_text += text
                setattr(self._state, "_stderr_capture", stderr_text)
            else:
                stdout_text += text
                setattr(self._state, "_stdout_capture", stdout_text)
            combined = stdout_text.strip()
            errors = stderr_text.strip()
            if errors:
                combined = f"{combined}\n\n[stderr]\n{errors}".strip()
            self._state.log = combined or "尚未執行任何動作。"
            self._state.updated_at = time.time()
        return written

    def flush(self) -> None:  # type: ignore[override]
        return


def _run_capture(state: AppState, task: Callable[[], int]) -> tuple[int, str]:
    stdout = _StreamingBuffer(state)
    stderr = _StreamingBuffer(state, is_stderr=True)
    with state.lock:
        setattr(state, "_stdout_capture", "")
        setattr(state, "_stderr_capture", "")
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = task()
    output = stdout.getvalue().strip()
    errors = stderr.getvalue().strip()
    if errors:
        output = f"{output}\n\n[stderr]\n{errors}".strip()
    return code, output or "No output."


def _start_background_task(state: AppState, task_name: str, task: Callable[[], int]) -> bool:
    with state.lock:
        if state.running:
            return False
        state.running = True
        state.task_name = task_name
        state.log = f"{task_name} 啟動中..."
        state.last_result = "執行中"
        state.progress_current = 0
        state.progress_total = 0
        state.current_step = "準備啟動"
        state.current_day = ""
        state.error_category = ""
        state.cancel_requested = False
        state.updated_at = time.time()

    def worker() -> None:
        code = 1
        output = ""
        try:
            code, output = _run_capture(state, task)
        except Exception as exc:  # noqa: BLE001
            output = f"執行時發生未處理錯誤：\n{exc}"
            code = 1
            with state.lock:
                state.error_category = classify_error(str(exc), output)
        with state.lock:
            state.running = False
            state.last_exit_code = code
            state.last_result = "已取消" if state.cancel_requested and code != 0 else ("成功" if code == 0 else "失敗")
            state.log = output
            if code == 0:
                state.error_category = ""
            elif not state.error_category:
                state.error_category = classify_error(state.last_result, output)
            state.updated_at = time.time()
            setattr(state, "_stdout_capture", "")
            setattr(state, "_stderr_capture", "")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return True


def build_handler(state: AppState, frontend_dist: Path | None) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GarminObsidianSyncApi/0.2"

        def _send_json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def _send_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/status":
                with state.lock:
                    payload = state.snapshot()
                self._send_json(payload)
                return
            if parsed.path == "/api/records":
                params = parse_qs(parsed.query)
                kind = params.get("kind", ["daily"])[0]
                try:
                    self._send_json({"records": _list_notes(state.config_path, kind)})
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if parsed.path == "/api/note":
                params = parse_qs(parsed.query)
                kind = params.get("kind", ["daily"])[0]
                note_id = params.get("id", [""])[0]
                try:
                    self._send_json(_read_note(state.config_path, kind, note_id))
                except FileNotFoundError:
                    self._send_json({"error": "找不到指定紀錄。"}, status=HTTPStatus.NOT_FOUND)
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._serve_frontend(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not parsed.path.startswith("/api/actions/"):
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return

            action = parsed.path.rsplit("/", 1)[-1]
            if action == "stop":
                with state.lock:
                    if not state.running:
                        self._send_json({"error": "目前沒有執行中的任務。"}, status=HTTPStatus.CONFLICT)
                        return
                    state.cancel_requested = True
                    state.current_step = "正在停止"
                    state.updated_at = time.time()
                self._send_json({"ok": True})
                return

            task: tuple[str, Callable[[], int]] | None = None
            if action == "run-latest":
                task = ("抓最新資料並匯出", _build_task_runner(state))
            elif action == "run-range":
                payload = self._read_json_body()
                start_date = str(payload.get("start_date", "")).strip()
                end_date = str(payload.get("end_date", "")).strip()
                if not start_date or not end_date:
                    self._send_json({"error": "請先輸入開始日期與結束日期。"}, status=HTTPStatus.BAD_REQUEST)
                    return
                task = (f"區間同步並匯出（{start_date} 到 {end_date}）", _build_task_runner(state, start_date=start_date, end_date=end_date))

            if task is None:
                self._send_json({"error": "Unknown action"}, status=HTTPStatus.BAD_REQUEST)
                return
            started = _start_background_task(state, task[0], task[1])
            if not started:
                self._send_json({"error": "目前已有任務執行中，請稍候。"}, status=HTTPStatus.CONFLICT)
                return
            self._send_json({"ok": True})

        def _read_json_body(self) -> dict[str, object]:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            if content_length <= 0:
                return {}
            raw = self.rfile.read(content_length)
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return {}

        def _serve_frontend(self, request_path: str) -> None:
            if frontend_dist is None or not frontend_dist.exists():
                self._send_bytes(FALLBACK_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return

            normalized = request_path if request_path not in {"", "/"} else "/index.html"
            relative = Path(unquote(normalized.lstrip("/")))
            target = (frontend_dist / relative).resolve()
            frontend_root = frontend_dist.resolve()

            if frontend_root not in target.parents and target != frontend_root:
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return

            if not target.exists() or target.is_dir():
                target = frontend_dist / "index.html"

            if not target.exists():
                self._send_bytes(FALLBACK_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return

            content_type, _ = mimetypes.guess_type(target.name)
            self._send_bytes(target.read_bytes(), content_type or "application/octet-stream")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local API/static server for Garmin Obsidian Sync.")
    parser.add_argument("--config", default="config.local.json", help="Path to config JSON file.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the local web server.")
    parser.add_argument("--port", default=8765, type=int, help="Port to bind the local web server.")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        validate_config(config)
        initialize_storage(config)
    except Exception as exc:  # noqa: BLE001
        print(f"啟動失敗：{exc}", flush=True)
        return 1

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    state = AppState(config_path=args.config)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(state, frontend_dist if frontend_dist.exists() else None))
    url = f"http://{args.host}:{args.port}/"
    print("啟動檢查完成")
    print(f"設定檔：{config.config_path}")
    print(f"資料目錄：{config.healthdata_dir}")
    print(f"Obsidian 目錄：{config.obsidian_root_path}")
    print(f"Token 目錄：{config.garmin_tokenstore_path}")
    print(f"本機 API / 前端入口：{url}")
    if frontend_dist.exists():
        print(f"前端建置目錄：{frontend_dist}")
    else:
        print("前端建置目錄尚未生成，將顯示後備頁面。")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("正在關閉本機服務...")
    finally:
        server.server_close()
    return 0


def _note_root(config_path: str, kind: str) -> Path:
    config = load_config(config_path)
    if kind == "daily":
        return config.obsidian_daily_path
    if kind == "activity":
        return config.obsidian_activity_path
    raise ValueError("不支援的紀錄類型。")


def _list_notes(config_path: str, kind: str) -> list[dict[str, object]]:
    root = _note_root(config_path, kind)
    if not root.exists():
        return []
    records: list[dict[str, object]] = []
    note_items: list[tuple[tuple[str, str, float], Path, str, str, str]] = []
    for path in root.rglob("*.md"):
        note = path.read_text(encoding="utf-8")
        title = _extract_title(note) or path.stem
        subtitle = _extract_subtitle(path, kind)
        preview = _extract_preview(note)
        note_items.append((_record_sort_key(root, path, note, kind), path, title, subtitle, preview))

    for sort_key, path, title, subtitle, preview in sorted(note_items, key=lambda item: item[0], reverse=True):
        records.append(
            {
                "id": path.relative_to(root).as_posix(),
                "title": title,
                "subtitle": subtitle,
                "preview": preview,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime)),
                "sort_key": sort_key[0],
            }
        )
    return records


def _record_sort_key(root: Path, path: Path, note: str, kind: str) -> tuple[str, str, float]:
    relative = path.relative_to(root).as_posix()
    if kind == "activity":
        activity_time = _extract_frontmatter_value(note, "activity_time") or path.stem
        return (activity_time, relative, path.stat().st_mtime)
    note_date = _extract_frontmatter_value(note, "date")
    match = re.match(r"(\d{4}-\d{2}-\d{2})", note_date or path.stem)
    date_prefix = match.group(1) if match else (note_date or "")
    return (date_prefix, relative, path.stat().st_mtime)


def _read_note(config_path: str, kind: str, note_id: str) -> dict[str, object]:
    if not note_id:
        raise ValueError("缺少紀錄 ID。")
    root = _note_root(config_path, kind)
    note_path = (root / note_id).resolve()
    root_resolved = root.resolve()
    if root_resolved not in note_path.parents and note_path != root_resolved:
        raise ValueError("非法的紀錄路徑。")
    if not note_path.exists() or note_path.suffix.lower() != ".md":
        raise FileNotFoundError(note_path)
    note = note_path.read_text(encoding="utf-8")
    return {
        "id": note_id,
        "title": _extract_title(note) or note_path.stem,
        "subtitle": _extract_subtitle(note_path, kind),
        "path": str(note_path),
        "content": _prepare_note_content_for_web(note),
    }


def _extract_title(note: str) -> str:
    for line in note.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _extract_frontmatter_value(note: str, key: str) -> str:
    if not note.startswith("---\n"):
        return ""
    end = note.find("\n---\n", 4)
    if end == -1:
        return ""
    frontmatter = note[4:end]
    pattern = rf"^{re.escape(key)}:\s*\"?(.*?)\"?$"
    for line in frontmatter.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            return match.group(1).strip().strip('"')
    return ""


def _extract_subtitle(path: Path, kind: str) -> str:
    if kind == "daily":
        return path.stem
    parts = path.stem.split("-")
    if len(parts) >= 4:
        return f"{parts[0]}-{parts[1]}-{parts[2]} | {parts[-1]}"
    return path.stem


def _extract_preview(note: str) -> str:
    note = _strip_frontmatter(note)
    lines = []
    for raw_line in note.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("---") or line.startswith("#") or line.startswith("```") or line.startswith("<details"):
            continue
        if line.startswith("<summary>"):
            continue
        lines.append(line)
        if len(lines) >= 2:
            break
    return " ".join(lines)[:140]


def _prepare_note_content_for_web(note: str) -> str:
    note = _strip_frontmatter(note)
    start_marker = "<details>\n<summary>原始"
    start = note.find(start_marker)
    if start == -1:
        return _strip_leading_title(note)
    end = note.find("</details>", start)
    if end == -1:
        return _strip_leading_title(note)
    cleaned = (note[:start].rstrip() + "\n\n" + note[end + len("</details>") :].lstrip()).strip()
    return _strip_leading_title(cleaned)


def _strip_frontmatter(note: str) -> str:
    if not note.startswith("---\n"):
        return note
    end = note.find("\n---\n", 4)
    if end == -1:
        return note
    return note[end + len("\n---\n") :].lstrip()


def _strip_leading_title(note: str) -> str:
    lines = note.splitlines()
    if not lines:
        return note
    if lines[0].startswith("# "):
        return "\n".join(lines[1:]).lstrip()
    return note


def _build_task_runner(
    state: AppState,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Callable[[], int]:
    return lambda: command_run(
        state.config_path,
        full=False,
        start_date=start_date,
        end_date=end_date,
        progress_callback=lambda event, payload: _update_progress(state, event, payload),
        cancel_check=lambda: _is_cancel_requested(state),
    )


def _update_progress(state: AppState, event: str, payload: dict[str, object] | None) -> None:
    payload = payload or {}
    with state.lock:
        if "step" in payload:
            state.current_step = str(payload["step"] or "")
        if "current_day" in payload:
            state.current_day = str(payload["current_day"] or "")
        if "progress_current" in payload:
            state.progress_current = int(payload["progress_current"] or 0)
        if "progress_total" in payload:
            state.progress_total = int(payload["progress_total"] or 0)
        state.updated_at = time.time()


def _is_cancel_requested(state: AppState) -> bool:
    with state.lock:
        return state.cancel_requested


def _classify_error(message: str, log: str) -> str:
    return classify_error(message, log)


if __name__ == "__main__":
    raise SystemExit(main())
