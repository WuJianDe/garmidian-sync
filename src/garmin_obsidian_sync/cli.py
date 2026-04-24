from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .config import AppConfig, load_config, validate_config
from .exporter import export_obsidian_notes
from .garmindb_wrapper import ensure_runtime_dirs, run_garmindb_sync, write_garmindb_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync GarminDB data and export notes to Obsidian.")
    parser.add_argument("--config", default="config.local.json", help="Path to config JSON file.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create runtime directories and GarminDB config.")

    sync_parser = subparsers.add_parser("sync", help="Run GarminDB sync.")
    sync_parser.add_argument("--full", action="store_true", help="Run a full sync instead of --latest.")

    subparsers.add_parser("export", help="Export Markdown notes into Obsidian.")

    run_parser = subparsers.add_parser("run", help="Run sync then export.")
    run_parser.add_argument("--full", action="store_true", help="Run a full sync instead of --latest.")
    return parser


def _load_and_validate(config_path: str) -> AppConfig:
    config = load_config(config_path)
    validate_config(config)
    return config


def command_init(config_path: str) -> int:
    config = load_config(config_path)
    ensure_runtime_dirs(config)
    write_garmindb_config(config)
    print(f"Initialized runtime at: {config.runtime_home}")
    print(f"GarminDB config: {config.garmindb_config_path}")
    print(f"Obsidian export root: {config.obsidian_root_path}")
    return 0


def command_sync(config_path: str, full: bool) -> int:
    config = _load_and_validate(config_path)
    ensure_runtime_dirs(config)

    if shutil.which("garmindb_cli.py") is None and " " not in config.garmin_command and Path(config.garmin_command).name == config.garmin_command:
        print(
            "Warning: garmindb_cli.py was not found in PATH. "
            "If you installed GarminDB in a virtual environment, activate it first or set garmin.command in config.",
            file=sys.stderr,
        )

    result = run_garmindb_sync(config, full=full)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def command_export(config_path: str) -> int:
    config = _load_and_validate(config_path)
    result = export_obsidian_notes(config)
    print(f"Exported {result['daily_notes']} daily notes and {result['activity_notes']} activity notes.")
    print(f"Obsidian root: {config.obsidian_root_path}")
    return 0


def command_run(config_path: str, full: bool) -> int:
    sync_code = command_sync(config_path, full=full)
    if sync_code != 0:
        return sync_code
    return command_export(config_path)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        return command_init(args.config)
    if args.command == "sync":
        return command_sync(args.config, full=args.full)
    if args.command == "export":
        return command_export(args.config)
    if args.command == "run":
        return command_run(args.config, full=args.full)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
