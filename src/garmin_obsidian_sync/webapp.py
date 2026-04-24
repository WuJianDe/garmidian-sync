from __future__ import annotations

import argparse
import json
import mimetypes
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
        }


def _run_capture(task: Callable[[], int]) -> tuple[int, str]:
    stdout = StringIO()
    stderr = StringIO()
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
        state.updated_at = time.time()

    def worker() -> None:
        code = 1
        output = ""
        try:
            code, output = _run_capture(task)
        except Exception as exc:  # noqa: BLE001
            output = f"執行時發生未處理錯誤：\n{exc}"
            code = 1
        with state.lock:
            state.running = False
            state.last_exit_code = code
            state.last_result = "成功" if code == 0 else "失敗"
            state.log = output
            state.updated_at = time.time()

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
            tasks: dict[str, tuple[str, Callable[[], int]]] = {
                "run-latest": ("抓最新資料並匯出", lambda: command_run(state.config_path, full=False)),
                "run-full": ("完整同步並匯出", lambda: command_run(state.config_path, full=True)),
            }
            task = tasks.get(action)
            if task is None:
                self._send_json({"error": "Unknown action"}, status=HTTPStatus.BAD_REQUEST)
                return
            started = _start_background_task(state, task[0], task[1])
            if not started:
                self._send_json({"error": "目前已有任務執行中，請稍候。"}, status=HTTPStatus.CONFLICT)
                return
            self._send_json({"ok": True})

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
    for path in sorted(root.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        note = path.read_text(encoding="utf-8")
        title = _extract_title(note) or path.stem
        subtitle = _extract_subtitle(path, kind)
        preview = _extract_preview(note)
        records.append(
            {
                "id": path.relative_to(root).as_posix(),
                "title": title,
                "subtitle": subtitle,
                "preview": preview,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime)),
            }
        )
    return records


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


def _extract_subtitle(path: Path, kind: str) -> str:
    if kind == "daily":
        return path.stem
    parts = path.stem.split("-")
    if len(parts) >= 4:
        return f"{parts[0]}-{parts[1]}-{parts[2]} | {parts[-1]}"
    return path.stem


def _extract_preview(note: str) -> str:
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
    start_marker = "<details>\n<summary>原始"
    start = note.find(start_marker)
    if start == -1:
        return note
    end = note.find("</details>", start)
    if end == -1:
        return note
    replacement = "## 原始資料\n\n已在網頁閱讀模式中收合。若要看完整 raw JSON，請回 Obsidian 查看。\n"
    return note[:start].rstrip() + "\n\n" + replacement + note[end + len("</details>") :]


if __name__ == "__main__":
    raise SystemExit(main())
