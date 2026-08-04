from __future__ import annotations

import copy
import json

from src.analyze_experiment import evaluate_rollout_decision
from src.config import REPORTS_DIR, ensure_directories


def _evaluate(metrics: dict, *, quality_checks_pass: bool = True) -> dict:
    best_variant = metrics["decision"]["best_observed_variant"]
    return evaluate_rollout_decision(
        best_variant,
        metrics["comparisons_vs_control"][best_variant],
        metrics["randomization_diagnostics"],
        metrics["power_plan"],
        quality_checks_pass=quality_checks_pass,
    )


def simulate_decision_scenarios(metrics: dict | None = None) -> dict:
    """Stress-test the rollout policy against operational and analytical failures."""
    ensure_directories()
    if metrics is None:
        metrics = json.loads(
            (REPORTS_DIR / "experiment_metrics.json").read_text(encoding="utf-8")
        )

    scenarios: list[dict] = [
        {
            "scenario_id": "baseline",
            "description": "All pre-analysis, statistical, customer and commercial gates pass.",
            "decision": _evaluate(copy.deepcopy(metrics)),
        },
        {
            "scenario_id": "control_contamination",
            "description": "A control member receives a target-campaign message.",
            "decision": _evaluate(copy.deepcopy(metrics), quality_checks_pass=False),
        },
    ]

    srm = copy.deepcopy(metrics)
    srm["randomization_diagnostics"]["sample_ratio_mismatch"].update(
        {"p_value": 0.0005, "passes": False}
    )
    scenarios.append(
        {
            "scenario_id": "sample_ratio_mismatch",
            "description": "Observed assignment counts are inconsistent with the allocation plan.",
            "decision": _evaluate(srm),
        }
    )

    imbalance = copy.deepcopy(metrics)
    imbalance["randomization_diagnostics"]["pre_treatment_balance"].update(
        {"max_absolute_smd": 0.16, "passes": False}
    )
    scenarios.append(
        {
            "scenario_id": "pre_treatment_imbalance",
            "description": "A pre-treatment covariate exceeds the balance threshold.",
            "decision": _evaluate(imbalance),
        }
    )

    no_lift = copy.deepcopy(metrics)
    best_variant = no_lift["decision"]["best_observed_variant"]
    no_lift["comparisons_vs_control"][best_variant].update(
        {"bonferroni_p_value": 0.18, "ci_95_low_pp": -0.65}
    )
    scenarios.append(
        {
            "scenario_id": "no_confirmatory_lift",
            "description": "The treatment point estimate is positive but confirmatory evidence fails.",
            "decision": _evaluate(no_lift),
        }
    )

    unsubscribe = copy.deepcopy(metrics)
    unsubscribe["comparisons_vs_control"][best_variant].update(
        {"guardrail_unsubscribe_rate_pct": 1.35, "passes_unsubscribe_guardrail": False}
    )
    scenarios.append(
        {
            "scenario_id": "unsubscribe_breach",
            "description": "The treatment exceeds the one-percent unsubscribe guardrail.",
            "decision": _evaluate(unsubscribe),
        }
    )

    negative_roi = copy.deepcopy(metrics)
    negative_roi["comparisons_vs_control"][best_variant]["estimated_roi_pct"] = -18.0
    scenarios.append(
        {
            "scenario_id": "negative_roi",
            "description": "Approved unit economics produce a negative scenario ROI.",
            "decision": _evaluate(negative_roi),
        }
    )

    underpowered = copy.deepcopy(metrics)
    underpowered["power_plan"].update(
        {
            "observed_members_per_arm": underpowered["power_plan"][
                "required_members_per_arm"
            ]
            - 1,
            "passes": False,
        }
    )
    scenarios.append(
        {
            "scenario_id": "underpowered_test",
            "description": "The available audience is below the pre-specified sample requirement.",
            "decision": _evaluate(underpowered),
        }
    )

    artifact = {
        "policy": "every independent rollout gate must pass",
        "scenarios": scenarios,
    }
    (REPORTS_DIR / "decision_scenarios.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8"
    )
    return artifact
