# Campaign operations and rollback runbook

## Release gates

1. Raw sources pass freshness and primary-key checks.
2. Eligible audience count is within an agreed change threshold from the approved preview.
3. Consent and suppression violations equal zero.
4. Experiment assignment reconciles one-to-one with the eligible audience.
5. Control exposure equals zero.
6. Destination dry run returns expected create/update counts.
7. Lifecycle, Data and Privacy owners approve the final brief.

## Monitoring

| Signal | Alert | Owner response |
|---|---|---|
| Audience size | More than 20% outside approved preview | Pause activation and inspect source/model changes |
| Destination rejects | Above 0.5% | Pause sync; inspect ID and schema contract |
| Duplicate sends | Any confirmed duplicate | Stop Canvas and preserve logs |
| Unsubscribe | Above 1% cumulative | Stop treatment and notify Lifecycle/Privacy |
| Control exposure | Any target-campaign touch | Invalidate experiment and investigate routing |
| Missing conversion events | Freshness breach over two hours | Delay decision; do not report partial results |

## Rollback

- Disable the audience sync and Braze entry step.
- Preserve assignment and exposure records; never re-randomize the same experiment silently.
- Add affected members to a temporary campaign hold if duplicate exposure is possible.
- Correct destination or model logic in staging and rerun all checks.
- Reconcile members created, updated, rejected and suppressed before resuming.
- Document the incident, customer impact, root cause and prevention action.

## Safe retry policy

Retries must be idempotent on `experiment_id + member_id + campaign_id`. A retry may update an
existing audience membership but must not generate a second assignment or campaign touch.

