select
    cast(event_id as varchar) as event_id,
    cast(member_id as varchar) as member_id,
    cast(anonymous_id as varchar) as anonymous_id,
    cast(event_name as varchar) as event_name,
    cast(event_ts as timestamp_ntz) as event_ts,
    nullif(cast(category as varchar), '') as category,
    cast(platform as varchar) as platform,
    cast(source as varchar) as source
from {{ source('marketplace_raw', 'events') }}

