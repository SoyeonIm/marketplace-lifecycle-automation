select member_id
from {{ ref('mart_experiment_member_outcomes') }}
where variant = 'control' and message_sent_count <> 0

