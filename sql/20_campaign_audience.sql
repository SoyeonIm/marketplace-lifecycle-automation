DROP TABLE IF EXISTS mart_campaign_eligible_audience;

CREATE TABLE mart_campaign_eligible_audience AS
SELECT
    member_id,
    region,
    CASE
        WHEN preferred_channel = 'email' AND email_consent = 1 THEN 'email'
        WHEN preferred_channel = 'push' AND push_consent = 1 THEN 'push'
        WHEN email_consent = 1 THEN 'email'
        ELSE 'push'
    END AS activation_channel,
    preferred_category,
    historical_listing_count,
    historical_sales_count,
    historical_gmv,
    last_listing_at,
    last_activity_at,
    recent_event_count,
    recent_watchlist_count,
    recent_purchase_count,
    marketing_contacts_7d,
    'seller_reactivation_2026_08' AS campaign_id,
    '2026-08-01 09:00:00' AS audience_created_at
FROM mart_member_360
WHERE is_eligible = 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_eligible_member
    ON mart_campaign_eligible_audience(member_id);

