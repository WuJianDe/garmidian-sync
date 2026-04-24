from __future__ import annotations

import argparse
import json
import os
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
from urllib.parse import urlparse

from .cli import command_doctor, command_export, command_init, command_run, command_sync
from .config import load_config


HTML_PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Garmin Obsidian Sync</title>
  <style>
    :root {
      --bg: #f4efe7;
      --card: #fffaf3;
      --ink: #1f2a24;
      --muted: #647067;
      --line: #dccfbc;
      --accent: #2c6e49;
      --accent-2: #d68c45;
      --danger: #b8402a;
      --shadow: 0 18px 50px rgba(44, 47, 38, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft JhengHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(214, 140, 69, 0.20), transparent 24rem),
        linear-gradient(180deg, #f7f1e8 0%, var(--bg) 100%);
      min-height: 100vh;
    }
    .shell {
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }
    .hero {
      display: grid;
      gap: 18px;
      grid-template-columns: 1.2fr 0.8fr;
      align-items: stretch;
      margin-bottom: 24px;
    }
    .panel {
      background: rgba(255, 250, 243, 0.92);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }
    .hero-main {
      padding: 28px;
    }
    .eyebrow {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(44, 110, 73, 0.10);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    h1 {
      margin: 16px 0 10px;
      font-size: clamp(30px, 4vw, 52px);
      line-height: 1.04;
    }
    .lead {
      margin: 0;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.7;
      max-width: 52rem;
    }
    .hero-side {
      padding: 24px;
      display: grid;
      gap: 14px;
      align-content: start;
    }
    .metric {
      padding: 14px 16px;
      border-radius: 16px;
      background: #fff;
      border: 1px solid var(--line);
    }
    .metric-label {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }
    .metric-value {
      font-size: 18px;
      font-weight: 700;
      word-break: break-all;
    }
    .layout {
      display: grid;
      grid-template-columns: 0.95fr 1.05fr;
      gap: 18px;
    }
    .actions, .log {
      padding: 22px;
    }
    .section-title {
      margin: 0 0 8px;
      font-size: 20px;
    }
    .section-copy {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.6;
    }
    .button-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    button {
      border: none;
      border-radius: 16px;
      padding: 14px 16px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 120ms ease, opacity 120ms ease, box-shadow 120ms ease;
      box-shadow: 0 8px 18px rgba(44, 110, 73, 0.12);
    }
    button:hover { transform: translateY(-1px); }
    button:disabled { cursor: not-allowed; opacity: 0.55; transform: none; box-shadow: none; }
    .primary { background: var(--accent); color: white; }
    .secondary { background: #fff; color: var(--ink); border: 1px solid var(--line); }
    .warm { background: var(--accent-2); color: #23180d; }
    .status-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
    }
    .pill {
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 700;
      background: rgba(44, 110, 73, 0.10);
      color: var(--accent);
    }
    .pill.error {
      background: rgba(184, 64, 42, 0.10);
      color: var(--danger);
    }
    .pill.running {
      background: rgba(214, 140, 69, 0.16);
      color: #8b5a21;
    }
    pre {
      margin: 0;
      min-height: 420px;
      max-height: 70vh;
      overflow: auto;
      padding: 18px;
      background: #1d221f;
      color: #e8f0e8;
      border-radius: 18px;
      line-height: 1.55;
      font-family: Consolas, "Cascadia Code", monospace;
      font-size: 13px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .footer-note {
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    @media (max-width: 920px) {
      .hero, .layout { grid-template-columns: 1fr; }
      .button-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="hero">
      <section class="panel hero-main">
        <span class="eyebrow">Local Control Panel</span>
        <h1>Garmin 到 Obsidian 的同步面板</h1>
        <p class="lead">這是你本機的控制頁。你可以在這裡檢查環境、抓最新資料、做完整同步，或直接打開 Obsidian 匯出資料夾，不用再手動輸入指令。</p>
      </section>
      <aside class="panel hero-side">
        <div class="metric">
          <div class="metric-label">設定檔</div>
          <div class="metric-value" id="configPath">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">Obsidian 目錄</div>
          <div class="metric-value" id="obsidianRoot">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">每日快照數量</div>
          <div class="metric-value" id="dbCount">-</div>
        </div>
      </aside>
    </div>

    <div class="layout">
      <section class="panel actions">
        <h2 class="section-title">操作</h2>
        <p class="section-copy">建議先按「檢查環境」。如果狀態正常，再按「抓最新資料並匯出」。</p>
        <div class="button-grid">
          <button class="secondary" data-action="doctor">檢查環境</button>
          <button class="primary" data-action="run-latest">抓最新資料並匯出</button>
          <button class="warm" data-action="run-full">完整同步並匯出</button>
          <button class="secondary" data-action="export">只匯出 Obsidian</button>
          <button class="secondary" data-action="init">重新初始化</button>
          <button class="secondary" data-action="open-obsidian">打開 Obsidian 資料夾</button>
        </div>
        <div class="status-bar">
          <span class="pill" id="taskStatus">等待操作</span>
          <span class="pill" id="taskName">目前任務：無</span>
          <span class="pill" id="lastCode">最後狀態碼：-</span>
        </div>
        <div class="footer-note">提示：同步過程如果遇到 Garmin 限流，系統會自動延遲後重試。</div>
      </section>

      <section class="panel log">
        <h2 class="section-title">執行紀錄</h2>
        <p class="section-copy">這裡會顯示最新任務的輸出結果與診斷資訊。</p>
        <pre id="log">尚未執行任何動作。</pre>
      </section>
    </div>
  </div>

  <script>
    const statusEl = document.getElementById("taskStatus");
    const taskEl = document.getElementById("taskName");
    const codeEl = document.getElementById("lastCode");
    const logEl = document.getElementById("log");
    const configPathEl = document.getElementById("configPath");
    const obsidianRootEl = document.getElementById("obsidianRoot");
    const dbCountEl = document.getElementById("dbCount");
    const buttons = Array.from(document.querySelectorAll("button[data-action]"));

    function setButtonsDisabled(disabled) {
      buttons.forEach((button) => {
        if (button.dataset.action === "open-obsidian") {
          button.disabled = false;
          return;
        }
        button.disabled = disabled;
      });
    }

    async function refreshStatus() {
      const res = await fetch("/api/status");
      const data = await res.json();
      statusEl.textContent = data.running ? "執行中" : "待命中";
      statusEl.className = "pill " + (data.running ? "running" : (data.last_exit_code && data.last_exit_code !== 0 ? "error" : ""));
      taskEl.textContent = "目前任務：" + (data.task_name || "無");
      codeEl.textContent = "最後狀態碼：" + (data.last_exit_code ?? "-");
      logEl.textContent = data.log || "尚未執行任何動作。";
      configPathEl.textContent = data.config_path || "-";
      obsidianRootEl.textContent = data.obsidian_root || "-";
      dbCountEl.textContent = String(data.daily_json_count ?? "-");
      setButtonsDisabled(Boolean(data.running));
    }

    async function runAction(action) {
      const res = await fetch("/api/actions/" + action, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || "操作失敗");
      }
      await refreshStatus();
    }

    buttons.forEach((button) => {
      button.addEventListener("click", () => runAction(button.dataset.action));
    });

    refreshStatus();
    setInterval(refreshStatus, 2000);
  </script>
</body>
</html>
"""


@dataclass
class AppState:
    config_path: str
    running: bool = False
    task_name: str = ""
    last_exit_code: int | None = None
    log: str = "尚未執行任何動作。"
    updated_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, object]:
        config = load_config(self.config_path)
        return {
            "running": self.running,
            "task_name": self.task_name,
            "last_exit_code": self.last_exit_code,
            "log": self.log,
            "config_path": str(Path(self.config_path).resolve()),
            "obsidian_root": str(config.obsidian_root_path),
            "daily_json_count": len(list(config.raw_daily_dir.glob("*.json"))) if config.raw_daily_dir.exists() else 0,
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
            output = f"Unhandled error:\n{exc}"
            code = 1
        with state.lock:
            state.running = False
            state.last_exit_code = code
            state.log = output
            state.updated_at = time.time()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return True


def build_handler(state: AppState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GarminObsidianSyncWeb/0.1"

        def _send_json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(HTML_PAGE)
                return
            if parsed.path == "/api/status":
                with state.lock:
                    payload = state.snapshot()
                self._send_json(payload)
                return
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not parsed.path.startswith("/api/actions/"):
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return

            action = parsed.path.rsplit("/", 1)[-1]
            if action == "open-obsidian":
                config = load_config(state.config_path)
                os.startfile(config.obsidian_root_path)  # type: ignore[attr-defined]
                self._send_json({"ok": True})
                return

            tasks: dict[str, tuple[str, Callable[[], int]]] = {
                "doctor": ("檢查環境", lambda: command_doctor(state.config_path)),
                "init": ("重新初始化", lambda: command_init(state.config_path)),
                "export": ("只匯出 Obsidian", lambda: command_export(state.config_path)),
                "run-latest": ("抓最新資料並匯出", lambda: command_run(state.config_path, full=False)),
                "run-full": ("完整同步並匯出", lambda: command_run(state.config_path, full=True)),
                "sync-latest": ("只抓最新資料", lambda: command_sync(state.config_path, full=False)),
                "sync-full": ("完整抓取 Garmin 資料", lambda: command_sync(state.config_path, full=True)),
            }
            task = tasks.get(action)
            if task is None:
                self._send_json({"error": "Unknown action"}, status=HTTPStatus.BAD_REQUEST)
                return
            started = _start_background_task(state, task[0], task[1])
            if not started:
                self._send_json({"error": "Another task is already running."}, status=HTTPStatus.CONFLICT)
                return
            self._send_json({"ok": True})

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local web UI for Garmin Obsidian Sync.")
    parser.add_argument("--config", default="config.local.json", help="Path to config JSON file.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the local web server.")
    parser.add_argument("--port", default=8765, type=int, help="Port to bind the local web server.")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    state = AppState(config_path=args.config)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(state))
    url = f"http://{args.host}:{args.port}/"
    print(f"Garmin Obsidian web UI running at {url}")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down web UI...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
