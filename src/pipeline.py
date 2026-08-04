from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from src.config import DATABASE_PATH, RAW_DIR, REPORTS_DIR, SQL_DIR, ensure_directories


TABLES: dict[str, dict] = {
    "raw_members": {
        "file": "members.csv",
        "columns": [
            "member_id",
            "joined_at",
            "region",
            "preferred_channel",
            "email_consent",
            "push_consent",
            "is_suppressed",
        ],
        "ddl": """
            CREATE TABLE raw_members (
                member_id TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                region TEXT NOT NULL,
                preferred_channel TEXT NOT NULL,
                email_consent INTEGER NOT NULL,
                push_consent INTEGER NOT NULL,
                is_suppressed INTEGER NOT NULL
            )
        """,
    },
    "raw_events": {
        "file": "events.csv",
        "columns": [
            "event_id",
            "member_id",
            "anonymous_id",
            "event_name",
            "event_ts",
            "category",
            "platform",
            "source",
        ],
        "ddl": """
            CREATE TABLE raw_events (
                event_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                anonymous_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_ts TEXT NOT NULL,
                category TEXT,
                platform TEXT NOT NULL,
                source TEXT NOT NULL
            )
        """,
    },
    "raw_listings": {
        "file": "listings.csv",
        "columns": ["listing_id", "member_id", "category", "created_at", "sold_at", "sale_value"],
        "ddl": """
            CREATE TABLE raw_listings (
                listing_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sold_at TEXT,
                sale_value REAL NOT NULL
            )
        """,
    },
    "raw_campaign_touches": {
        "file": "campaign_touches.csv",
        "columns": [
            "touch_id",
            "member_id",
            "campaign_id",
            "variant",
            "channel",
            "sent_at",
            "opened_at",
            "clicked_at",
            "unsubscribed_at",
        ],
        "ddl": """
            CREATE TABLE raw_campaign_touches (
                touch_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                campaign_id TEXT NOT NULL,
                variant TEXT NOT NULL,
                channel TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                opened_at TEXT,
                clicked_at TEXT,
                unsubscribed_at TEXT
            )
        """,
    },
    "raw_consent_history": {
        "file": "consent_history.csv",
        "columns": ["consent_id", "member_id", "channel", "status", "effective_at", "source"],
        "ddl": """
            CREATE TABLE raw_consent_history (
                consent_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                effective_at TEXT NOT NULL,
                source TEXT NOT NULL
            )
        """,
    },
    "raw_campaign_exclusions": {
        "file": "campaign_exclusions.csv",
        "columns": ["member_id", "exclusion_reason", "start_at", "end_at"],
        "ddl": """
            CREATE TABLE raw_campaign_exclusions (
                member_id TEXT NOT NULL,
                exclusion_reason TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL
            )
        """,
    },
    "raw_experiment_assignments": {
        "file": "experiment_assignments.csv",
        "columns": ["experiment_id", "member_id", "variant", "assigned_at"],
        "ddl": """
            CREATE TABLE raw_experiment_assignments (
                experiment_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                variant TEXT NOT NULL,
                assigned_at TEXT NOT NULL
            )
        """,
    },
}


def _normalise(value: str) -> object:
    return None if value == "" else value


def _load_csv(connection: sqlite3.Connection, table: str, spec: dict) -> int:
    path = RAW_DIR / spec["file"]
    if not path.exists():
        raise FileNotFoundError(f"Missing raw input: {path}. Run without --skip-generate.")
    connection.execute(f"DROP TABLE IF EXISTS {table}")
    connection.execute(spec["ddl"])
    columns = spec["columns"]
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    rows: list[tuple] = []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            rows.append(tuple(_normalise(row[column]) for column in columns))
            if len(rows) >= 10_000:
                connection.executemany(insert_sql, rows)
                rows.clear()
        if rows:
            connection.executemany(insert_sql, rows)
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def build_warehouse() -> dict[str, int]:
    ensure_directories()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    row_counts: dict[str, int] = {}
    try:
        with connection:
            for table, spec in TABLES.items():
                row_counts[table] = _load_csv(connection, table, spec)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_member_ts ON raw_events(member_id, event_ts)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_listings_member_created ON raw_listings(member_id, created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_touches_member_sent ON raw_campaign_touches(member_id, sent_at)"
            )
            for sql_path in sorted(SQL_DIR.glob("*.sql")):
                connection.executescript(sql_path.read_text(encoding="utf-8"))
        for table in [
            "mart_member_360",
            "mart_campaign_eligible_audience",
            "mart_experiment_member_outcomes",
            "mart_experiment_results",
        ]:
            row_counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        _export_activation_sample(connection)
    finally:
        connection.close()
    return row_counts


def _export_activation_sample(connection: sqlite3.Connection) -> None:
    """Write a pseudonymous contract sample, never a full activation export."""
    columns = [
        "member_id",
        "campaign_id",
        "activation_channel",
        "preferred_category",
        "historical_listing_count",
        "marketing_contacts_7d",
        "audience_created_at",
    ]
    rows = connection.execute(
        f"""
            SELECT {', '.join(columns)}
            FROM mart_campaign_eligible_audience
            ORDER BY member_id
            LIMIT 50
        """
    ).fetchall()
    path = REPORTS_DIR / "activation_audience_sample.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)
