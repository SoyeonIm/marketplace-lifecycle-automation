select
    variant,
    count(*) as assigned_members,
    count_if(converted_14d) as converted_members,
    round(100 * count_if(converted_14d) / count(*), 2) as conversion_rate_pct,
    sum(listing_count_14d) as total_listings_14d,
    round(sum(observed_gmv_14d), 2) as observed_gmv_14d,
    sum(message_sent_count) as message_sent_count,
    sum(message_click_count) as message_click_count,
    round(100 * sum(message_click_count) / nullif(sum(message_sent_count), 0), 2)
        as click_rate_pct,
    sum(unsubscribe_count) as unsubscribe_count,
    round(100 * sum(unsubscribe_count) / nullif(sum(message_sent_count), 0), 2)
        as unsubscribe_rate_pct
from {{ ref('mart_experiment_member_outcomes') }}
group by variant
