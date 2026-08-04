select
    member_id,
    region,
    case
        when preferred_channel = 'email' and email_consent then 'email'
        when preferred_channel = 'push' and push_consent then 'push'
        when email_consent then 'email'
        else 'push'
    end as activation_channel,
    preferred_category,
    historical_listing_count,
    historical_sales_count,
    last_listing_at,
    last_activity_at,
    recent_event_count,
    recent_watchlist_count,
    recent_purchase_count,
    marketing_contacts_7d,
    '{{ var("campaign_id") }}' as campaign_id,
    to_timestamp_ntz('{{ var("campaign_at") }}') as audience_created_at
from {{ ref('int_member_360') }}
where is_eligible

