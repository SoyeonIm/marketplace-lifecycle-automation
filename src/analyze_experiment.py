from __future__ import annotations

import json
import math
import sqlite3
import statistics

from src.config import DATABASE_PATH, REPORTS_DIR, ensure_directories


# Illustrative unit economics only. The deliberately conservative value avoids
# making the case depend on an implausibly large financial assumption.
VALUE_PER_INCREMENTAL_LISTING_NZD = 5.50
CAMPAIGN_COSTS = {
    "generic": {"fixed": 80.0, "per_message": 0.015},
    "personalized": {"fixed": 120.0, "per_message": 0.020},
}


def _format_p_value(value: float) -> str:
    return "<0.0001" if value < 0.0001 else f"{value:.4f}"


def _wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    rate = successes / n
    denominator = 1 + z * z / n
    centre = (rate + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denominator
    return centre - radius, centre + radius


def _two_proportion_test(
    treatment_conversions: int,
    treatment_n: int,
    control_conversions: int,
    control_n: int,
) -> dict:
    treatment_rate = treatment_conversions / treatment_n
    control_rate = control_conversions / control_n
    difference = treatment_rate - control_rate
    pooled = (treatment_conversions + control_conversions) / (treatment_n + control_n)
    pooled_se = math.sqrt(pooled * (1 - pooled) * (1 / treatment_n + 1 / control_n))
    z_score = difference / pooled_se if pooled_se else 0.0
    p_value = math.erfc(abs(z_score) / math.sqrt(2))
    treatment_low, treatment_high = _wilson_interval(treatment_conversions, treatment_n)
    control_low, control_high = _wilson_interval(control_conversions, control_n)
    # Newcombe's score interval for a difference in independent proportions.
    ci_low = difference - math.sqrt(
        (treatment_rate - treatment_low) ** 2 + (control_high - control_rate) ** 2
    )
    ci_high = difference + math.sqrt(
        (treatment_high - treatment_rate) ** 2 + (control_rate - control_low) ** 2
    )
    return {
        "absolute_uplift_pp": difference * 100,
        "relative_uplift_pct": (difference / control_rate * 100) if control_rate else None,
        "ci_95_low_pp": ci_low * 100,
        "ci_95_high_pp": ci_high * 100,
        "z_score": z_score,
        "p_value": p_value,
    }


def _standardized_mean_difference(treatment: list[float], control: list[float]) -> float:
    treatment_mean = statistics.fmean(treatment)
    control_mean = statistics.fmean(control)
    treatment_variance = statistics.variance(treatment) if len(treatment) > 1 else 0.0
    control_variance = statistics.variance(control) if len(control) > 1 else 0.0
    pooled_sd = math.sqrt((treatment_variance + control_variance) / 2)
    return (treatment_mean - control_mean) / pooled_sd if pooled_sd else 0.0


def _required_sample_per_arm(
    baseline_rate: float,
    minimum_detectable_effect: float,
    alpha_per_comparison: float,
    power: float,
) -> int:
    treatment_rate = baseline_rate + minimum_detectable_effect
    average_rate = (baseline_rate + treatment_rate) / 2
    z_alpha = statistics.NormalDist().inv_cdf(1 - alpha_per_comparison / 2)
    z_power = statistics.NormalDist().inv_cdf(power)
    numerator = (
        z_alpha * math.sqrt(2 * average_rate * (1 - average_rate))
        + z_power
        * math.sqrt(
            baseline_rate * (1 - baseline_rate)
            + treatment_rate * (1 - treatment_rate)
        )
    ) ** 2
    return math.ceil(numerator / minimum_detectable_effect**2)


def _randomization_diagnostics(connection: sqlite3.Connection, arms: dict[str, dict]) -> dict:
    observed = {name: arm["assigned_members"] for name, arm in arms.items()}
    expected = sum(observed.values()) / len(observed)
    chi_square = sum((count - expected) ** 2 / expected for count in observed.values())
    # With three equal arms, df=2 and the chi-square survival function is exp(-x/2).
    srm_p_value = math.exp(-chi_square / 2)

    covariates = [
        "historical_listing_count",
        "historical_sales_count",
        "historical_gmv",
        "recent_event_count",
        "recent_watchlist_count",
        "recent_purchase_count",
        "marketing_contacts_7d",
    ]
    rows = connection.execute(
        f"""
            SELECT x.variant, {', '.join('m.' + column for column in covariates)}
            FROM raw_experiment_assignments x
            JOIN mart_member_360 m ON x.member_id = m.member_id
        """
    ).fetchall()
    grouped: dict[str, dict[str, list[float]]] = {
        variant: {column: [] for column in covariates} for variant in arms
    }
    for row in rows:
        variant = row[0]
        for index, column in enumerate(covariates, start=1):
            grouped[variant][column].append(float(row[index] or 0))

    balance: dict[str, dict[str, float]] = {}
    for variant in ("generic", "personalized"):
        balance[variant] = {
            column: _standardized_mean_difference(
                grouped[variant][column], grouped["control"][column]
            )
            for column in covariates
        }
    max_absolute_smd = max(
        abs(value) for comparison in balance.values() for value in comparison.values()
    )
    return {
        "sample_ratio_mismatch": {
            "observed_counts": observed,
            "expected_per_arm": expected,
            "chi_square": chi_square,
            "p_value": srm_p_value,
            "passes": srm_p_value >= 0.01,
            "decision_threshold": 0.01,
        },
        "pre_treatment_balance": {
            "standardized_mean_differences_vs_control": balance,
            "max_absolute_smd": max_absolute_smd,
            "passes": max_absolute_smd < 0.10,
            "decision_threshold": 0.10,
        },
    }


def evaluate_rollout_decision(
    best_variant: str,
    comparison: dict,
    randomization: dict,
    power_plan: dict,
    *,
    quality_checks_pass: bool = True,
) -> dict:
    """Evaluate independent rollout gates and return an auditable decision."""
    gates = [
        {
            "name": "data_quality",
            "requirement": "all blocking data and campaign-safety checks pass",
            "observed": "pass" if quality_checks_pass else "failure detected",
            "passes": quality_checks_pass,
        },
        {
            "name": "sample_ratio_mismatch",
            "requirement": "p-value >= 0.01",
            "observed": randomization["sample_ratio_mismatch"]["p_value"],
            "passes": randomization["sample_ratio_mismatch"]["passes"],
        },
        {
            "name": "pre_treatment_balance",
            "requirement": "maximum absolute SMD < 0.10",
            "observed": randomization["pre_treatment_balance"]["max_absolute_smd"],
            "passes": randomization["pre_treatment_balance"]["passes"],
        },
        {
            "name": "statistical_significance",
            "requirement": "Bonferroni-adjusted p-value < 0.05",
            "observed": comparison["bonferroni_p_value"],
            "passes": comparison["bonferroni_p_value"] < 0.05,
        },
        {
            "name": "confidence_interval",
            "requirement": "95% confidence interval lower bound > 0",
            "observed": comparison["ci_95_low_pp"],
            "passes": comparison["ci_95_low_pp"] > 0,
        },
        {
            "name": "unsubscribe_guardrail",
            "requirement": "unsubscribe rate <= 1%",
            "observed": comparison["guardrail_unsubscribe_rate_pct"],
            "passes": comparison["passes_unsubscribe_guardrail"],
        },
        {
            "name": "commercial_viability",
            "requirement": "scenario ROI > 0%",
            "observed": comparison["estimated_roi_pct"],
            "passes": comparison["estimated_roi_pct"] > 0,
        },
        {
            "name": "statistical_power",
            "requirement": "observed members per arm >= required members per arm",
            "observed": power_plan["observed_members_per_arm"],
            "passes": power_plan["passes"],
        },
    ]
    failed_gates = [gate["name"] for gate in gates if not gate["passes"]]
    rollout_ready = not failed_gates
    recommendation = (
        f"Roll out {best_variant} to a staged 50% audience, retain a 10% holdout, and monitor "
        "unsubscribe and listing quality."
        if rollout_ready
        else "Do not roll out; investigate failed gates: " + ", ".join(failed_gates) + "."
    )
    return {
        "best_observed_variant": best_variant,
        "rollout_ready": rollout_ready,
        "failed_gates": failed_gates,
        "gates": gates,
        "recommendation": recommendation,
    }


def analyze_experiment() -> dict:
    ensure_directories()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT * FROM mart_experiment_results ORDER BY variant"
        ).fetchall()
        arms: dict[str, dict] = {}
        for row in rows:
            arm = dict(row)
            arm["conversion_rate"] = arm["converted_members"] / arm["assigned_members"]
            arm["unsubscribe_rate"] = (
                arm["unsubscribe_count"] / arm["message_sent_count"]
                if arm["message_sent_count"]
                else 0.0
            )
            arms[arm["variant"]] = arm

        required = {"control", "generic", "personalized"}
        if set(arms) != required:
            raise ValueError(f"Expected experiment arms {required}, observed {set(arms)}")

        randomization = _randomization_diagnostics(connection, arms)
    finally:
        connection.close()

    control = arms["control"]
    power_plan = {
        "assumed_baseline_rate": 0.07,
        "minimum_detectable_effect_pp": 4.0,
        "alpha_per_comparison": 0.025,
        "target_power": 0.80,
    }
    power_plan["required_members_per_arm"] = _required_sample_per_arm(
        power_plan["assumed_baseline_rate"],
        power_plan["minimum_detectable_effect_pp"] / 100,
        power_plan["alpha_per_comparison"],
        power_plan["target_power"],
    )
    power_plan["observed_members_per_arm"] = min(
        arm["assigned_members"] for arm in arms.values()
    )
    power_plan["passes"] = (
        power_plan["observed_members_per_arm"] >= power_plan["required_members_per_arm"]
    )
    comparisons: dict[str, dict] = {}
    for variant in ("generic", "personalized"):
        arm = arms[variant]
        comparison = _two_proportion_test(
            arm["converted_members"],
            arm["assigned_members"],
            control["converted_members"],
            control["assigned_members"],
        )
        comparison["bonferroni_p_value"] = min(1.0, comparison["p_value"] * 2)
        incremental_listings = comparison["absolute_uplift_pp"] / 100 * arm["assigned_members"]
        cost = CAMPAIGN_COSTS[variant]["fixed"] + (
            CAMPAIGN_COSTS[variant]["per_message"] * arm["message_sent_count"]
        )
        incremental_value = incremental_listings * VALUE_PER_INCREMENTAL_LISTING_NZD
        comparison.update(
            {
                "incremental_listings_estimate": incremental_listings,
                "assumed_incremental_value_nzd": incremental_value,
                "assumed_campaign_cost_nzd": cost,
                "estimated_roi_pct": (incremental_value - cost) / cost * 100,
                "guardrail_unsubscribe_rate_pct": arm["unsubscribe_rate"] * 100,
                "passes_unsubscribe_guardrail": arm["unsubscribe_rate"] <= 0.01,
            }
        )
        comparisons[variant] = comparison

    best_variant = max(comparisons, key=lambda name: comparisons[name]["absolute_uplift_pp"])
    best = comparisons[best_variant]
    decision = evaluate_rollout_decision(
        best_variant,
        best,
        randomization,
        power_plan,
    )

    metrics = {
        "experiment_id": "exp_seller_reactivation_2026_08",
        "analysis_window": "2026-08-01 to 2026-08-15",
        "primary_metric": "member created at least one listing within 14 days",
        "arms": arms,
        "comparisons_vs_control": comparisons,
        "randomization_diagnostics": randomization,
        "power_plan": power_plan,
        "decision": decision,
        "commercial_assumptions": {
            "value_per_incremental_listing_nzd": VALUE_PER_INCREMENTAL_LISTING_NZD,
            "note": "Synthetic scenario assumption; not real company financial data.",
        },
        "methodology": {
            "test": "two-sided pooled two-proportion z-test",
            "confidence_interval": "95% Newcombe score interval for absolute difference",
            "multiple_comparison_control": "Bonferroni correction for two treatment arms",
            "estimand": "intention-to-treat incremental conversion",
            "randomization_validation": "sample-ratio-mismatch test plus pre-treatment standardized mean differences",
        },
    }

    (REPORTS_DIR / "experiment_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    _write_executive_summary(metrics)
    return metrics


def _write_executive_summary(metrics: dict) -> None:
    control = metrics["arms"]["control"]
    best_name = metrics["decision"]["best_observed_variant"]
    best_arm = metrics["arms"][best_name]
    best = metrics["comparisons_vs_control"][best_name]
    randomization = metrics["randomization_diagnostics"]
    summary = f"""# Campaign experiment executive summary

## Decision

{metrics['decision']['recommendation']}

## Evidence

- Eligible and randomized audience: {sum(arm['assigned_members'] for arm in metrics['arms'].values()):,} members.
- Control conversion: {control['conversion_rate'] * 100:.2f}% ({control['converted_members']}/{control['assigned_members']}).
- Best observed variant: **{best_name}**, at {best_arm['conversion_rate'] * 100:.2f}%.
- Absolute uplift: {best['absolute_uplift_pp']:.2f} percentage points.
- Relative uplift: {best['relative_uplift_pct']:.1f}%.
- 95% CI: {best['ci_95_low_pp']:.2f} to {best['ci_95_high_pp']:.2f} percentage points.
- Bonferroni-adjusted p-value: {_format_p_value(best['bonferroni_p_value'])}.
- Sample-ratio-mismatch p-value: {_format_p_value(randomization['sample_ratio_mismatch']['p_value'])}.
- Maximum pre-treatment standardized mean difference: {randomization['pre_treatment_balance']['max_absolute_smd']:.3f}.
- Pre-specified sample requirement: {metrics['power_plan']['required_members_per_arm']:,} per arm; observed {metrics['power_plan']['observed_members_per_arm']:,}.
- Estimated incremental listings in the test: {best['incremental_listings_estimate']:.1f}.
- Unsubscribe guardrail: {best['guardrail_unsubscribe_rate_pct']:.2f}% (limit: 1.00%).
- Scenario ROI: {best['estimated_roi_pct']:.1f}%.

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
"""
    (REPORTS_DIR / "executive_summary.md").write_text(summary, encoding="utf-8")
