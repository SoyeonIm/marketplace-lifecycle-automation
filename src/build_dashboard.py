from __future__ import annotations

import html
import json
import sqlite3
from pathlib import Path

from src.config import DATABASE_PATH, REPORTS_DIR, ensure_directories


def _format_pct(value: float) -> str:
    return f"{value:.2f}%"


def _format_p_value(value: float) -> str:
    return "&lt;0.0001" if value < 0.0001 else f"{value:.4f}"


def build_dashboard() -> Path:
    ensure_directories()
    metrics = json.loads((REPORTS_DIR / "experiment_metrics.json").read_text(encoding="utf-8"))
    quality = json.loads((REPORTS_DIR / "data_quality.json").read_text(encoding="utf-8"))

    connection = sqlite3.connect(DATABASE_PATH)
    try:
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
        category_rows = connection.execute(
            """
                SELECT COALESCE(preferred_category, 'Unknown') AS category, COUNT(*) AS members
                FROM mart_campaign_eligible_audience
                GROUP BY COALESCE(preferred_category, 'Unknown')
                ORDER BY members DESC
            """
        ).fetchall()
    finally:
        connection.close()

    arms = metrics["arms"]
    comparisons = metrics["comparisons_vs_control"]
    total_audience = sum(arm["assigned_members"] for arm in arms.values())
    best_name = metrics["decision"]["best_observed_variant"]
    best = comparisons[best_name]
    randomization = metrics["randomization_diagnostics"]
    power_plan = metrics["power_plan"]
    max_conversion = max(arm["conversion_rate"] for arm in arms.values()) * 1.20
    quality_passed = sum(check["status"] == "PASS" for check in quality)

    conversion_bars = "".join(
        f"""
        <div class="bar-row">
          <div class="bar-label">{html.escape(name.title())}</div>
          <div class="bar-track"><div class="bar {name}" style="width:{arm['conversion_rate'] / max_conversion * 100:.1f}%"></div></div>
          <div class="bar-value">{arm['conversion_rate'] * 100:.2f}%</div>
        </div>
        """
        for name, arm in sorted(arms.items())
    )

    funnel_max = funnel[0]["count"]
    funnel_html = "".join(
        f"""
        <div class="funnel-row">
          <div><strong>{html.escape(item['label'])}</strong><span>{item['count']:,}</span></div>
          <div class="funnel-track"><div style="width:{item['count'] / funnel_max * 100:.1f}%"></div></div>
        </div>
        """
        for item in funnel
    )

    result_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(name.title())}</td>
          <td>{arms[name]['assigned_members']:,}</td>
          <td>{arms[name]['conversion_rate'] * 100:.2f}%</td>
          <td>{comparison['absolute_uplift_pp']:.2f} pp</td>
          <td>{comparison['ci_95_low_pp']:.2f} to {comparison['ci_95_high_pp']:.2f} pp</td>
          <td>{_format_p_value(comparison['bonferroni_p_value'])}</td>
          <td>{comparison['guardrail_unsubscribe_rate_pct']:.2f}%</td>
          <td>{comparison['estimated_roi_pct']:.1f}%</td>
        </tr>
        """
        for name, comparison in comparisons.items()
    )

    category_max = max(count for _, count in category_rows)
    category_html = "".join(
        f"""
        <div class="category-row">
          <span>{html.escape(category)}</span>
          <div><i style="width:{count / category_max * 100:.1f}%"></i></div>
          <b>{count:,}</b>
        </div>
        """
        for category, count in category_rows
    )

    dashboard = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Marketplace Seller Reactivation | Campaign Analytics</title>
  <style>
    :root {{ --ink:#17212b; --muted:#687583; --line:#dfe5ea; --blue:#087ec7; --orange:#f6a800; --green:#14845c; --bg:#f4f7f9; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--bg); font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    header {{ color:white; padding:46px 7vw 38px; background:linear-gradient(125deg,#075f9e,#0a8ed7 62%,#f6a800 160%); }}
    header p {{ max-width:820px; margin:10px 0 0; color:#dcedf8; line-height:1.55; }}
    h1 {{ margin:0; font-size:clamp(30px,4vw,48px); letter-spacing:-1.2px; }}
    h2 {{ margin:0 0 18px; font-size:22px; }}
    .eyebrow {{ color:#f9c548; text-transform:uppercase; letter-spacing:.12em; font-weight:750; font-size:12px; margin-bottom:10px; }}
    main {{ width:min(1180px,92vw); margin:-20px auto 54px; }}
    .grid {{ display:grid; gap:18px; }}
    .kpis {{ grid-template-columns:repeat(4,1fr); }}
    .two {{ grid-template-columns:1.15fr .85fr; margin-top:18px; }}
    .card {{ background:white; border:1px solid var(--line); border-radius:14px; box-shadow:0 5px 22px rgba(26,50,71,.07); padding:24px; }}
    .kpi .label {{ font-size:13px; color:var(--muted); font-weight:650; }}
    .kpi .value {{ font-size:32px; font-weight:780; margin:7px 0 4px; letter-spacing:-.7px; }}
    .kpi .note {{ font-size:12px; color:var(--muted); line-height:1.4; }}
    .decision {{ margin-top:18px; border-left:5px solid var(--green); }}
    .decision strong {{ color:var(--green); }}
    .bar-row {{ display:grid; grid-template-columns:110px 1fr 64px; gap:12px; align-items:center; margin:17px 0; }}
    .bar-label,.bar-value {{ font-size:13px; font-weight:700; }}
    .bar-value {{ text-align:right; }}
    .bar-track {{ height:20px; background:#edf1f4; border-radius:20px; overflow:hidden; }}
    .bar {{ height:100%; border-radius:20px; background:#9aa8b3; }}
    .bar.generic {{ background:var(--blue); }} .bar.personalized {{ background:var(--orange); }}
    .funnel-row {{ margin:12px 0; }}
    .funnel-row>div:first-child {{ display:flex; justify-content:space-between; font-size:13px; }}
    .funnel-row span {{ color:var(--muted); }}
    .funnel-track {{ height:8px; border-radius:8px; background:#edf1f4; margin-top:6px; overflow:hidden; }}
    .funnel-track div {{ height:100%; background:linear-gradient(90deg,var(--blue),#43a8df); border-radius:8px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th {{ color:var(--muted); text-align:left; font-weight:700; border-bottom:1px solid var(--line); padding:11px 9px; }}
    td {{ border-bottom:1px solid #edf1f4; padding:13px 9px; white-space:nowrap; }}
    .table-wrap {{ overflow-x:auto; }}
    .category-row {{ display:grid; grid-template-columns:120px 1fr 50px; align-items:center; gap:10px; font-size:12px; margin:11px 0; }}
    .category-row div {{ height:9px; background:#edf1f4; border-radius:9px; overflow:hidden; }}
    .category-row i {{ display:block; height:100%; background:var(--orange); border-radius:9px; }}
    .category-row b {{ text-align:right; }}
    .method {{ color:var(--muted); font-size:12px; line-height:1.6; margin-top:16px; }}
    footer {{ color:var(--muted); text-align:center; font-size:12px; padding:12px 0 30px; }}
    @media(max-width:850px) {{ .kpis,.two {{ grid-template-columns:1fr 1fr; }} }}
    @media(max-width:560px) {{ .kpis,.two {{ grid-template-columns:1fr; }} header {{ padding-left:5vw; padding-right:5vw; }} }}
  </style>
</head>
<body>
  <header>
    <div class="eyebrow">Synthetic lifecycle analytics · August 2026</div>
    <h1>Seller Reactivation Campaign</h1>
    <p>An end-to-end lifecycle analytics project: governed audience creation, randomized campaign testing, incrementality, customer guardrails and commercial decisioning.</p>
  </header>
  <main>
    <section class="grid kpis">
      <article class="card kpi"><div class="label">Eligible audience</div><div class="value">{total_audience:,}</div><div class="note">After consent, suppression, recency and campaign-conflict rules</div></article>
      <article class="card kpi"><div class="label">Best absolute uplift</div><div class="value">{best['absolute_uplift_pp']:.2f} pp</div><div class="note">{html.escape(best_name.title())} versus randomized control</div></article>
      <article class="card kpi"><div class="label">Estimated incremental listings</div><div class="value">{best['incremental_listings_estimate']:.1f}</div><div class="note">Intention-to-treat estimate within 14 days</div></article>
      <article class="card kpi"><div class="label">Data quality</div><div class="value">{quality_passed}/{len(quality)}</div><div class="note">Automated integrity, consent and campaign-safety checks passed</div></article>
    </section>

    <section class="card decision">
      <h2>Decision</h2>
      <p><strong>{'Staged rollout recommended.' if metrics['decision']['rollout_ready'] else 'More evidence required.'}</strong> {html.escape(metrics['decision']['recommendation'])}</p>
    </section>

    <section class="grid two">
      <article class="card"><h2>14-day listing conversion</h2>{conversion_bars}<p class="method">Primary KPI: at least one listing created within 14 days. Open and click metrics are diagnostic, not the decision metric.</p></article>
      <article class="card"><h2>Governed audience funnel</h2>{funnel_html}</article>
    </section>

    <section class="card" style="margin-top:18px">
      <h2>Incrementality, guardrails and scenario ROI</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>Variant</th><th>Members</th><th>Conversion</th><th>Uplift</th><th>95% CI</th><th>Adj. p</th><th>Unsubscribe</th><th>ROI</th></tr></thead>
        <tbody>{result_rows}</tbody>
      </table></div>
      <p class="method">ROI uses a synthetic NZ${metrics['commercial_assumptions']['value_per_incremental_listing_nzd']:.2f} value per incremental listing plus illustrative campaign costs. It demonstrates the decision framework and is not real company financial data.</p>
    </section>

    <section class="grid two">
      <article class="card"><h2>Audience by recent category signal</h2>{category_html}</article>
      <article class="card"><h2>Measurement design</h2>
        <ul class="method">
          <li>Random assignment across control, generic and personalized arms</li>
          <li>Two-sided two-proportion z-tests</li>
          <li>Newcombe 95% score intervals for absolute uplift</li>
          <li>Bonferroni correction for two treatment comparisons</li>
          <li>SRM p-value: {_format_p_value(randomization['sample_ratio_mismatch']['p_value'])}</li>
          <li>Maximum absolute pre-treatment SMD: {randomization['pre_treatment_balance']['max_absolute_smd']:.3f}</li>
          <li>Power plan: {power_plan['observed_members_per_arm']:,} observed vs {power_plan['required_members_per_arm']:,} required per arm</li>
          <li>1% unsubscribe guardrail and persistent control discipline</li>
          <li>All source data is deterministic, fictional and privacy-safe</li>
        </ul>
      </article>
    </section>
  </main>
  <footer>Marketplace Lifecycle Automation · Synthetic data only · No real member or company data</footer>
</body>
</html>
"""

    dashboard = "\n".join(line.rstrip() for line in dashboard.splitlines()) + "\n"
    output = REPORTS_DIR / "dashboard.html"
    output.write_text(dashboard, encoding="utf-8")
    return output
