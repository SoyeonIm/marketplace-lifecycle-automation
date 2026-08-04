select
    cast(member_id as varchar) as member_id,
    cast(exclusion_reason as varchar) as exclusion_reason,
    cast(start_at as timestamp_ntz) as start_at,
    cast(end_at as timestamp_ntz) as end_at
from {{ source('marketplace_raw', 'campaign_exclusions') }}

