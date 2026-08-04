# Business brief: lapsed-seller reactivation

## Context

A marketplace needs healthy supply as well as buyer demand. Historical sellers who still browse,
watch or purchase are a promising reactivation population, but broad messaging can create fatigue,
conflict with other lifecycle journeys and overstate success when naturally returning sellers are
counted as campaign-driven conversions.

## Objective

Increase the number of eligible historical sellers who create at least one listing within 14 days,
while preserving member trust and measuring true incremental impact.

## Target population

- At least one listing before campaign launch
- No listing in the previous 90 days
- At least one product event in the previous 30 days
- Consent for email or push at campaign time
- Not on the suppression list
- Fewer than two marketing contacts in the previous seven days
- No active high-priority campaign, customer-support hold or experiment holdout

## Hypotheses

- **H1:** A generic reactivation message increases 14-day listing creation versus no message.
- **H2:** A message personalized using the member's recent category signal produces greater uplift
  than no message and is the preferred scalable treatment.
- **Guardrail hypothesis:** Neither treatment pushes unsubscribe above 1%.

## KPIs

| Type | KPI | Definition |
|---|---|---|
| Primary | 14-day listing conversion | Member creates one or more listings within 14 days of assignment |
| Secondary | Listing count | Total listings created within the outcome window |
| Secondary | Observed sold listings | Outcome-window listings with a later sold timestamp |
| Diagnostic | Click rate | Campaign clicks divided by sent messages |
| Guardrail | Unsubscribe rate | Unsubscribes divided by sent messages |
| Guardrail | Contact pressure | Marketing contacts in seven days, including the planned touch |
| Commercial | Incremental listing value | Estimated incremental listings multiplied by approved unit value |

## Stakeholders and responsibilities

| Stakeholder | Decision or contribution |
|---|---|
| Customer Lifecycle | Journey objective, channel, message and customer experience |
| Lifecycle Analytics | Audience logic, experiment, QA, measurement and recommendation |
| Data/Analytics Engineering | Governed models, freshness, lineage and production reliability |
| Product/Event Tagging | Event definitions and instrumentation quality |
| Legal/Privacy | Consent, unsubscribe and permitted use review |
| Finance | Unit economics and ROI assumptions |

## Out of scope

- Creative production and brand approval
- Real company data or financial assumptions
- Production API credentials
- Long-term seller quality, retention and fraud outcomes
