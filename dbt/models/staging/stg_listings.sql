select
    cast(listing_id as varchar) as listing_id,
    cast(member_id as varchar) as member_id,
    cast(category as varchar) as category,
    cast(created_at as timestamp_ntz) as created_at,
    try_to_timestamp_ntz(nullif(cast(sold_at as varchar), '')) as sold_at,
    cast(sale_value as number(18, 2)) as sale_value
from {{ source('marketplace_raw', 'listings') }}
