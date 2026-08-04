select
    cast(experiment_id as varchar) as experiment_id,
    cast(member_id as varchar) as member_id,
    cast(variant as varchar) as variant,
    cast(assigned_at as timestamp_ntz) as assigned_at
from {{ source('marketplace_raw', 'experiment_assignments') }}

