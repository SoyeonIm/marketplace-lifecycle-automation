from __future__ import annotations

import json
import re
import sqlite3
import sys
import unittest
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analyze_experiment import _two_proportion_test, analyze_experiment
from src.activation_mock import (
    build_activation_records,
    initialize_destination,
    run_activation_mock,
    sync_activation_records,
)
from src.build_dashboard import build_dashboard
from src.build_readme_assets import build_readme_assets
from src.config import ASSETS_DIR, DATABASE_PATH, RAW_DIR, REPORTS_DIR
from src.generate_data import generate_data
from src.pipeline import build_warehouse
from src.quality_checks import run_quality_checks
from src.simulate_decision_scenarios import simulate_decision_scenarios


class EndToEndProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (RAW_DIR / "members.csv").exists():
            generate_data(member_count=12_000, seed=42)
        build_warehouse()
        cls.quality = run_quality_checks(write_report=True)
        cls.metrics = analyze_experiment()
        cls.dashboard_path = build_dashboard()
        cls.asset_paths = build_readme_assets()
        cls.decision_scenarios = simulate_decision_scenarios(cls.metrics)
        cls.activation_report = run_activation_mock(reset=True)

    def test_all_quality_and_campaign_safety_checks_pass(self) -> None:
        failures = [check for check in self.quality if check["status"] != "PASS"]
        self.assertEqual([], failures)
        self.assertGreaterEqual(len(self.quality), 25)

    def test_randomization_is_valid_before_reading_effects(self) -> None:
        diagnostics = self.metrics["randomization_diagnostics"]
        self.assertTrue(diagnostics["sample_ratio_mismatch"]["passes"])
        self.assertTrue(diagnostics["pre_treatment_balance"]["passes"])
        self.assertLess(diagnostics["pre_treatment_balance"]["max_absolute_smd"], 0.10)
        self.assertTrue(self.metrics["power_plan"]["passes"])
        self.assertGreaterEqual(
            self.metrics["power_plan"]["observed_members_per_arm"],
            self.metrics["power_plan"]["required_members_per_arm"],
        )

    def test_personalized_arm_has_positive_confirmatory_result(self) -> None:
        comparison = self.metrics["comparisons_vs_control"]["personalized"]
        self.assertGreater(comparison["absolute_uplift_pp"], 0)
        self.assertGreater(comparison["ci_95_low_pp"], 0)
        self.assertLess(comparison["bonferroni_p_value"], 0.05)
        self.assertTrue(comparison["passes_unsubscribe_guardrail"])

    def test_rollout_decision_requires_all_gates(self) -> None:
        self.assertTrue(self.metrics["decision"]["rollout_ready"])
        self.assertEqual(
            "personalized", self.metrics["decision"]["best_observed_variant"]
        )
        self.assertEqual([], self.metrics["decision"]["failed_gates"])
        self.assertTrue(all(gate["passes"] for gate in self.metrics["decision"]["gates"]))

    def test_failure_scenarios_block_rollout_at_expected_gate(self) -> None:
        scenarios = {
            scenario["scenario_id"]: scenario
            for scenario in self.decision_scenarios["scenarios"]
        }
        self.assertTrue(scenarios["baseline"]["decision"]["rollout_ready"])
        expected_failures = {
            "control_contamination": "data_quality",
            "sample_ratio_mismatch": "sample_ratio_mismatch",
            "pre_treatment_imbalance": "pre_treatment_balance",
            "no_confirmatory_lift": "statistical_significance",
            "unsubscribe_breach": "unsubscribe_guardrail",
            "negative_roi": "commercial_viability",
            "underpowered_test": "statistical_power",
        }
        for scenario_id, gate_name in expected_failures.items():
            with self.subTest(scenario=scenario_id):
                decision = scenarios[scenario_id]["decision"]
                self.assertFalse(decision["rollout_ready"])
                self.assertIn(gate_name, decision["failed_gates"])

    def test_activation_sync_is_idempotent_and_reconciled(self) -> None:
        report = self.activation_report
        treatment_count = report["reconciliation"]["treatment_source_count"]
        self.assertEqual(treatment_count, report["first_sync"]["created"])
        self.assertEqual(treatment_count, report["idempotent_replay"]["unchanged"])
        self.assertEqual(
            treatment_count,
            report["reconciliation"]["destination_active_count"],
        )
        self.assertEqual(0, report["reconciliation"]["source_destination_delta"])
        self.assertEqual(0, report["reconciliation"]["duplicate_idempotency_keys"])
        self.assertTrue(all(check["status"] == "PASS" for check in report["checks"]))
        self.assertNotIn("email_address", report["sample_payloads"][0])

    def test_activation_validation_suppresses_and_rejects_unsafe_records(self) -> None:
        source_records = build_activation_records()
        suppressed = dict(source_records[0])
        suppressed["is_suppressed"] = 1
        invalid_channel = dict(source_records[1])
        invalid_channel["activation_channel"] = "sms"
        control = dict(source_records[2])
        control["variant"] = "control"
        with closing(sqlite3.connect(":memory:")) as destination:
            initialize_destination(destination, reset=True)
            result = sync_activation_records(
                [suppressed, invalid_channel, control],
                destination,
                run_id="validation-test",
            )
        self.assertEqual(1, result["suppressed"])
        self.assertEqual(2, result["rejected"])
        self.assertEqual(0, result["created"])

    def test_two_proportion_interval_contains_observed_difference(self) -> None:
        result = _two_proportion_test(162, 1358, 93, 1358)
        self.assertLess(result["ci_95_low_pp"], result["absolute_uplift_pp"])
        self.assertGreater(result["ci_95_high_pp"], result["absolute_uplift_pp"])

    def test_dashboard_and_activation_contract_are_generated(self) -> None:
        self.assertTrue(self.dashboard_path.exists())
        dashboard = self.dashboard_path.read_text(encoding="utf-8")
        self.assertIn("Seller Reactivation Campaign", dashboard)
        self.assertIn("Staged rollout recommended", dashboard)
        sample = REPORTS_DIR / "activation_audience_sample.csv"
        self.assertTrue(sample.exists())
        header = sample.read_text(encoding="utf-8").splitlines()[0]
        self.assertNotIn("email_address", header)
        self.assertIn("member_id", header)

    def test_readme_visual_assets_are_generated_from_current_metrics(self) -> None:
        expected = {
            ASSETS_DIR / "project-overview.svg",
            ASSETS_DIR / "audience-funnel.svg",
            ASSETS_DIR / "experiment-results.svg",
            ASSETS_DIR / "system-architecture.svg",
        }
        self.assertEqual(expected, set(self.asset_paths))
        for svg_path in expected:
            self.assertEqual(
                "{http://www.w3.org/2000/svg}svg",
                ET.parse(svg_path).getroot().tag,
            )
        experiment_svg = (ASSETS_DIR / "experiment-results.svg").read_text(encoding="utf-8")
        personalized = self.metrics["arms"]["personalized"]
        self.assertIn(f"{personalized['conversion_rate'] * 100:.2f}%", experiment_svg)
        self.assertIn("Bonferroni-adjusted", experiment_svg)
        preview = ASSETS_DIR / "dashboard-preview.jpg"
        self.assertTrue(preview.exists())
        self.assertEqual(b"\xff\xd8", preview.read_bytes()[:2])

    def test_metrics_artifact_labels_commercial_assumptions_synthetic(self) -> None:
        metrics_path = REPORTS_DIR / "experiment_metrics.json"
        artifact = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertIn("not real company financial data", artifact["commercial_assumptions"]["note"])

    def test_readme_result_snapshot_matches_generated_metrics(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        personalized = self.metrics["arms"]["personalized"]
        control = self.metrics["arms"]["control"]
        total = sum(arm["assigned_members"] for arm in self.metrics["arms"].values())
        comparison = self.metrics["comparisons_vs_control"]["personalized"]
        self.assertIn(f"{total:,} eligible", readme)
        self.assertIn(f"{personalized['conversion_rate'] * 100:.2f}%", readme)
        self.assertIn(f"{control['conversion_rate'] * 100:.2f}%", readme)
        self.assertIn(f"{comparison['absolute_uplift_pp']:.2f} percentage points", readme)

    def test_relative_markdown_links_resolve(self) -> None:
        markdown_files = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "dbt" / "README.md"]
        markdown_files.extend(sorted((PROJECT_ROOT / "docs").glob("*.md")))
        broken: list[str] = []
        for markdown_path in markdown_files:
            content = markdown_path.read_text(encoding="utf-8")
            targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", content)
            targets.extend(re.findall(r'<img[^>]+src="([^"]+)"', content))
            for target in targets:
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                relative_target = target.split("#", 1)[0]
                if not (markdown_path.parent / relative_target).resolve().exists():
                    broken.append(f"{markdown_path.relative_to(PROJECT_ROOT)} -> {target}")
        self.assertEqual([], broken)

    def test_dbt_model_references_resolve_within_scaffold(self) -> None:
        model_paths = list((PROJECT_ROOT / "dbt" / "models").rglob("*.sql"))
        model_names = {path.stem for path in model_paths}
        unresolved: list[str] = []
        for model_path in model_paths:
            sql = model_path.read_text(encoding="utf-8")
            for reference in re.findall(r"ref\(['\"]([^'\"]+)['\"]\)", sql):
                if reference not in model_names:
                    unresolved.append(f"{model_path.name} -> {reference}")
        self.assertEqual([], unresolved)


if __name__ == "__main__":
    unittest.main()
