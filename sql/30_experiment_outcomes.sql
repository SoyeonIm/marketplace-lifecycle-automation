DROP TABLE IF EXISTS mart_experiment_member_outcomes;

CREATE TABLE mart_experiment_member_outcomes AS
WITH post_campaign_listings AS (
    SELECT
        member_id,
        COUNT(*) AS listing_count_14d,
        SUM(CASE WHEN sold_at IS NOT NULL THEN 1 ELSE 0 END) AS sold_listing_count_14d,
        ROUND(SUM(COALESCE(sale_value, 0)), 2) AS observed_gmv_14d
    FROM raw_listings
    WHERE created_at >= '2026-08-01 09:00:00'
        AND created_at <= '2026-08-15 23:59:59'
    GROUP BY member_id
),
campaign_response AS (
    SELECT
        member_id,
        SUM(CASE WHEN sent_at IS NOT NULL THEN 1 ELSE 0 END) AS message_sent_count,
        SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) AS message_open_count,
        SUM(CASE WHEN clicked_at IS NOT NULL THEN 1 ELSE 0 END) AS message_click_count,
        SUM(CASE WHEN unsubscribed_at IS NOT NULL THEN 1 ELSE 0 END) AS unsubscribe_count
    FROM raw_campaign_touches
    WHERE campaign_id = 'seller_reactivation_2026_08'
    GROUP BY member_id
)
SELECT
    a.member_id,
    a.region,
    a.activation_channel,
    a.preferred_category,
    x.experiment_id,
    x.variant,
    x.assigned_at,
    CASE WHEN COALESCE(p.listing_count_14d, 0) >= 1 THEN 1 ELSE 0 END AS converted_14d,
    COALESCE(p.listing_count_14d, 0) AS listing_count_14d,
    COALESCE(p.sold_listing_count_14d, 0) AS sold_listing_count_14d,
    COALESCE(p.observed_gmv_14d, 0) AS observed_gmv_14d,
    COALESCE(r.message_sent_count, 0) AS message_sent_count,
    COALESCE(r.message_open_count, 0) AS message_open_count,
    COALESCE(r.message_click_count, 0) AS message_click_count,
    COALESCE(r.unsubscribe_count, 0) AS unsubscribe_count
FROM mart_campaign_eligible_audience a
INNER JOIN raw_experiment_assignments x ON a.member_id = x.member_id
LEFT JOIN post_campaign_listings p ON a.member_id = p.member_id
LEFT JOIN campaign_response r ON a.member_id = r.member_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_outcome_member
    ON mart_experiment_member_outcomes(member_id);

DROP TABLE IF EXISTS mart_experiment_results;

CREATE TABLE mart_experiment_results AS
SELECT
    variant,
    COUNT(*) AS assigned_members,
    SUM(converted_14d) AS converted_members,
    ROUND(100.0 * SUM(converted_14d) / COUNT(*), 2) AS conversion_rate_pct,
    SUM(listing_count_14d) AS total_listings_14d,
    ROUND(SUM(observed_gmv_14d), 2) AS observed_gmv_14d,
    SUM(message_sent_count) AS message_sent_count,
    SUM(message_click_count) AS message_click_count,
    ROUND(
        100.0 * SUM(message_click_count) / NULLIF(SUM(message_sent_count), 0),
        2
    ) AS click_rate_pct,
    SUM(unsubscribe_count) AS unsubscribe_count,
    ROUND(
        100.0 * SUM(unsubscribe_count) / NULLIF(SUM(message_sent_count), 0),
        2
    ) AS unsubscribe_rate_pct
FROM mart_experiment_member_outcomes
GROUP BY variant;

