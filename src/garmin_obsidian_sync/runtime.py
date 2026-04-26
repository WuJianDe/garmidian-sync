from __future__ import annotations

from typing import Any, Callable

ProgressCallback = Callable[[str, dict[str, Any] | None], None]
CancelCheck = Callable[[], bool]


def emit_progress(callback: ProgressCallback | None, event: str, payload: dict[str, Any] | None = None) -> None:
    if callback is None:
        return
    callback(event, payload or {})


def ensure_not_cancelled(cancel_check: CancelCheck | None) -> None:
    if cancel_check and cancel_check():
        raise RuntimeError("使用者已取消同步。")


def classify_error(message: str, log: str) -> str:
    combined = f"{message}\n{log}".lower()
    if "取消" in combined or "cancel" in combined:
        return "cancelled"
    if "限制登入請求次數" in combined or "too many requests" in combined or "rate limited" in combined:
        return "rate_limit"
    if "登入失敗" in combined or "authentication" in combined:
        return "auth"
    if "連線失敗" in combined or "connection" in combined or "econnrefused" in combined:
        return "network"
    if "缺少" in combined or "validation" in combined or "開始日期不能晚於結束日期" in combined:
        return "config"
    return "unknown"
