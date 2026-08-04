select member_id
from {{ ref('mart_experiment_member_outcomes') }}
where variant in ('generic', 'personalized') and message_sent_count <> 1

