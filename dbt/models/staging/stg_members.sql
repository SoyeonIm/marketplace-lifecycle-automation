select
    cast(member_id as varchar) as member_id,
    cast(joined_at as timestamp_ntz) as joined_at,
    cast(region as varchar) as region,
    cast(preferred_channel as varchar) as preferred_channel,
    cast(email_consent as boolean) as email_consent,
    cast(push_consent as boolean) as push_consent,
    cast(is_suppressed as boolean) as is_suppressed
from {{ source('marketplace_raw', 'members') }}

