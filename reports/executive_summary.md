# Campaign experiment executive summary

## Decision

Roll out personalized to a staged 50% audience, retain a 10% holdout, and monitor unsubscribe and listing quality.

## Evidence

- Eligible and randomized audience: 4,051 members.
- Control conversion: 7.92% (107/1351).
- Best observed variant: **personalized**, at 11.33%.
- Absolute uplift: 3.41 percentage points.
- Relative uplift: 43.1%.
- 95% CI: 1.19 to 5.65 percentage points.
- Bonferroni-adjusted p-value: 0.0053.
- Sample-ratio-mismatch p-value: 0.9998.
- Maximum pre-treatment standardized mean difference: 0.047.
- Pre-specified sample requirement: 972 per arm; observed 1,350.
- Estimated incremental listings in the test: 46.1.
- Unsubscribe guardrail: 0.22% (limit: 1.00%).
- Scenario ROI: 72.4%.

## Interpretation

This is an intention-to-treat result from deterministic random assignment. Assignment ratios and
pre-treatment covariates passed the pre-specified randomization checks. Open and click rates are
diagnostic metrics only; the decision is based on incremental listing creation, a customer guardrail,
and an explicit commercial scenario. The value-per-listing and campaign-cost inputs are synthetic
assumptions for scenario modelling and must be replaced with Finance-approved values in production.

## Next actions

1. Stage the winning variant rather than launching to 100% of the eligible audience.
2. Keep a persistent holdout to measure longer-term incremental listings and downstream sales.
3. Monitor unsubscribe, support contacts, duplicate messaging and listing quality by category.
4. Re-estimate ROI with approved contribution-margin inputs.
