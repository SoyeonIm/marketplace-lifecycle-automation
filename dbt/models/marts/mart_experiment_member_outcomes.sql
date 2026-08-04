{% set campaign_at = "to_timestamp_ntz('" ~ var('campaign_at') ~ "')" %}
{% set analysis_end_at = "to_timestamp_ntz('" ~ var('analysis_end_at') ~ "')" %}

with post_campaign_listings as (
    select
        member_id,
        count(*) as listing_count_14d,
        count_if(sold_at is not null) as sold_listing_count_14d,
        sum(coalesce(sale_value, 0)) as observed_gmv_14d
    from {{ ref('stg_listings') }}
    where created_at >= {{ campaign_at }} and created_at <= {{ analysis_end_at }}
    group by member_id
),
campaign_response as (
    select
        member_id,
        count(*) as message_sent_count,
        count_if(opened_at is not null) as message_open_count,
        count_if(clicked_at is not null) as message_click_count,
        count_if(unsubscribed_at is not null) as unsubscribe_count
    from {{ ref('stg_campaign_touches') }}
    where campaign_id = '{{ var("campaign_id") }}'
    group by member_id
)
select
    a.member_id,
    a.region,
    a.activation_channel,
    a.preferred_category,
    x.experiment_id,
    x.variant,
    x.assigned_at,
    coalesce(p.listing_count_14d, 0) >= 1 as converted_14d,
    coalesce(p.listing_count_14d, 0) as listing_count_14d,
    coalesce(p.sold_listing_count_14d, 0) as sold_listing_count_14d,
    coalesce(p.observed_gmv_14d, 0) as observed_gmv_14d,
    coalesce(r.message_sent_count, 0) as message_sent_count,
    coalesce(r.message_open_count, 0) as message_open_count,
    coalesce(r.message_click_count, 0) as message_click_count,
    coalesce(r.unsubscribe_count, 0) as unsubscribe_count
from {{ ref('mart_campaign_eligible_audience') }} a
inner join {{ ref('stg_experiment_assignments') }} x using (member_id)
left join post_campaign_listings p using (member_id)
left join campaign_response r using (member_id)

