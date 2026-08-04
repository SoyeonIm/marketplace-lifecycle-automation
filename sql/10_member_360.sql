DROP TABLE IF EXISTS mart_member_360;

CREATE TABLE mart_member_360 AS
WITH listing_features AS (
    SELECT
        member_id,
        COUNT(*) AS historical_listing_count,
        MAX(created_at) AS last_listing_at,
        SUM(CASE WHEN sold_at IS NOT NULL THEN 1 ELSE 0 END) AS historical_sales_count,
        ROUND(SUM(COALESCE(sale_value, 0)), 2) AS historical_gmv
    FROM raw_listings
    WHERE created_at < '2026-08-01 09:00:00'
    GROUP BY member_id
),
event_features AS (
    SELECT
        member_id,
        MAX(CASE WHEN event_ts < '2026-08-01 09:00:00' THEN event_ts END) AS last_activity_at,
        SUM(
            CASE
                WHEN event_ts >= '2026-07-02 09:00:00'
                    AND event_ts < '2026-08-01 09:00:00'
                THEN 1 ELSE 0
            END
        ) AS recent_event_count,
        SUM(
            CASE
                WHEN event_name = 'watchlist_added'
                    AND event_ts >= '2026-07-02 09:00:00'
                    AND event_ts < '2026-08-01 09:00:00'
                THEN 1 ELSE 0
            END
        ) AS recent_watchlist_count,
        SUM(
            CASE
                WHEN event_name = 'purchase_completed'
                    AND event_ts >= '2026-07-02 09:00:00'
                    AND event_ts < '2026-08-01 09:00:00'
                THEN 1 ELSE 0
            END
        ) AS recent_purchase_count
    FROM raw_events
    GROUP BY member_id
),
contact_features AS (
    SELECT
        member_id,
        SUM(
            CASE
                WHEN sent_at >= '2026-07-25 09:00:00'
                    AND sent_at < '2026-08-01 09:00:00'
                THEN 1 ELSE 0
            END
        ) AS marketing_contacts_7d
    FROM raw_campaign_touches
    GROUP BY member_id
),
exclusion_features AS (
    SELECT
        member_id,
        1 AS has_active_campaign_exclusion
    FROM raw_campaign_exclusions
    WHERE start_at <= '2026-08-01 09:00:00'
        AND end_at >= '2026-08-01 09:00:00'
    GROUP BY member_id
)
SELECT
    m.member_id,
    m.joined_at,
    m.region,
    m.preferred_channel,
    m.email_consent,
    m.push_consent,
    m.is_suppressed,
    COALESCE(l.historical_listing_count, 0) AS historical_listing_count,
    l.last_listing_at,
    COALESCE(l.historical_sales_count, 0) AS historical_sales_count,
    COALESCE(l.historical_gmv, 0) AS historical_gmv,
    e.last_activity_at,
    COALESCE(e.recent_event_count, 0) AS recent_event_count,
    COALESCE(e.recent_watchlist_count, 0) AS recent_watchlist_count,
    COALESCE(e.recent_purchase_count, 0) AS recent_purchase_count,
    COALESCE(c.marketing_contacts_7d, 0) AS marketing_contacts_7d,
    COALESCE(x.has_active_campaign_exclusion, 0) AS has_active_campaign_exclusion,
    (
        SELECT re.category
        FROM raw_events re
        WHERE re.member_id = m.member_id
            AND re.category IS NOT NULL
            AND re.category <> ''
            AND re.event_ts < '2026-08-01 09:00:00'
        ORDER BY re.event_ts DESC
        LIMIT 1
    ) AS preferred_category,
    CASE WHEN COALESCE(l.historical_listing_count, 0) >= 1 THEN 1 ELSE 0 END AS has_seller_history,
    CASE WHEN l.last_listing_at <= '2026-05-03 09:00:00' THEN 1 ELSE 0 END AS is_lapsed_seller,
    CASE WHEN COALESCE(e.recent_event_count, 0) >= 1 THEN 1 ELSE 0 END AS has_recent_activity,
    CASE WHEN m.email_consent = 1 OR m.push_consent = 1 THEN 1 ELSE 0 END AS has_marketing_consent,
    CASE WHEN COALESCE(c.marketing_contacts_7d, 0) < 2 THEN 1 ELSE 0 END AS within_contact_cap,
    CASE WHEN COALESCE(x.has_active_campaign_exclusion, 0) = 0 THEN 1 ELSE 0 END AS has_no_campaign_conflict,
    CASE
        WHEN COALESCE(l.historical_listing_count, 0) < 1 THEN 'no_seller_history'
        WHEN l.last_listing_at > '2026-05-03 09:00:00' THEN 'not_lapsed_90d'
        WHEN COALESCE(e.recent_event_count, 0) < 1 THEN 'no_recent_activity_30d'
        WHEN NOT (m.email_consent = 1 OR m.push_consent = 1) THEN 'no_marketing_consent'
        WHEN m.is_suppressed = 1 THEN 'suppressed'
        WHEN COALESCE(c.marketing_contacts_7d, 0) >= 2 THEN 'contact_cap_reached'
        WHEN COALESCE(x.has_active_campaign_exclusion, 0) = 1 THEN 'campaign_conflict'
        ELSE 'eligible'
    END AS eligibility_status,
    CASE
        WHEN COALESCE(l.historical_listing_count, 0) >= 1
            AND l.last_listing_at <= '2026-05-03 09:00:00'
            AND COALESCE(e.recent_event_count, 0) >= 1
            AND (m.email_consent = 1 OR m.push_consent = 1)
            AND m.is_suppressed = 0
            AND COALESCE(c.marketing_contacts_7d, 0) < 2
            AND COALESCE(x.has_active_campaign_exclusion, 0) = 0
        THEN 1 ELSE 0
    END AS is_eligible
FROM raw_members m
LEFT JOIN listing_features l ON m.member_id = l.member_id
LEFT JOIN event_features e ON m.member_id = e.member_id
LEFT JOIN contact_features c ON m.member_id = c.member_id
LEFT JOIN exclusion_features x ON m.member_id = x.member_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_member_360_member ON mart_member_360(member_id);

