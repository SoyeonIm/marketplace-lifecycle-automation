# Data dictionary

## Raw entities

| Entity | Grain | Key fields | Notes |
|---|---|---|---|
| `raw_members` | One row per member at campaign time | `member_id` | Consent flags are a campaign-date snapshot |
| `raw_events` | One row per product event | `event_id` | Includes pseudonymous anonymous-to-member mapping |
| `raw_listings` | One row per listing | `listing_id` | Pre- and post-campaign records separated by timestamp |
| `raw_campaign_touches` | One row per attempted campaign touch | `touch_id` | Control members have no target-campaign record |
| `raw_consent_history` | One consent state change | `consent_id` | Channel-specific and effective-dated |
| `raw_campaign_exclusions` | One active exclusion interval | member/reason/start | Holds higher-priority journeys and experiment exclusions |
| `raw_experiment_assignments` | One assignment per eligible member | member/experiment | Assigned before exposure |

## Analytics marts

### `mart_member_360`

One row per member as of campaign launch. Contains only pre-treatment features used for eligibility,
randomization diagnostics and personalization.

Important fields:

- `historical_listing_count`: listings created before campaign launch
- `last_listing_at`: most recent pre-campaign listing
- `recent_event_count`: events in the preceding 30 days
- `marketing_contacts_7d`: prior marketing touches in seven days
- `eligibility_status`: first failed rule or `eligible`
- `is_eligible`: final reusable activation flag

### `mart_campaign_eligible_audience`

One row per member allowed to enter the experiment. Contains pseudonymous activation fields only.
No email address or raw message content is exposed.

### `mart_experiment_member_outcomes`

One row per assigned member. Contains assignment, treatment exposure, 14-day listing outcome and
guardrail measures. This is the intention-to-treat analysis grain.

### `mart_experiment_results`

One row per experiment arm. Used for reconciliation and reporting; statistical testing is performed
from the underlying counts rather than rounded percentages.

