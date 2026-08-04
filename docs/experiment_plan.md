# Pre-analysis plan

## Design

- Unit of randomization: member
- Arms: equal allocation to control, generic and personalized
- Assignment time: one hour before campaign launch
- Primary analysis: intention to treat
- Outcome window: 14 days after launch
- Main comparisons: generic vs control; personalized vs control
- No generic-vs-personalized confirmatory test is used for rollout

## Statistical policy

- Two-sided pooled two-proportion z-test for each treatment-control comparison
- Newcombe score interval for the absolute difference in proportions
- Bonferroni-adjusted alpha of 0.025 per confirmatory comparison
- Sample-ratio-mismatch failure threshold: p < 0.01
- Pre-treatment imbalance threshold: absolute standardized mean difference >= 0.10
- No peeking-based early stop in this fixed synthetic dataset

## Sample-size plan

The design assumes a 7% control conversion rate and treats a 4 percentage point absolute uplift as
the minimum effect worth detecting. With 80% power, a two-sided alpha of 0.025 per comparison after
Bonferroni allocation, and equal treatment/control sizes, the normal approximation requires about
972 members per arm. The generated eligible audience provides at least 1,350 members per arm, so it clears
the pre-specified requirement before results are examined.

## Decision table

| Evidence | Action |
|---|---|
| Positive adjusted result, CI above zero, guardrails and ROI pass | Staged rollout with persistent holdout |
| Positive point estimate but adjusted p or CI fails | Continue or redesign; no rollout claim |
| Unsubscribe exceeds 1% | Stop treatment regardless of conversion |
| SRM or covariate balance fails | Investigate assignment/instrumentation before reading effect |
| ROI fails using approved inputs | Do not scale even if causal effect is positive |

## Avoided analytical errors

- Campaign openers are not compared with non-openers because opening is post-treatment selection.
- Only pre-campaign data is used for audience eligibility and balance checks.
- Click rate is not treated as the business outcome.
- Treatment effects are not inferred from simple before-and-after comparisons.
- Segment-level results are exploratory unless independently powered and pre-registered.
