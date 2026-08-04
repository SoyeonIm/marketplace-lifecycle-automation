{% set campaign_at = "to_timestamp_ntz('" ~ var('campaign_at') ~ "')" %}
{% set recent_activity_start = "to_timestamp_ntz('" ~ var('recent_activity_start') ~ "')" %}
{% set contact_cap_start = "to_timestamp_ntz('" ~ var('contact_cap_start') ~ "')" %}
{% set lapsed_cutoff = "to_timestamp_ntz('" ~ var('lapsed_cutoff') ~ "')" %}

with members as (
    select * from {{ ref('stg_members') }}
),
listings as (
    select
        member_id,
        count(*) as historical_listing_count,
        max(created_at) as last_listing_at,
        count_if(sold_at is not null) as historical_sales_count,
        sum(coalesce(sale_value, 0)) as historical_gmv
    from {{ ref('stg_listings') }}
    where created_at < {{ campaign_at }}
    group by member_id
),
events as (
    select
        member_id,
        max(event_ts) as last_activity_at,
        count_if(event_ts >= {{ recent_activity_start }} and event_ts < {{ campaign_at }})
            as recent_event_count,
        count_if(event_name = 'watchlist_added' and event_ts >= {{ recent_activity_start }}
            and event_ts < {{ campaign_at }}) as recent_watchlist_count,
        count_if(event_name = 'purchase_completed' and event_ts >= {{ recent_activity_start }}
            and event_ts < {{ campaign_at }}) as recent_purchase_count
    from {{ ref('stg_events') }}
    where event_ts < {{ campaign_at }}
    group by member_id
),
recent_category as (
    select member_id, category as preferred_category
    from {{ ref('stg_events') }}
    where event_ts < {{ campaign_at }} and category is not null
    qualify row_number() over (partition by member_id order by event_ts desc, event_id desc) = 1
),
contacts as (
    select
        member_id,
        count_if(sent_at >= {{ contact_cap_start }} and sent_at < {{ campaign_at }})
            as marketing_contacts_7d
    from {{ ref('stg_campaign_touches') }}
    group by member_id
),
exclusions as (
    select member_id, true as has_active_campaign_exclusion
    from {{ ref('stg_campaign_exclusions') }}
    where start_at <= {{ campaign_at }} and end_at >= {{ campaign_at }}
    group by member_id
)
select
    m.*,
    coalesce(l.historical_listing_count, 0) as historical_listing_count,
    l.last_listing_at,
    coalesce(l.historical_sales_count, 0) as historical_sales_count,
    coalesce(l.historical_gmv, 0) as historical_gmv,
    e.last_activity_at,
    coalesce(e.recent_event_count, 0) as recent_event_count,
    coalesce(e.recent_watchlist_count, 0) as recent_watchlist_count,
    coalesce(e.recent_purchase_count, 0) as recent_purchase_count,
    coalesce(c.marketing_contacts_7d, 0) as marketing_contacts_7d,
    coalesce(x.has_active_campaign_exclusion, false) as has_active_campaign_exclusion,
    r.preferred_category,
    coalesce(l.historical_listing_count, 0) >= 1 as has_seller_history,
    l.last_listing_at <= {{ lapsed_cutoff }} as is_lapsed_seller,
    coalesce(e.recent_event_count, 0) >= 1 as has_recent_activity,
    (m.email_consent or m.push_consent) as has_marketing_consent,
    coalesce(c.marketing_contacts_7d, 0) < 2 as within_contact_cap,
    not coalesce(x.has_active_campaign_exclusion, false) as has_no_campaign_conflict,
    (
        coalesce(l.historical_listing_count, 0) >= 1
        and l.last_listing_at <= {{ lapsed_cutoff }}
        and coalesce(e.recent_event_count, 0) >= 1
        and (m.email_consent or m.push_consent)
        and not m.is_suppressed
        and coalesce(c.marketing_contacts_7d, 0) < 2
        and not coalesce(x.has_active_campaign_exclusion, false)
    ) as is_eligible
from members m
left join listings l using (member_id)
left join events e using (member_id)
left join recent_category r using (member_id)
left join contacts c using (member_id)
left join exclusions x using (member_id)

