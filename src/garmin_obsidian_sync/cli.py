from __future__ import annotations

import argparse
import sys

from .config import AppConfig, load_config, validate_config
from .exporter import export_obsidian_notes
from .garmin_connect_sync import get_sync_diagnostics, initialize_storage, run_garmin_sync
from .runtime import CancelCheck, ProgressCallback, emit_progress


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Garmin Connect data and export notes to Obsidian.")
    parser.add_argument("--config", default="config.local.json", help="Path to config JSON file.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create runtime directories and local sync storage.")

    sync_parser = subparsers.add_parser("sync", help="Run Garmin Connect sync.")
    sync_parser.add_argument("--full", action="store_true", help="Run a full sync instead of --latest.")
    sync_parser.add_argument("--start-date", help="Sync start date in YYYY-MM-DD format.")
    sync_parser.add_argument("--end-date", help="Sync end date in YYYY-MM-DD format.")

    subparsers.add_parser("export", help="Export Markdown notes into Obsidian.")
    subparsers.add_parser("doctor", help="Show config and environment diagnostics without printing secrets.")

    run_parser = subparsers.add_parser("run", help="Run sync then export.")
    run_parser.add_argument("--full", action="store_true", help="Run a full sync instead of --latest.")
    run_parser.add_argument("--start-date", help="Sync start date in YYYY-MM-DD format.")
    run_parser.add_argument("--end-date", help="Sync end date in YYYY-MM-DD format.")
    return parser


def _load_and_validate(config_path: str) -> AppConfig:
    config = load_config(config_path)
    validate_config(config)
    return config


def command_init(config_path: str) -> int:
    config = load_config(config_path)
    initialize_storage(config)
    print(f"Initialized runtime at: {config.runtime_home}")
    print(f"Garmin token store: {config.garmin_tokenstore_path}")
    print(f"Health data root: {config.healthdata_dir}")
    print(f"Obsidian export root: {config.obsidian_root_path}")
    return 0


def command_sync(
    config_path: str,
    full: bool,
    start_date: str | None = None,
    end_date: str | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> int:
    print("步驟 1/3：檢查同步設定")
    emit_progress(progress_callback, "cli_step", {"step": "檢查同步設定"})
    config = _load_and_validate(config_path)
    print("步驟 2/3：開始抓取 Garmin 資料")
    emit_progress(progress_callback, "cli_step", {"step": "開始抓取 Garmin 資料"})
    result = run_garmin_sync(
        config,
        full=full,
        start_date=start_date,
        end_date=end_date,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    print("步驟 2/3：Garmin 資料抓取完成")
    emit_progress(progress_callback, "cli_step", {"step": "Garmin 資料抓取完成"})
    print(
        f"本次同步完成：{result.start_date} 到 {result.end_date}，"
        f"新增或更新 {result.daily_files} 份每日快照、{result.activity_files} 份活動資料。"
    )
    return 0


def command_export(
    config_path: str,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> int:
    print("步驟 3/3：開始匯出 Obsidian 筆記")
    emit_progress(progress_callback, "cli_step", {"step": "開始匯出 Obsidian 筆記"})
    config = _load_and_validate(config_path)
    result = export_obsidian_notes(config, progress_callback=progress_callback, cancel_check=cancel_check)
    print("步驟 3/3：Obsidian 筆記匯出完成")
    emit_progress(progress_callback, "cli_step", {"step": "Obsidian 筆記匯出完成"})
    print(
        f"匯出完成：目前共整理 {result['daily_notes']} 篇每日筆記（更新 {result['daily_updated']} 篇）、"
        f"{result['activity_notes']} 篇活動筆記（更新 {result['activity_updated']} 篇）、"
        f"{result['ai_files']} 份 AI 摘要檔（更新 {result['ai_updated']} 份）。"
    )
    print(f"Obsidian 目錄：{config.obsidian_root_path}")
    return 0


def command_doctor(config_path: str) -> int:
    config = load_config(config_path)
    diagnostics = get_sync_diagnostics(config)
    print("Garmin Obsidian Sync 診斷資訊")
    for key, value in diagnostics.items():
        print(f"- {key}: {value}")
    try:
        validate_config(config)
    except ValueError as exc:
        print(f"- validation: failed ({exc})", file=sys.stderr)
        return 1
    print("- validation: ok")
    return 0


def command_run(
    config_path: str,
    full: bool,
    start_date: str | None = None,
    end_date: str | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> int:
    print("開始執行同步流程")
    emit_progress(progress_callback, "cli_step", {"step": "開始執行同步流程"})
    sync_code = command_sync(
        config_path,
        full=full,
        start_date=start_date,
        end_date=end_date,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    if sync_code != 0:
        return sync_code
    export_code = command_export(config_path, progress_callback=progress_callback, cancel_check=cancel_check)
    if export_code == 0:
        print("全部步驟完成")
        emit_progress(progress_callback, "cli_step", {"step": "全部步驟完成"})
    return export_code

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "init":
            return command_init(args.config)
        if args.command == "sync":
            return command_sync(args.config, full=args.full, start_date=args.start_date, end_date=args.end_date)
        if args.command == "export":
            return command_export(args.config)
        if args.command == "doctor":
            return command_doctor(args.config)
        if args.command == "run":
            return command_run(args.config, full=args.full, start_date=args.start_date, end_date=args.end_date)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
