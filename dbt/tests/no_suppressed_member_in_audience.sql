select a.member_id
from {{ ref('mart_campaign_eligible_audience') }} a
join {{ ref('stg_members') }} m using (member_id)
where m.is_suppressed

