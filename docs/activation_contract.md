# Warehouse-to-activation contract

## Audience grain and key

- Grain: one current membership row per `campaign_id + member_id`
- Primary destination key: pseudonymous `member_id`
- Update behaviour: upsert membership; do not create a new customer profile from this table alone

## Fields

| Field | Type | Required | Destination use |
|---|---|---:|---|
| `member_id` | string | Yes | Hightouch/Braze external ID |
| `campaign_id` | string | Yes | Audit and destination namespace |
| `activation_channel` | enum | Yes | Route to email or push branch |
| `preferred_category` | string | No | Non-sensitive message personalization |
| `historical_listing_count` | integer | Yes | QA and audience insight, not copy |
| `marketing_contacts_7d` | integer | Yes | Final frequency-cap check |
| `audience_created_at` | timestamp | Yes | Freshness and replay protection |

## Destination validation

- Reject null or unknown `member_id`.
- Reject channel values outside `email` and `push`.
- Suppress rather than default when channel consent no longer exists.
- Do not send `historical_gmv` to the messaging platform; it is unnecessary for activation.
- Log create, update, reject and suppress counts for reconciliation.
- Use environment-specific destination namespaces to prevent staging sends to production members.

## Hightouch implementation note

Use the warehouse model as the source of truth, map `member_id` to the existing Braze external ID,
and configure a pre-send consent/suppression check. A sync success only proves delivery to the
destination API; it does not prove that the campaign message was sent or converted.

