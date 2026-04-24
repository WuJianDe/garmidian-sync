from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import AppConfig
from .garmindb_wrapper import ensure_runtime_dirs, find_sqlite_files


DATE_COLUMN_CANDIDATES = (
    "date",
    "day",
    "calendar_date",
    "summary_date",
    "local_date",
    "start_date",
    "begin_date",
)

ACTIVITY_ID_CANDIDATES = (
    "activity_id",
    "activityid",
    "id",
)

ACTIVITY_TIME_CANDIDATES = (
    "begin_timestamp",
    "start_time",
    "start_timestamp",
    "start_datetime",
    "begin_datetime",
    "time",
    "date",
)

ACTIVITY_TYPE_CANDIDATES = (
    "sport",
    "activity_type",
    "type",
    "name",
    "sub_sport",
)

DAILY_TABLE_HINTS = (
    "daily",
    "summary",
    "sleep",
    "weight",
    "rhr",
    "rest",
    "stress",
    "steps",
    "monitor",
    "body",
    "training",
)

DAILY_TABLE_EXCLUDES = (
    "activity",
    "record",
    "lap",
    "sample",
    "debug",
)


@dataclass(slots=True)
class TableInfo:
    db_path: Path
    name: str
    kind: str
    columns: list[str]

    @property
    def lower_columns(self) -> list[str]:
        return [column.lower() for column in self.columns]


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _list_tables(db_path: Path) -> list[TableInfo]:
    items: list[TableInfo] = []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        for name, kind in rows:
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({_quote(name)})").fetchall()]
            items.append(TableInfo(db_path=db_path, name=name, kind=kind, columns=columns))
    return items


def _pick_column(columns: Iterable[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _table_name_matches(name: str, includes: tuple[str, ...], excludes: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in includes) and not any(token in lowered for token in excludes)


def _discover_daily_sources(db_files: list[Path]) -> list[tuple[TableInfo, str]]:
    sources: list[tuple[TableInfo, str]] = []
    for db_path in db_files:
        for table in _list_tables(db_path):
            date_column = _pick_column(table.columns, DATE_COLUMN_CANDIDATES)
            if not date_column:
                continue
            if not _table_name_matches(table.name, DAILY_TABLE_HINTS, DAILY_TABLE_EXCLUDES):
                continue
            sources.append((table, date_column))
    return sources


def _discover_activity_source(db_files: list[Path]) -> tuple[TableInfo, str, str | None, str | None] | None:
    scored: list[tuple[int, TableInfo, str, str | None, str | None]] = []
    for db_path in db_files:
        for table in _list_tables(db_path):
            lowered_name = table.name.lower()
            if "activ" not in lowered_name:
                continue
            id_column = _pick_column(table.columns, ACTIVITY_ID_CANDIDATES)
            time_column = _pick_column(table.columns, ACTIVITY_TIME_CANDIDATES)
            type_column = _pick_column(table.columns, ACTIVITY_TYPE_CANDIDATES)
            score = 0
            if id_column:
                score += 3
            if time_column:
                score += 3
            if type_column:
                score += 2
            if table.kind == "view":
                score += 1
            if "summary" in lowered_name:
                score += 1
            if score >= 5:
                scored.append((score, table, id_column or "id", time_column, type_column))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    _, table, id_column, time_column, type_column = scored[0]
    return table, id_column, time_column, type_column


def _fetch_distinct_dates(db_path: Path, table: str, date_column: str) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT date({_quote(date_column)}) AS d
            FROM {_quote(table)}
            WHERE {_quote(date_column)} IS NOT NULL
            ORDER BY d DESC
            """
        ).fetchall()
    return [row[0] for row in rows if row[0]]


def _fetch_rows_for_day(
    db_path: Path,
    table: str,
    date_column: str,
    day: str,
    limit: int,
) -> list[dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT *
            FROM {_quote(table)}
            WHERE date({_quote(date_column)}) = date(?)
            LIMIT ?
            """,
            (day, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def _fetch_activity_rows(
    table: TableInfo,
    id_column: str,
    time_column: str | None,
    limit: int,
) -> list[dict[str, object]]:
    order_by = f"ORDER BY {_quote(time_column)} DESC" if time_column else ""
    with sqlite3.connect(table.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT *
            FROM {_quote(table.name)}
            WHERE {_quote(id_column)} IS NOT NULL
            {order_by}
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _render_frontmatter(pairs: dict[str, str]) -> str:
    lines = ["---"]
    for key, value in pairs.items():
        escaped = value.replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def _render_key_values(row: dict[str, object]) -> str:
    lines: list[str] = []
    for key, value in row.items():
        text = _stringify(value)
        if text == "":
            continue
        lines.append(f"- **{key}**: {text}")
    return "\n".join(lines) if lines else "- No data"


def export_obsidian_notes(config: AppConfig) -> dict[str, int]:
    ensure_runtime_dirs(config)
    db_files = find_sqlite_files(config)
    if not db_files:
        raise FileNotFoundError(f"No SQLite files found under {config.healthdata_dir}")

    daily_count = _export_daily_notes(config, db_files)
    activity_count = _export_activity_notes(config, db_files)
    _write_schema_note(config, db_files)
    return {"daily_notes": daily_count, "activity_notes": activity_count}


def _export_daily_notes(config: AppConfig, db_files: list[Path]) -> int:
    sources = _discover_daily_sources(db_files)
    if not sources:
        return 0

    days: set[str] = set()
    for table, date_column in sources:
        days.update(_fetch_distinct_dates(table.db_path, table.name, date_column))

    written = 0
    daily_links: list[str] = []
    for day in sorted(days, reverse=True):
        dt = datetime.strptime(day, "%Y-%m-%d")
        note_dir = config.obsidian_daily_path / dt.strftime("%Y") / dt.strftime("%m")
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / f"{day}.md"

        sections: list[str] = []
        for table, date_column in sources:
            rows = _fetch_rows_for_day(
                table.db_path,
                table.name,
                date_column,
                day,
                config.daily_limit_per_section,
            )
            if not rows:
                continue
            title = f"## {table.db_path.stem}.{table.name}"
            rendered_rows = []
            for index, row in enumerate(rows, start=1):
                rendered_rows.append(f"### Row {index}\n{_render_key_values(row)}")
            sections.append(f"{title}\n\n" + "\n\n".join(rendered_rows))

        if not sections:
            continue

        frontmatter = _render_frontmatter(
            {
                "type": "garmin-daily",
                "date": day,
            }
        )
        body = "\n\n".join(
            [
                frontmatter,
                f"# Garmin Daily Summary - {day}",
                f"Generated from `{len(db_files)}` SQLite database file(s).",
                *sections,
            ]
        )
        note_path.write_text(body + "\n", encoding="utf-8")
        rel = note_path.relative_to(config.obsidian_vault_path).as_posix()
        daily_links.append(f"- [[{rel[:-3]}|{day}]]")
        written += 1

    index_body = "\n".join(
        [
            "# Garmin Daily Index",
            "",
            f"Total notes: {written}",
            "",
            *daily_links,
        ]
    )
    (config.obsidian_index_path / "Daily Index.md").write_text(index_body + "\n", encoding="utf-8")
    return written


def _export_activity_notes(config: AppConfig, db_files: list[Path]) -> int:
    source = _discover_activity_source(db_files)
    if not source:
        return 0

    table, id_column, time_column, type_column = source
    rows = _fetch_activity_rows(table, id_column, time_column, config.activity_limit)

    written = 0
    activity_links: list[str] = []
    for row in rows:
        raw_activity_id = _stringify(row.get(id_column))
        if not raw_activity_id:
            continue

        raw_time = _stringify(row.get(time_column)) if time_column else ""
        safe_time = raw_time.replace(":", "").replace(" ", "-").replace("/", "-")
        activity_date = raw_time[:10] if len(raw_time) >= 10 else "unknown-date"
        year = activity_date[:4] if len(activity_date) >= 4 else "unknown"
        activity_type = _stringify(row.get(type_column)) if type_column else "activity"
        slug_type = activity_type.lower().replace(" ", "-") or "activity"

        note_dir = config.obsidian_activity_path / year
        note_dir.mkdir(parents=True, exist_ok=True)
        note_name = f"{activity_date}-{safe_time[-4:] if safe_time else 'time'}-{slug_type}-{raw_activity_id}.md"
        note_path = note_dir / note_name

        frontmatter = _render_frontmatter(
            {
                "type": "garmin-activity",
                "activity_id": raw_activity_id,
                "activity_type": activity_type,
                "activity_time": raw_time or "unknown",
            }
        )
        body = "\n\n".join(
            [
                frontmatter,
                f"# Garmin Activity - {activity_type}",
                f"- **activity_id**: {raw_activity_id}",
                f"- **source**: {table.db_path.stem}.{table.name}",
                "",
                "## Data",
                _render_key_values(row),
            ]
        )
        note_path.write_text(body + "\n", encoding="utf-8")
        rel = note_path.relative_to(config.obsidian_vault_path).as_posix()
        activity_links.append(f"- [[{rel[:-3]}|{activity_date} {activity_type} #{raw_activity_id}]]")
        written += 1

    index_body = "\n".join(
        [
            "# Garmin Activity Index",
            "",
            f"Total notes: {written}",
            "",
            *activity_links,
        ]
    )
    (config.obsidian_index_path / "Activity Index.md").write_text(index_body + "\n", encoding="utf-8")
    return written


def _write_schema_note(config: AppConfig, db_files: list[Path]) -> None:
    grouped: dict[str, list[str]] = defaultdict(list)
    for db_path in db_files:
        lines: list[str] = []
        for table in _list_tables(db_path):
            lines.append(f"## {table.name} ({table.kind})")
            lines.append("")
            for column in table.columns:
                lines.append(f"- {column}")
            lines.append("")
        grouped[db_path.name] = lines

    parts = ["# Garmin Schema Snapshot", ""]
    for db_name, lines in grouped.items():
        parts.append(f"# {db_name}")
        parts.append("")
        parts.extend(lines)
    (config.obsidian_index_path / "Schema Snapshot.md").write_text("\n".join(parts) + "\n", encoding="utf-8")

