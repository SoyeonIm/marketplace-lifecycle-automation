from __future__ import annotations

import csv
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from src.config import (
    ANALYSIS_END_AT,
    CAMPAIGN_AT,
    CAMPAIGN_ID,
    CATEGORIES,
    EXPERIMENT_ID,
    LAPSED_CUTOFF,
    RAW_DIR,
    REGIONS,
    ensure_directories,
)


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _timestamp(value: datetime | None) -> str:
    return value.strftime(TIMESTAMP_FORMAT) if value else ""


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _random_datetime(rng: random.Random, start: datetime, end: datetime) -> datetime:
    seconds = max(0, int((end - start).total_seconds()))
    return start + timedelta(seconds=rng.randint(0, seconds))


def _choose_channel(member: dict) -> str:
    preferred = member["preferred_channel"]
    if preferred == "email" and member["email_consent"] == 1:
        return "email"
    if preferred == "push" and member["push_consent"] == 1:
        return "push"
    return "email" if member["email_consent"] == 1 else "push"


def generate_data(member_count: int = 12_000, seed: int = 42) -> dict:
    """Generate deterministic synthetic data with a known positive treatment effect.

    The data is entirely fictional. Eligibility is calculated from pre-campaign facts,
    then outcomes are generated after random assignment so the analysis can recover
    an incremental effect without leaking post-treatment information.
    """

    ensure_directories()
    rng = random.Random(seed)
    join_start = datetime(2023, 1, 1)
    pre_period_start = CAMPAIGN_AT - timedelta(days=180)
    lapse_cutoff_dt = datetime.strptime(LAPSED_CUTOFF, TIMESTAMP_FORMAT)

    members: list[dict] = []
    events: list[dict] = []
    listings: list[dict] = []
    campaign_touches: list[dict] = []
    consent_history: list[dict] = []
    exclusions: list[dict] = []
    assignments: list[dict] = []

    event_counter = 1
    listing_counter = 1
    touch_counter = 1
    consent_counter = 1

    member_listing_dates: dict[str, list[datetime]] = defaultdict(list)
    member_recent_activity: dict[str, bool] = defaultdict(bool)
    member_recent_categories: dict[str, list[str]] = defaultdict(list)
    member_recent_event_names: dict[str, set[str]] = defaultdict(set)
    member_contact_count_7d: dict[str, int] = defaultdict(int)
    member_has_active_exclusion: dict[str, bool] = defaultdict(bool)

    for index in range(1, member_count + 1):
        member_id = f"M{index:06d}"
        joined_at = _random_datetime(rng, join_start, CAMPAIGN_AT - timedelta(days=10))
        email_consent = int(rng.random() < 0.84)
        push_consent = int(rng.random() < 0.64)
        if not email_consent and not push_consent and rng.random() < 0.55:
            email_consent = 1
        preferred_channel = rng.choice(["email", "email", "push"])
        member = {
            "member_id": member_id,
            "joined_at": _timestamp(joined_at),
            "region": rng.choices(REGIONS, weights=[34, 14, 13, 11, 7, 21], k=1)[0],
            "preferred_channel": preferred_channel,
            "email_consent": email_consent,
            "push_consent": push_consent,
            "is_suppressed": int(rng.random() < 0.018),
        }
        members.append(member)

        for channel, consent in (("email", email_consent), ("push", push_consent)):
            consent_history.append(
                {
                    "consent_id": f"CN{consent_counter:07d}",
                    "member_id": member_id,
                    "channel": channel,
                    "status": "subscribed" if consent else "unsubscribed",
                    "effective_at": _timestamp(
                        _random_datetime(rng, joined_at, CAMPAIGN_AT - timedelta(days=1))
                    ),
                    "source": rng.choice(["registration", "preference_centre", "app_settings"]),
                }
            )
            consent_counter += 1

        is_historical_seller = rng.random() < 0.63
        if is_historical_seller:
            listing_count = rng.choices([1, 2, 3, 4, 5], weights=[34, 29, 19, 11, 7], k=1)[0]
            last_listing_days_ago = rng.randint(15, 230)
            last_listing_at = CAMPAIGN_AT - timedelta(
                days=last_listing_days_ago, hours=rng.randint(1, 20)
            )
            listing_dates = [last_listing_at]
            for _ in range(listing_count - 1):
                older_start = max(joined_at, pre_period_start - timedelta(days=365))
                older_end = last_listing_at - timedelta(days=1)
                if older_start < older_end:
                    listing_dates.append(_random_datetime(rng, older_start, older_end))
            for created_at in sorted(listing_dates):
                category = rng.choice(CATEGORIES)
                sold = rng.random() < 0.58
                sold_at = created_at + timedelta(days=rng.randint(1, 18)) if sold else None
                sale_value = round(rng.lognormvariate(4.25, 0.65), 2) if sold else 0.0
                listings.append(
                    {
                        "listing_id": f"L{listing_counter:07d}",
                        "member_id": member_id,
                        "category": category,
                        "created_at": _timestamp(created_at),
                        "sold_at": _timestamp(sold_at),
                        "sale_value": f"{sale_value:.2f}",
                    }
                )
                member_listing_dates[member_id].append(created_at)
                listing_counter += 1

        event_count = rng.randint(4, 12)
        force_recent = rng.random() < 0.73
        event_times = [
            _random_datetime(rng, max(joined_at, pre_period_start), CAMPAIGN_AT - timedelta(minutes=1))
            for _ in range(event_count)
        ]
        if force_recent:
            recent_start = max(joined_at, CAMPAIGN_AT - timedelta(days=29))
            event_times[0] = _random_datetime(
                rng, recent_start, CAMPAIGN_AT - timedelta(minutes=1)
            )

        for event_ts in sorted(event_times):
            event_name = rng.choices(
                [
                    "session_started",
                    "search_performed",
                    "item_viewed",
                    "watchlist_added",
                    "purchase_completed",
                    "listing_started",
                ],
                weights=[18, 19, 32, 13, 9, 9],
                k=1,
            )[0]
            category = rng.choice(CATEGORIES) if event_name != "session_started" else ""
            events.append(
                {
                    "event_id": f"E{event_counter:08d}",
                    "member_id": member_id,
                    "anonymous_id": f"A{index:06d}-{rng.randint(1, 3)}",
                    "event_name": event_name,
                    "event_ts": _timestamp(event_ts),
                    "category": category,
                    "platform": rng.choices(["web", "ios", "android"], weights=[48, 31, 21], k=1)[0],
                    "source": "product_tracking",
                }
            )
            event_counter += 1
            if event_ts >= CAMPAIGN_AT - timedelta(days=30):
                member_recent_activity[member_id] = True
                member_recent_event_names[member_id].add(event_name)
                if category:
                    member_recent_categories[member_id].append(category)

        historical_touch_count = rng.choices([0, 1, 2, 3], weights=[42, 34, 17, 7], k=1)[0]
        for sequence in range(historical_touch_count):
            sent_at = _random_datetime(
                rng, CAMPAIGN_AT - timedelta(days=30), CAMPAIGN_AT - timedelta(hours=2)
            )
            channel = _choose_channel(member) if email_consent or push_consent else "email"
            opened = rng.random() < (0.46 if channel == "email" else 0.31)
            clicked = opened and rng.random() < 0.18
            campaign_touches.append(
                {
                    "touch_id": f"T{touch_counter:08d}",
                    "member_id": member_id,
                    "campaign_id": f"historical_campaign_{sequence + 1}",
                    "variant": "historical",
                    "channel": channel,
                    "sent_at": _timestamp(sent_at),
                    "opened_at": _timestamp(sent_at + timedelta(hours=rng.randint(1, 24))) if opened else "",
                    "clicked_at": _timestamp(sent_at + timedelta(hours=rng.randint(1, 36))) if clicked else "",
                    "unsubscribed_at": "",
                }
            )
            if sent_at >= CAMPAIGN_AT - timedelta(days=7):
                member_contact_count_7d[member_id] += 1
            touch_counter += 1

        if rng.random() < 0.055:
            exclusions.append(
                {
                    "member_id": member_id,
                    "exclusion_reason": rng.choice(
                        ["high_priority_journey", "customer_support_hold", "experiment_holdout"]
                    ),
                    "start_at": _timestamp(CAMPAIGN_AT - timedelta(days=rng.randint(1, 10))),
                    "end_at": _timestamp(CAMPAIGN_AT + timedelta(days=rng.randint(2, 20))),
                }
            )
            member_has_active_exclusion[member_id] = True

    member_map = {row["member_id"]: row for row in members}
    eligible_members: list[str] = []
    for member_id, member in member_map.items():
        listing_dates = member_listing_dates.get(member_id, [])
        has_seller_history = bool(listing_dates)
        is_lapsed = has_seller_history and max(listing_dates) <= lapse_cutoff_dt
        has_consent = member["email_consent"] == 1 or member["push_consent"] == 1
        if (
            has_seller_history
            and is_lapsed
            and member_recent_activity[member_id]
            and has_consent
            and member["is_suppressed"] == 0
            and member_contact_count_7d[member_id] < 2
            and not member_has_active_exclusion[member_id]
        ):
            eligible_members.append(member_id)

    rng.shuffle(eligible_members)
    variants = ["control", "generic", "personalized"]
    assigned_variants: dict[str, str] = {}
    for position, member_id in enumerate(eligible_members):
        variant = variants[position % len(variants)]
        assigned_variants[member_id] = variant
        assignments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "member_id": member_id,
                "variant": variant,
                "assigned_at": _timestamp(CAMPAIGN_AT - timedelta(hours=1)),
            }
        )

    for member_id in eligible_members:
        member = member_map[member_id]
        variant = assigned_variants[member_id]
        event_signals = member_recent_event_names[member_id]
        historical_count = len(member_listing_dates[member_id])
        baseline_probability = 0.058
        baseline_probability += 0.014 if "watchlist_added" in event_signals else 0.0
        baseline_probability += 0.016 if "purchase_completed" in event_signals else 0.0
        baseline_probability += min(historical_count, 3) * 0.004
        treatment_effect = {"control": 0.0, "generic": 0.024, "personalized": 0.048}[variant]
        converted = rng.random() < baseline_probability + treatment_effect

        if variant != "control":
            channel = _choose_channel(member)
            sent_at = CAMPAIGN_AT + timedelta(minutes=rng.randint(0, 45))
            open_probability = 0.49 if variant == "generic" else 0.57
            click_probability = 0.085 if variant == "generic" else 0.132
            opened = rng.random() < open_probability
            clicked = rng.random() < click_probability
            unsubscribed = channel == "email" and rng.random() < (
                0.0065 if variant == "generic" else 0.004
            )
            unsubscribe_at = sent_at + timedelta(hours=rng.randint(1, 48)) if unsubscribed else None
            campaign_touches.append(
                {
                    "touch_id": f"T{touch_counter:08d}",
                    "member_id": member_id,
                    "campaign_id": CAMPAIGN_ID,
                    "variant": variant,
                    "channel": channel,
                    "sent_at": _timestamp(sent_at),
                    "opened_at": _timestamp(sent_at + timedelta(hours=rng.randint(1, 20))) if opened else "",
                    "clicked_at": _timestamp(sent_at + timedelta(hours=rng.randint(1, 30))) if clicked else "",
                    "unsubscribed_at": _timestamp(unsubscribe_at),
                }
            )
            touch_counter += 1
            if unsubscribed:
                consent_history.append(
                    {
                        "consent_id": f"CN{consent_counter:07d}",
                        "member_id": member_id,
                        "channel": "email",
                        "status": "unsubscribed",
                        "effective_at": _timestamp(unsubscribe_at),
                        "source": "campaign_unsubscribe",
                    }
                )
                consent_counter += 1

        if converted:
            created_at = CAMPAIGN_AT + timedelta(
                days=rng.randint(1, 13), hours=rng.randint(1, 20), minutes=rng.randint(0, 59)
            )
            recent_categories = member_recent_categories[member_id]
            category = (
                rng.choice(recent_categories)
                if variant == "personalized" and recent_categories
                else rng.choice(CATEGORIES)
            )
            sold = rng.random() < 0.51
            sold_at = created_at + timedelta(days=rng.randint(1, 12)) if sold else None
            if sold_at and sold_at > ANALYSIS_END_AT + timedelta(days=15):
                sold_at = None
                sold = False
            sale_value = round(rng.lognormvariate(4.35, 0.62), 2) if sold else 0.0
            listings.append(
                {
                    "listing_id": f"L{listing_counter:07d}",
                    "member_id": member_id,
                    "category": category,
                    "created_at": _timestamp(created_at),
                    "sold_at": _timestamp(sold_at),
                    "sale_value": f"{sale_value:.2f}",
                }
            )
            listings_created_id = f"L{listing_counter:07d}"
            listing_counter += 1
            events.append(
                {
                    "event_id": f"E{event_counter:08d}",
                    "member_id": member_id,
                    "anonymous_id": f"A{int(member_id[1:]):06d}-1",
                    "event_name": "listing_created",
                    "event_ts": _timestamp(created_at),
                    "category": category,
                    "platform": rng.choice(["web", "ios", "android"]),
                    "source": listings_created_id,
                }
            )
            event_counter += 1

    _write_csv(
        RAW_DIR / "members.csv",
        [
            "member_id",
            "joined_at",
            "region",
            "preferred_channel",
            "email_consent",
            "push_consent",
            "is_suppressed",
        ],
        members,
    )
    _write_csv(
        RAW_DIR / "events.csv",
        [
            "event_id",
            "member_id",
            "anonymous_id",
            "event_name",
            "event_ts",
            "category",
            "platform",
            "source",
        ],
        events,
    )
    _write_csv(
        RAW_DIR / "listings.csv",
        ["listing_id", "member_id", "category", "created_at", "sold_at", "sale_value"],
        listings,
    )
    _write_csv(
        RAW_DIR / "campaign_touches.csv",
        [
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
        campaign_touches,
    )
    _write_csv(
        RAW_DIR / "consent_history.csv",
        ["consent_id", "member_id", "channel", "status", "effective_at", "source"],
        consent_history,
    )
    _write_csv(
        RAW_DIR / "campaign_exclusions.csv",
        ["member_id", "exclusion_reason", "start_at", "end_at"],
        exclusions,
    )
    _write_csv(
        RAW_DIR / "experiment_assignments.csv",
        ["experiment_id", "member_id", "variant", "assigned_at"],
        assignments,
    )

    return {
        "seed": seed,
        "members": len(members),
        "events": len(events),
        "listings": len(listings),
        "campaign_touches": len(campaign_touches),
        "eligible_and_randomized": len(assignments),
        "privacy": "100% synthetic; no real member data used",
    }
