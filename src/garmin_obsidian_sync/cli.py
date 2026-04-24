from __future__ import annotations

import argparse
import sys

from .config import AppConfig, load_config, validate_config
from .exporter import export_obsidian_notes
from .garmin_connect_sync import get_sync_diagnostics, initialize_storage, run_garmin_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Garmin Connect data and export notes to Obsidian.")
    parser.add_argument("--config", default="config.local.json", help="Path to config JSON file.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create runtime directories and local sync storage.")

    sync_parser = subparsers.add_parser("sync", help="Run Garmin Connect sync.")
    sync_parser.add_argument("--full", action="store_true", help="Run a full sync instead of --latest.")

    subparsers.add_parser("export", help="Export Markdown notes into Obsidian.")
    subparsers.add_parser("doctor", help="Show config and environment diagnostics without printing secrets.")

    run_parser = subparsers.add_parser("run", help="Run sync then export.")
    run_parser.add_argument("--full", action="store_true", help="Run a full sync instead of --latest.")
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


def command_sync(config_path: str, full: bool) -> int:
    config = _load_and_validate(config_path)
    result = run_garmin_sync(config, full=full)
    print(
        f"本次同步完成：{result.start_date} 到 {result.end_date}，"
        f"新增或更新 {result.daily_files} 份每日快照、{result.activity_files} 份活動資料。"
    )
    return 0


def command_export(config_path: str) -> int:
    config = _load_and_validate(config_path)
    result = export_obsidian_notes(config)
    print(
        f"匯出完成：目前共整理 {result['daily_notes']} 篇每日筆記、"
        f"{result['activity_notes']} 篇活動筆記。"
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


def command_run(config_path: str, full: bool) -> int:
    sync_code = command_sync(config_path, full=full)
    if sync_code != 0:
        return sync_code
    return command_export(config_path)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "init":
            return command_init(args.config)
        if args.command == "sync":
            return command_sync(args.config, full=args.full)
        if args.command == "export":
            return command_export(args.config)
        if args.command == "doctor":
            return command_doctor(args.config)
        if args.command == "run":
            return command_run(args.config, full=args.full)
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
