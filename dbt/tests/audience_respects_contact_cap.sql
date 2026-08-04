select member_id
from {{ ref('mart_campaign_eligible_audience') }}
where marketing_contacts_7d >= 2

