select
    cast(touch_id as varchar) as touch_id,
    cast(member_id as varchar) as member_id,
    cast(campaign_id as varchar) as campaign_id,
    cast(variant as varchar) as variant,
    cast(channel as varchar) as channel,
    cast(sent_at as timestamp_ntz) as sent_at,
    try_to_timestamp_ntz(nullif(cast(opened_at as varchar), '')) as opened_at,
    try_to_timestamp_ntz(nullif(cast(clicked_at as varchar), '')) as clicked_at,
    try_to_timestamp_ntz(nullif(cast(unsubscribed_at as varchar), '')) as unsubscribed_at
from {{ source('marketplace_raw', 'campaign_touches') }}
