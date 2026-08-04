from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.config import DATABASE_PATH, REPORTS_DIR, ensure_directories


def _scalar(connection: sqlite3.Connection, sql: str) -> int | float:
    value = connection.execute(sql).fetchone()[0]
    return value if value is not None else 0


def run_quality_checks(write_report: bool = False) -> list[dict]:
    ensure_directories()
    connection = sqlite3.connect(DATABASE_PATH)
    checks: list[dict] = []

    def check(name: str, sql: str, expected: int | float = 0, description: str = "") -> None:
        actual = _scalar(connection, sql)
        status = "PASS" if actual == expected else "FAIL"
        checks.append(
            {
                "name": name,
                "status": status,
                "actual": actual,
                "expected": expected,
                "detail": description or f"Expected {expected}; observed {actual}",
            }
        )

    try:
        check(
            "member_primary_key_unique",
            "SELECT COUNT(*) - COUNT(DISTINCT member_id) FROM raw_members",
            description="Every member has one canonical record.",
        )
        check(
            "event_primary_key_unique",
            "SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM raw_events",
            description="Product event IDs are unique.",
        )
        check(
            "listing_primary_key_unique",
            "SELECT COUNT(*) - COUNT(DISTINCT listing_id) FROM raw_listings",
            description="Listing IDs are unique.",
        )
        check(
            "event_member_referential_integrity",
            """
                SELECT COUNT(*)
                FROM raw_events e
                LEFT JOIN raw_members m ON e.member_id = m.member_id
                WHERE m.member_id IS NULL
            """,
            description="All product events resolve to a known member.",
        )
        check(
            "anonymous_identity_maps_to_one_member",
            """
                SELECT COUNT(*)
                FROM (
                    SELECT anonymous_id
                    FROM raw_events
                    GROUP BY anonymous_id
                    HAVING COUNT(DISTINCT member_id) > 1
                )
            """,
            description="An anonymous browser or app identifier never resolves to multiple members.",
        )
        check(
            "accepted_event_names",
            """
                SELECT COUNT(*)
                FROM raw_events
                WHERE event_name NOT IN (
                    'session_started', 'search_performed', 'item_viewed',
                    'watchlist_added', 'purchase_completed', 'listing_started',
                    'listing_created'
                )
            """,
            description="The event stream conforms to the governed tracking plan.",
        )
        check(
            "events_not_before_member_join",
            """
                SELECT COUNT(*)
                FROM raw_events e
                JOIN raw_members m ON e.member_id = m.member_id
                WHERE e.event_ts < m.joined_at
            """,
            description="No known-member event predates the member record.",
        )
        check(
            "listing_member_referential_integrity",
            """
                SELECT COUNT(*)
                FROM raw_listings l
                LEFT JOIN raw_members m ON l.member_id = m.member_id
                WHERE m.member_id IS NULL
            """,
            description="All listings resolve to a known member.",
        )
        check(
            "listing_sale_after_creation",
            """
                SELECT COUNT(*)
                FROM raw_listings
                WHERE sold_at IS NOT NULL AND sold_at < created_at
            """,
            description="A sold timestamp cannot precede listing creation.",
        )
        check(
            "touch_member_referential_integrity",
            """
                SELECT COUNT(*)
                FROM raw_campaign_touches t
                LEFT JOIN raw_members m ON t.member_id = m.member_id
                WHERE m.member_id IS NULL
            """,
            description="All campaign touches resolve to a known member.",
        )
        check(
            "accepted_consent_statuses",
            """
                SELECT COUNT(*)
                FROM raw_consent_history
                WHERE status NOT IN ('subscribed', 'unsubscribed')
            """,
            description="Consent history uses governed status values.",
        )
        check(
            "campaign_date_consent_snapshot_reconciles",
            """
                WITH ranked AS (
                    SELECT
                        member_id,
                        channel,
                        status,
                        ROW_NUMBER() OVER (
                            PARTITION BY member_id, channel
                            ORDER BY effective_at DESC, consent_id DESC
                        ) AS row_number
                    FROM raw_consent_history
                    WHERE effective_at < '2026-08-01 09:00:00'
                )
                SELECT COUNT(*)
                FROM ranked c
                JOIN raw_members m ON c.member_id = m.member_id
                WHERE c.row_number = 1
                    AND (
                        (c.channel = 'email' AND (c.status = 'subscribed') <> m.email_consent)
                        OR (c.channel = 'push' AND (c.status = 'subscribed') <> m.push_consent)
                    )
            """,
            description="Campaign-date member consent flags reconcile to consent history.",
        )
        check(
            "audience_has_channel_consent",
            """
                SELECT COUNT(*)
                FROM mart_campaign_eligible_audience a
                JOIN raw_members m ON a.member_id = m.member_id
                WHERE (a.activation_channel = 'email' AND m.email_consent <> 1)
                    OR (a.activation_channel = 'push' AND m.push_consent <> 1)
            """,
            description="Every activated member has campaign-date consent for the selected channel.",
        )
        check(
            "audience_has_no_suppressed_members",
            """
                SELECT COUNT(*)
                FROM mart_campaign_eligible_audience a
                JOIN raw_members m ON a.member_id = m.member_id
                WHERE m.is_suppressed = 1
            """,
            description="Suppressed members never enter the activation audience.",
        )
        check(
            "audience_respects_contact_cap",
            """
                SELECT COUNT(*)
                FROM mart_campaign_eligible_audience a
                JOIN mart_member_360 m ON a.member_id = m.member_id
                WHERE m.marketing_contacts_7d >= 2
            """,
            description="Eligible members have received fewer than two marketing contacts in seven days.",
        )
        check(
            "audience_has_no_campaign_conflict",
            """
                SELECT COUNT(*)
                FROM mart_campaign_eligible_audience a
                JOIN mart_member_360 m ON a.member_id = m.member_id
                WHERE m.has_active_campaign_exclusion = 1
            """,
            description="High-priority journeys and holdouts are excluded.",
        )
        check(
            "audience_is_lapsed_and_recently_active",
            """
                SELECT COUNT(*)
                FROM mart_campaign_eligible_audience a
                JOIN mart_member_360 m ON a.member_id = m.member_id
                WHERE m.is_lapsed_seller <> 1 OR m.has_recent_activity <> 1
            """,
            description="Audience members are both 90-day lapsed sellers and recently active.",
        )
        check(
            "experiment_assignment_unique",
            """
                SELECT COUNT(*) - COUNT(DISTINCT member_id)
                FROM raw_experiment_assignments
            """,
            description="Each eligible member receives exactly one experiment assignment.",
        )
        check(
            "accepted_experiment_variants",
            """
                SELECT COUNT(*)
                FROM raw_experiment_assignments
                WHERE variant NOT IN ('control', 'generic', 'personalized')
            """,
            description="Assignments use only pre-registered experiment variants.",
        )
        check(
            "assignment_precedes_campaign",
            """
                SELECT COUNT(*)
                FROM raw_experiment_assignments
                WHERE assigned_at >= '2026-08-01 09:00:00'
            """,
            description="Randomization is completed before campaign exposure.",
        )
        check(
            "all_audience_members_randomized",
            """
                SELECT COUNT(*)
                FROM mart_campaign_eligible_audience a
                LEFT JOIN raw_experiment_assignments x ON a.member_id = x.member_id
                WHERE x.member_id IS NULL
            """,
            description="No eligible audience member is missing an assignment.",
        )
        check(
            "no_ineligible_member_randomized",
            """
                SELECT COUNT(*)
                FROM raw_experiment_assignments x
                LEFT JOIN mart_campaign_eligible_audience a ON x.member_id = a.member_id
                WHERE a.member_id IS NULL
            """,
            description="Assignments contain no member outside the governed audience.",
        )
        check(
            "control_receives_no_campaign_message",
            """
                SELECT COUNT(*)
                FROM mart_experiment_member_outcomes
                WHERE variant = 'control' AND message_sent_count <> 0
            """,
            description="The control group remains unexposed.",
        )
        check(
            "treatments_receive_one_campaign_message",
            """
                SELECT COUNT(*)
                FROM mart_experiment_member_outcomes
                WHERE variant IN ('generic', 'personalized') AND message_sent_count <> 1
            """,
            description="Every treatment member receives one initial campaign touch.",
        )
        check(
            "experiment_groups_balanced",
            """
                SELECT CASE WHEN MAX(n) - MIN(n) <= 1 THEN 0 ELSE 1 END
                FROM (
                    SELECT variant, COUNT(*) AS n
                    FROM raw_experiment_assignments
                    GROUP BY variant
                )
            """,
            description="Deterministic randomization keeps arm sizes within one member.",
        )
        check(
            "experiment_results_reconcile",
            """
                SELECT ABS(
                    (SELECT COUNT(*) FROM mart_campaign_eligible_audience)
                    - (SELECT SUM(assigned_members) FROM mart_experiment_results)
                )
            """,
            description="The aggregated experiment population reconciles to the governed audience.",
        )
    finally:
        connection.close()

    if write_report:
        output = REPORTS_DIR / "data_quality.json"
        output.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    return checks
