from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing

from src.config import (
    ACTIVATION_DATABASE_PATH,
    CAMPAIGN_DATE,
    DATABASE_PATH,
    REPORTS_DIR,
    ensure_directories,
)


DESTINATION_FIELDS = (
    "member_id",
    "campaign_id",
    "variant",
    "activation_channel",
    "preferred_category",
    "historical_listing_count",
    "marketing_contacts_7d",
    "audience_created_at",
)


def _idempotency_key(record: dict) -> str:
    natural_key = "|".join(
        str(record.get(field, "")) for field in ("campaign_id", "member_id", "variant")
    )
    return hashlib.sha256(natural_key.encode("utf-8")).hexdigest()[:24]


def _destination_payload(record: dict) -> dict:
    return {field: record.get(field) for field in DESTINATION_FIELDS}


def _payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_activation_records() -> list[dict]:
    """Build treatment-only records with internal fields for final safety validation."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
                SELECT
                    a.member_id,
                    a.campaign_id,
                    x.variant,
                    a.activation_channel,
                    a.preferred_category,
                    a.historical_listing_count,
                    a.marketing_contacts_7d,
                    a.audience_created_at,
                    m.is_suppressed,
                    m.within_contact_cap,
                    m.has_no_campaign_conflict,
                    CASE
                        WHEN a.activation_channel = 'email' THEN m.email_consent
                        WHEN a.activation_channel = 'push' THEN m.push_consent
                        ELSE 0
                    END AS has_channel_consent
                FROM mart_campaign_eligible_audience a
                JOIN raw_experiment_assignments x ON a.member_id = x.member_id
                JOIN mart_member_360 m ON a.member_id = m.member_id
                WHERE x.variant IN ('generic', 'personalized')
                ORDER BY a.member_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def initialize_destination(connection: sqlite3.Connection, *, reset: bool = False) -> None:
    if reset:
        connection.executescript(
            """
                DROP TABLE IF EXISTS sync_events;
                DROP TABLE IF EXISTS destination_memberships;
            """
        )
    connection.executescript(
        """
            CREATE TABLE IF NOT EXISTS destination_memberships (
                idempotency_key TEXT PRIMARY KEY,
                member_id TEXT NOT NULL,
                campaign_id TEXT NOT NULL,
                variant TEXT NOT NULL,
                activation_channel TEXT NOT NULL,
                preferred_category TEXT,
                payload_hash TEXT NOT NULL,
                first_synced_at TEXT NOT NULL,
                last_synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                idempotency_key TEXT,
                member_id TEXT,
                action TEXT NOT NULL,
                reason TEXT NOT NULL
            );
        """
    )


def _validation_failure(record: dict) -> tuple[str, str] | None:
    required = ("member_id", "campaign_id", "variant", "activation_channel")
    if any(not record.get(field) for field in required):
        return "rejected", "missing_required_field"
    if record["variant"] == "control":
        return "rejected", "control_not_activatable"
    if record["variant"] not in {"generic", "personalized"}:
        return "rejected", "unknown_variant"
    if record["activation_channel"] not in {"email", "push"}:
        return "rejected", "unsupported_channel"
    if record.get("is_suppressed"):
        return "suppressed", "member_suppressed"
    if not record.get("has_channel_consent"):
        return "suppressed", "channel_consent_missing"
    if not record.get("within_contact_cap"):
        return "suppressed", "contact_cap_reached"
    if not record.get("has_no_campaign_conflict"):
        return "suppressed", "campaign_conflict"
    return None


def sync_activation_records(
    records: list[dict],
    destination: sqlite3.Connection,
    *,
    run_id: str,
) -> dict:
    """Upsert safe records using a stable natural-key hash and log every outcome."""
    counts: Counter[str] = Counter()
    for record in records:
        failure = _validation_failure(record)
        key = _idempotency_key(record) if record.get("member_id") else None
        if failure:
            action, reason = failure
        else:
            payload = _destination_payload(record)
            payload_hash = _payload_hash(payload)
            existing = destination.execute(
                "SELECT payload_hash FROM destination_memberships WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing is None:
                destination.execute(
                    """
                        INSERT INTO destination_memberships (
                            idempotency_key, member_id, campaign_id, variant,
                            activation_channel, preferred_category, payload_hash,
                            first_synced_at, last_synced_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        payload["member_id"],
                        payload["campaign_id"],
                        payload["variant"],
                        payload["activation_channel"],
                        payload["preferred_category"],
                        payload_hash,
                        CAMPAIGN_DATE,
                        CAMPAIGN_DATE,
                    ),
                )
                action, reason = "created", "new_membership"
            elif existing[0] == payload_hash:
                action, reason = "unchanged", "idempotent_replay"
            else:
                destination.execute(
                    """
                        UPDATE destination_memberships
                        SET activation_channel = ?, preferred_category = ?, payload_hash = ?,
                            last_synced_at = ?
                        WHERE idempotency_key = ?
                    """,
                    (
                        payload["activation_channel"],
                        payload["preferred_category"],
                        payload_hash,
                        CAMPAIGN_DATE,
                        key,
                    ),
                )
                action, reason = "updated", "payload_changed"

        destination.execute(
            """
                INSERT INTO sync_events (run_id, idempotency_key, member_id, action, reason)
                VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, key, record.get("member_id"), action, reason),
        )
        counts[action] += 1
    destination.commit()
    actions = ("created", "updated", "unchanged", "suppressed", "rejected")
    return {
        "run_id": run_id,
        "attempted": len(records),
        **{action: counts[action] for action in actions},
    }


def run_activation_mock(*, reset: bool = True) -> dict:
    ensure_directories()
    records = build_activation_records()
    with closing(sqlite3.connect(ACTIVATION_DATABASE_PATH)) as destination:
        initialize_destination(destination, reset=reset)
        first_sync = sync_activation_records(records, destination, run_id="initial-sync")
        replay = sync_activation_records(records, destination, run_id="idempotent-replay")
        destination_active_count = destination.execute(
            "SELECT COUNT(*) FROM destination_memberships"
        ).fetchone()[0]
        duplicate_keys = destination.execute(
            """
                SELECT COUNT(*)
                FROM (
                    SELECT idempotency_key
                    FROM destination_memberships
                    GROUP BY idempotency_key
                    HAVING COUNT(*) > 1
                )
            """
        ).fetchone()[0]
        destination_control_count = destination.execute(
            "SELECT COUNT(*) FROM destination_memberships WHERE variant = 'control'"
        ).fetchone()[0]

    with closing(sqlite3.connect(DATABASE_PATH)) as warehouse:
        eligible_count = warehouse.execute(
            "SELECT COUNT(*) FROM mart_campaign_eligible_audience"
        ).fetchone()[0]
        control_count = warehouse.execute(
            "SELECT COUNT(*) FROM raw_experiment_assignments WHERE variant = 'control'"
        ).fetchone()[0]

    reconciliation = {
        "eligible_source_count": eligible_count,
        "control_excluded_count": control_count,
        "treatment_source_count": len(records),
        "destination_active_count": destination_active_count,
        "source_destination_delta": len(records) - destination_active_count,
        "duplicate_idempotency_keys": duplicate_keys,
        "destination_control_count": destination_control_count,
    }
    checks = [
        {
            "name": "treatment_source_matches_destination",
            "status": "PASS" if reconciliation["source_destination_delta"] == 0 else "FAIL",
        },
        {
            "name": "control_never_activated",
            "status": "PASS" if destination_control_count == 0 else "FAIL",
        },
        {
            "name": "idempotent_replay_creates_no_duplicates",
            "status": "PASS"
            if replay["created"] == 0
            and replay["unchanged"] == len(records)
            and duplicate_keys == 0
            else "FAIL",
        },
    ]
    report = {
        "destination": "local_activation_mock",
        "first_sync": first_sync,
        "idempotent_replay": replay,
        "reconciliation": reconciliation,
        "checks": checks,
        "sample_payloads": [_destination_payload(record) for record in records[:5]],
    }
    (REPORTS_DIR / "activation_reconciliation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
