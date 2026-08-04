# Privacy, anti-spam and audience-governance checklist

This is an operational checklist, not legal advice. Production rules require review by the company's
Privacy and Legal teams.

## Before activation

- [ ] Confirm the campaign purpose is compatible with the purpose for which data was collected.
- [ ] Confirm current channel consent from effective-dated history.
- [ ] Exclude global and channel-level suppression records.
- [ ] Exclude customer-support, safety and high-priority journey holds.
- [ ] Apply the cross-vertical contact-frequency policy.
- [ ] Limit the audience export to pseudonymous IDs and required personalization fields.
- [ ] Record model version, audience count, query run time and approval owner.
- [ ] Reconcile source count, activation count and destination count.

## Message requirements

- [ ] Identify the sender clearly.
- [ ] Include a clear, free and functioning unsubscribe mechanism.
- [ ] Keep the unsubscribe mechanism available for the required period.
- [ ] Do not obscure commercial intent.
- [ ] Avoid sensitive or surprising personalization.

## After send

- [ ] Process unsubscribe requests within the required service level.
- [ ] Propagate suppression to all relevant destinations.
- [ ] Monitor bounce, complaint and unsubscribe rates.
- [ ] Confirm control members received no target-campaign touch.
- [ ] Investigate source-to-destination count differences.
- [ ] Retain only the data required for measurement and audit.

## Encoded in this project

The executable checks channel consent, suppression, contact cap, campaign conflict, assignment timing,
control contamination, destination exposure count, referential integrity and consent-snapshot
reconciliation. Human review remains necessary for lawful purpose, copy, brand and broader privacy risk.
