from __future__ import annotations

import json
import sqlite3
from html import escape
from pathlib import Path

from src.config import ASSETS_DIR, DATABASE_PATH, REPORTS_DIR, ensure_directories


FONT = "Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
INK = "#17212b"
MUTED = "#647383"
LINE = "#dce5eb"
BLUE = "#087ec7"
BLUE_DARK = "#075f9e"
ORANGE = "#f6a800"
GREEN = "#14845c"
SOFT_BLUE = "#e9f4fb"
SOFT_ORANGE = "#fff5dd"
SOFT_GREEN = "#e8f5ef"


def _write_svg(name: str, content: str) -> Path:
    path = ASSETS_DIR / name
    normalized = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    path.write_text(normalized, encoding="utf-8")
    return path


def _load_inputs() -> tuple[dict, list[dict], int, int]:
    metrics = json.loads((REPORTS_DIR / "experiment_metrics.json").read_text(encoding="utf-8"))
    quality = json.loads((REPORTS_DIR / "data_quality.json").read_text(encoding="utf-8"))
    with sqlite3.connect(DATABASE_PATH) as connection:
        funnel_queries = [
            ("All members", "1 = 1"),
            ("Seller history", "has_seller_history = 1"),
            ("Lapsed 90+ days", "has_seller_history = 1 AND is_lapsed_seller = 1"),
            (
                "Recently active",
                "has_seller_history = 1 AND is_lapsed_seller = 1 AND has_recent_activity = 1",
            ),
            (
                "Marketing consent",
                "has_seller_history = 1 AND is_lapsed_seller = 1 AND has_recent_activity = 1 "
                "AND has_marketing_consent = 1",
            ),
            (
                "Not suppressed",
                "has_seller_history = 1 AND is_lapsed_seller = 1 AND has_recent_activity = 1 "
                "AND has_marketing_consent = 1 AND is_suppressed = 0",
            ),
            (
                "Within contact cap",
                "has_seller_history = 1 AND is_lapsed_seller = 1 AND has_recent_activity = 1 "
                "AND has_marketing_consent = 1 AND is_suppressed = 0 AND within_contact_cap = 1",
            ),
            (
                "No campaign conflict",
                "has_seller_history = 1 AND is_lapsed_seller = 1 AND has_recent_activity = 1 "
                "AND has_marketing_consent = 1 AND is_suppressed = 0 AND within_contact_cap = 1 "
                "AND has_no_campaign_conflict = 1",
            ),
        ]
        funnel = [
            {
                "label": label,
                "count": connection.execute(
                    f"SELECT COUNT(*) FROM mart_member_360 WHERE {condition}"
                ).fetchone()[0],
            }
            for label, condition in funnel_queries
        ]
        event_count = connection.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
    return metrics, funnel, sum(check["status"] == "PASS" for check in quality), event_count


def _project_overview(metrics: dict, funnel: list[dict], quality_passed: int, event_count: int) -> str:
    audience = sum(arm["assigned_members"] for arm in metrics["arms"].values())
    best = metrics["comparisons_vs_control"][metrics["decision"]["best_observed_variant"]]
    stages = [
        ("01 · SIGNALS", f"{event_count:,}", "product events"),
        ("02 · GOVERNANCE", f"{audience:,}", "eligible members"),
        ("03 · EXPERIMENT", "3 arms", "randomized design"),
        ("04 · OUTCOME", "+{:.2f} pp".format(best["absolute_uplift_pp"]), "incremental conversion"),
        ("05 · DECISION", "50% staged", "rollout + 10% holdout"),
    ]
    cards = []
    for index, (label, value, detail) in enumerate(stages):
        x = 48 + index * 226
        cards.append(
            f"""
    <g transform="translate({x} 172)">
      <rect width="202" height="142" rx="18" fill="#ffffff" fill-opacity="0.10" stroke="#ffffff" stroke-opacity="0.20"/>
      <text x="20" y="31" fill="#a9d8f3" font-size="12" font-weight="700" letter-spacing="1.2">{escape(label)}</text>
      <text x="20" y="78" fill="#ffffff" font-size="28" font-weight="750">{escape(value)}</text>
      <text x="20" y="108" fill="#dbeefa" font-size="14">{escape(detail)}</text>
    </g>"""
        )
        if index < len(stages) - 1:
            arrow_x = x + 207
            cards.append(
                f'<path d="M {arrow_x} 243 H {arrow_x + 14}" stroke="#7fc5eb" stroke-width="3" marker-end="url(#arrow)"/>'
            )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="390" viewBox="0 0 1200 390" role="img" aria-labelledby="title desc">
  <title id="title">Marketplace lifecycle automation project overview</title>
  <desc id="desc">Five stages connect product events to a governed audience, randomized experiment, causal outcome and staged rollout decision.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#063e69"/><stop offset="0.66" stop-color="#087ec7"/><stop offset="1" stop-color="#075f9e"/></linearGradient>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#7fc5eb"/></marker>
  </defs>
  <rect width="1200" height="390" rx="24" fill="url(#bg)"/>
  <circle cx="1110" cy="24" r="220" fill="#f6a800" opacity="0.10"/>
  <text x="48" y="62" fill="#f9c548" font-family="{FONT}" font-size="13" font-weight="700" letter-spacing="1.8">END-TO-END LIFECYCLE ANALYTICS</text>
  <text x="48" y="106" fill="#ffffff" font-family="{FONT}" font-size="35" font-weight="750">From product signals to a governed growth decision</text>
  <text x="48" y="137" fill="#dbeefa" font-family="{FONT}" font-size="16">Synthetic marketplace data · reproducible SQL pipeline · {quality_passed}/{quality_passed} quality and campaign-safety checks</text>
  <g font-family="{FONT}">{''.join(cards)}</g>
  <text x="48" y="354" fill="#dbeefa" font-family="{FONT}" font-size="13">Primary outcome: 14-day listing creation · Guardrail: unsubscribe ≤ 1% · Estimand: intention-to-treat uplift</text>
</svg>"""


def _audience_funnel(funnel: list[dict]) -> str:
    maximum = funnel[0]["count"]
    rows = []
    for index, item in enumerate(funnel):
        y = 106 + index * 54
        width = item["count"] / maximum * 760
        rate = item["count"] / maximum * 100
        fill = BLUE if index < len(funnel) - 1 else GREEN
        rows.append(
            f"""
    <text x="48" y="{y + 20}" fill="{INK}" font-size="14" font-weight="650">{escape(item['label'])}</text>
    <rect x="238" y="{y}" width="760" height="30" rx="8" fill="#eef3f6"/>
    <rect x="238" y="{y}" width="{width:.1f}" height="30" rx="8" fill="{fill}" opacity="{0.72 + index * 0.035:.2f}"/>
    <text x="1018" y="{y + 20}" fill="{INK}" font-size="14" font-weight="700">{item['count']:,}</text>
    <text x="1101" y="{y + 20}" fill="{MUTED}" font-size="13">{rate:.1f}%</text>"""
        )
    eligible = funnel[-1]["count"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="580" viewBox="0 0 1200 580" role="img" aria-labelledby="title desc">
  <title id="title">Governed campaign audience funnel</title>
  <desc id="desc">Audience counts after each lifecycle, consent, suppression, contact-cap and campaign-conflict rule.</desc>
  <rect width="1200" height="580" rx="20" fill="#ffffff"/>
  <text x="48" y="48" fill="{INK}" font-family="{FONT}" font-size="27" font-weight="750">Governed audience waterfall</text>
  <text x="48" y="76" fill="{MUTED}" font-family="{FONT}" font-size="14">Every exclusion is applied before assignment; percentages use all 12,000 members as the denominator.</text>
  <g font-family="{FONT}">{''.join(rows)}</g>
  <rect x="48" y="538" width="1104" height="1" fill="{LINE}"/>
  <text x="48" y="562" fill="{GREEN}" font-family="{FONT}" font-size="14" font-weight="700">Final activation audience: {eligible:,} pseudonymous member IDs</text>
  <text x="1128" y="562" text-anchor="end" fill="{MUTED}" font-family="{FONT}" font-size="13">Consent snapshot · suppression · contact pressure · campaign priority</text>
</svg>"""


def _experiment_results(metrics: dict) -> str:
    arms = metrics["arms"]
    best_name = metrics["decision"]["best_observed_variant"]
    comparison = metrics["comparisons_vs_control"][best_name]
    bar_positions = {"control": 166, "generic": 368, "personalized": 570}
    fills = {"control": "#9ba8b3", "generic": BLUE, "personalized": ORANGE}
    bars = []
    baseline_y = 455
    scale = 27.0
    for name in ("control", "generic", "personalized"):
        rate = arms[name]["conversion_rate"] * 100
        height = rate * scale
        y = baseline_y - height
        bars.append(
            f"""
    <rect x="{bar_positions[name]}" y="{y:.1f}" width="128" height="{height:.1f}" rx="10" fill="{fills[name]}"/>
    <text x="{bar_positions[name] + 64}" y="{y - 13:.1f}" text-anchor="middle" fill="{INK}" font-size="21" font-weight="750">{rate:.2f}%</text>
    <text x="{bar_positions[name] + 64}" y="482" text-anchor="middle" fill="{INK}" font-size="14" font-weight="650">{name.title()}</text>
    <text x="{bar_positions[name] + 64}" y="504" text-anchor="middle" fill="{MUTED}" font-size="12">n={arms[name]['assigned_members']:,}</text>"""
        )
    grid = []
    for tick in (0, 3, 6, 9, 12):
        y = baseline_y - tick * scale
        grid.append(
            f'<line x1="90" y1="{y:.1f}" x2="760" y2="{y:.1f}" stroke="{LINE}"/><text x="72" y="{y + 5:.1f}" text-anchor="end" fill="{MUTED}" font-size="12">{tick}%</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="550" viewBox="0 0 1200 550" role="img" aria-labelledby="title desc">
  <title id="title">Randomized experiment conversion results</title>
  <desc id="desc">Personalized treatment converted 11.33 percent compared with 7.92 percent in control, a statistically significant 3.41 percentage point uplift.</desc>
  <rect width="1200" height="550" rx="20" fill="#ffffff"/>
  <text x="48" y="48" fill="{INK}" font-family="{FONT}" font-size="27" font-weight="750">14-day listing conversion by randomized arm</text>
  <text x="48" y="76" fill="{MUTED}" font-family="{FONT}" font-size="14">Intention-to-treat comparison; opens and clicks remain diagnostic metrics.</text>
  <g font-family="{FONT}">{''.join(grid)}{''.join(bars)}</g>
  <g transform="translate(806 106)" font-family="{FONT}">
    <rect width="346" height="370" rx="18" fill="{SOFT_BLUE}" stroke="#cde5f4"/>
    <text x="24" y="40" fill="{BLUE_DARK}" font-size="12" font-weight="750" letter-spacing="1.1">CONFIRMATORY RESULT</text>
    <text x="24" y="88" fill="{INK}" font-size="31" font-weight="780">+{comparison['absolute_uplift_pp']:.2f} pp</text>
    <text x="24" y="115" fill="{MUTED}" font-size="14">personalized versus control</text>
    <line x1="24" y1="140" x2="322" y2="140" stroke="#c7dce9"/>
    <text x="24" y="177" fill="{INK}" font-size="14" font-weight="650">95% CI</text>
    <text x="322" y="177" text-anchor="end" fill="{INK}" font-size="14">+{comparison['ci_95_low_pp']:.2f} to +{comparison['ci_95_high_pp']:.2f} pp</text>
    <text x="24" y="214" fill="{INK}" font-size="14" font-weight="650">Bonferroni-adjusted p</text>
    <text x="322" y="214" text-anchor="end" fill="{INK}" font-size="14">{comparison['bonferroni_p_value']:.4f}</text>
    <text x="24" y="251" fill="{INK}" font-size="14" font-weight="650">Unsubscribe guardrail</text>
    <text x="322" y="251" text-anchor="end" fill="{GREEN}" font-size="14" font-weight="700">{comparison['guardrail_unsubscribe_rate_pct']:.2f}% ≤ 1.00%</text>
    <text x="24" y="288" fill="{INK}" font-size="14" font-weight="650">Incremental listings</text>
    <text x="322" y="288" text-anchor="end" fill="{INK}" font-size="14">{comparison['incremental_listings_estimate']:.0f} estimated</text>
    <rect x="24" y="316" width="298" height="34" rx="9" fill="{SOFT_GREEN}"/>
    <text x="173" y="338" text-anchor="middle" fill="{GREEN}" font-size="13" font-weight="750">Staged rollout with persistent holdout</text>
  </g>
</svg>"""


def _system_architecture() -> str:
    columns = [
        (48, "COLLECTION & IDENTITY", SOFT_BLUE, [("Product events", "Segment / GA4"), ("Consent history", "Preference centre")]),
        (330, "MODELLING & GOVERNANCE", "#eef2f5", [("Snowflake raw", "source contracts"), ("dbt marts", "Member 360 + audience"), ("Quality gates", "freshness + safety")]),
        (612, "ACTIVATION", SOFT_ORANGE, [("Hightouch", "audience sync"), ("Braze Canvas", "control + treatments")]),
        (894, "MEASUREMENT", SOFT_GREEN, [("Outcome mart", "14-day listings"), ("Experiment analysis", "uplift + guardrails"), ("Decision report", "rollout policy")]),
    ]
    groups = []
    for x, heading, background, nodes in columns:
        node_markup = []
        for index, (title, detail) in enumerate(nodes):
            y = 70 + index * 88
            node_markup.append(
                f"""
      <rect x="18" y="{y}" width="226" height="66" rx="12" fill="#ffffff" stroke="{LINE}"/>
      <text x="34" y="{y + 27}" fill="{INK}" font-size="14" font-weight="700">{escape(title)}</text>
      <text x="34" y="{y + 48}" fill="{MUTED}" font-size="12">{escape(detail)}</text>"""
            )
        groups.append(
            f"""
    <g transform="translate({x} 82)">
      <rect width="258" height="338" rx="18" fill="{background}" stroke="{LINE}"/>
      <text x="18" y="34" fill="{BLUE_DARK}" font-size="11" font-weight="750" letter-spacing="0.9">{escape(heading)}</text>
      {''.join(node_markup)}
    </g>"""
        )
    arrows = "".join(
        f'<path d="M {start} 256 H {start + 30}" stroke="{BLUE}" stroke-width="3" marker-end="url(#arrow)"/>'
        for start in (306, 588, 870)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="500" viewBox="0 0 1200 500" role="img" aria-labelledby="title desc">
  <title id="title">Production-oriented lifecycle analytics architecture</title>
  <desc id="desc">Data flows from product events and consent through Snowflake and dbt, then Hightouch and Braze, before experiment measurement and decision reporting.</desc>
  <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="{BLUE}"/></marker></defs>
  <rect width="1200" height="500" rx="20" fill="#ffffff"/>
  <text x="48" y="46" fill="{INK}" font-family="{FONT}" font-size="27" font-weight="750">Warehouse-to-activation architecture</text>
  <text x="48" y="72" fill="{MUTED}" font-family="{FONT}" font-size="14">Local execution uses SQLite; the documented production boundary maps the same contracts to Snowflake, dbt, Hightouch and Braze.</text>
  <g font-family="{FONT}">{''.join(groups)}{arrows}</g>
  <text x="48" y="468" fill="{MUTED}" font-family="{FONT}" font-size="13">Ownership is explicit: analytics defines semantics, engineering operates models, lifecycle owns the journey, and Privacy approves policy.</text>
</svg>"""


def build_readme_assets() -> list[Path]:
    ensure_directories()
    metrics, funnel, quality_passed, event_count = _load_inputs()
    return [
        _write_svg("project-overview.svg", _project_overview(metrics, funnel, quality_passed, event_count)),
        _write_svg("audience-funnel.svg", _audience_funnel(funnel)),
        _write_svg("experiment-results.svg", _experiment_results(metrics)),
        _write_svg("system-architecture.svg", _system_architecture()),
    ]
