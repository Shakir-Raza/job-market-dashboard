"""Dashboard aggregates and Plotly chart JSON."""

from __future__ import annotations

from collections import Counter
import json

import plotly
import plotly.graph_objects as go

from location_utils import matches_country


def _empty_fig(title, color="#14b8a6", msg="No data yet"):
    fig = go.Figure()
    fig.update_layout(
        title=title,
        paper_bgcolor="#09090b",
        plot_bgcolor="#111113",
        font_color="#fafafa",
        title_font_color=color,
        annotations=[
            dict(
                text=msg,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color="#888", size=13),
            )
        ],
        height=320,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


def _to_json(fig):
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def build_dashboard_context(jobs, total_jobs):
    """Compute all dashboard template variables from a jobs list."""
    all_skills = []
    for job in jobs:
        for s in job.get("skills") or []:
            if s and str(s).strip():
                all_skills.append(str(s).strip().lower())
    skill_counts = Counter(all_skills).most_common(15)
    locations = [j["location"] for j in jobs if j.get("location")]
    location_counts = Counter(locations).most_common(5)

    salaries_by_currency = {}
    for j in jobs:
        try:
            val = float(j.get("salary_min"))
            if val < 1000:
                continue
        except (TypeError, ValueError):
            continue
        cur = (j.get("currency") or "USD").upper()
        salaries_by_currency.setdefault(cur, []).append(val)

    preferred = ["PKR", "USD", "GBP", "EUR", "CAD", "AUD", "BDT", "INR"]
    primary_currency = None
    for cur in preferred:
        if cur in salaries_by_currency and len(salaries_by_currency[cur]) >= 3:
            primary_currency = cur
            break
    if primary_currency is None and salaries_by_currency:
        primary_currency = max(salaries_by_currency, key=lambda c: len(salaries_by_currency[c]))
    if primary_currency is None:
        primary_currency = "USD"
    primary_sals = salaries_by_currency.get(primary_currency, [])
    avg_salary = round(sum(primary_sals) / len(primary_sals)) if primary_sals else 0
    avg_salary_currency = primary_currency if primary_sals else None
    salary_coverage = (
        round(100 * sum(len(v) for v in salaries_by_currency.values()) / total_jobs)
        if total_jobs
        else 0
    )

    last_updated = None
    if jobs:
        dates = [j.get("scraped_at") for j in jobs if j.get("scraped_at")]
        if dates:
            last_updated = max(dates)[:10]

    def region_count(keyword):
        n = 0
        for j in jobs:
            cfield = (j.get("country") or "").lower().strip()
            if cfield == keyword:
                n += 1
            elif matches_country(j.get("location"), keyword, j.get("country")):
                n += 1
        return n

    pakistan_jobs = region_count("pakistan")
    india_jobs = region_count("india")
    bangladesh_jobs = region_count("bangladesh")
    uk_jobs = region_count("united kingdom")
    canada_jobs = region_count("canada")
    australia_jobs = region_count("australia")
    germany_jobs = region_count("germany")

    remote_jobs = 0
    onsite_jobs = 0
    for j in jobs:
        jt = (j.get("job_type") or "").lower().strip()
        loc = (j.get("location") or "").lower()
        if jt == "remote" or (not jt and ("remote" in loc or "worldwide" in loc or "anywhere" in loc)):
            remote_jobs += 1
        elif jt in ("onsite", "hybrid"):
            onsite_jobs += 1
        elif "remote" in loc or "worldwide" in loc:
            remote_jobs += 1
        else:
            onsite_jobs += 1

    cat_counter = Counter()
    for j in jobs:
        cat = (j.get("category") or "").strip()
        if cat:
            cat_counter[cat] += 1
    category_counts = cat_counter.most_common(10)

    skill_salary_sum = {}
    skill_salary_n = {}
    for job in jobs:
        try:
            sal = float(job.get("salary_min"))
            if sal < 5000:
                continue
        except (TypeError, ValueError):
            continue
        cur = (job.get("currency") or "USD").upper()
        if cur != primary_currency:
            continue
        for skill in job.get("skills") or []:
            sk = str(skill).strip().lower()
            if not sk:
                continue
            skill_salary_sum[sk] = skill_salary_sum.get(sk, 0) + sal
            skill_salary_n[sk] = skill_salary_n.get(sk, 0) + 1

    skill_avg_salary = {
        sk: round(skill_salary_sum[sk] / skill_salary_n[sk])
        for sk in skill_salary_sum
        if skill_salary_n[sk] >= 2
    }
    skill_avg_salary = dict(
        sorted(skill_avg_salary.items(), key=lambda x: x[1], reverse=True)[:12]
    )

    # Charts
    if skill_counts:
        ordered = list(reversed(skill_counts[:12]))
        fig_skills = go.Figure(
            go.Bar(
                x=[c for _, c in ordered],
                y=[s.title() for s, _ in ordered],
                orientation="h",
                marker_color="#14b8a6",
                text=[c for _, c in ordered],
                textposition="inside",
                insidetextanchor="end",
                textfont=dict(color="#042f2e", size=11),
                hovertemplate="%{y}: %{x} jobs<extra></extra>",
            )
        )
        fig_skills.update_layout(
            title=f"Top Skills in Demand ({sum(c for _, c in skill_counts)} skill tags across {total_jobs} jobs)",
            paper_bgcolor="#09090b",
            plot_bgcolor="#111113",
            font_color="#fafafa",
            title_font_color="#14b8a6",
            xaxis=dict(
                title=dict(text="Jobs mentioning skill", standoff=12),
                automargin=True,
                gridcolor="rgba(255,255,255,0.06)",
            ),
            yaxis=dict(title="", automargin=True, tickfont=dict(size=12)),
            margin=dict(l=24, r=40, t=56, b=72),
            height=460,
            showlegend=False,
            bargap=0.25,
        )
    else:
        fig_skills = _empty_fig("Top Skills in Demand", msg="No skill tags extracted yet")
    chart_skills = _to_json(fig_skills)

    geo_rows = [
        ("Pakistan", pakistan_jobs),
        ("India", india_jobs),
        ("Bangladesh", bangladesh_jobs),
        ("United Kingdom", uk_jobs),
        ("Canada", canada_jobs),
        ("Australia", australia_jobs),
        ("Germany", germany_jobs),
        ("Remote", remote_jobs),
    ]
    geo_rows = [(n, int(c)) for n, c in geo_rows if c and c > 0]
    geo_rows.sort(key=lambda x: x[1], reverse=True)
    if geo_rows:
        fig_loc = go.Figure(
            go.Bar(
                x=[n for n, _ in geo_rows],
                y=[c for _, c in geo_rows],
                marker_color="#0d9488",
                text=[c for _, c in geo_rows],
                textposition="auto",
            )
        )
        fig_loc.update_layout(
            title="Jobs by Region",
            paper_bgcolor="#09090b",
            plot_bgcolor="#111113",
            font_color="#fafafa",
            title_font_color="#0d9488",
            xaxis_tickangle=-25,
            yaxis_title="Jobs",
            margin=dict(l=48, r=24, t=56, b=88),
            height=420,
            showlegend=False,
        )
    else:
        fig_loc = _empty_fig("Jobs by Region", "#0d9488")
    chart_location = _to_json(fig_loc)
    top_location_label = geo_rows[0][0] if geo_rows else "N/A"

    if primary_sals:
        fig_salary = go.Figure(
            go.Histogram(
                x=primary_sals,
                nbinsx=min(25, max(8, len(primary_sals) // 4)),
                marker_color="#6366f1",
            )
        )
        fig_salary.update_layout(
            title=f"Salary Distribution — {primary_currency} ({len(primary_sals)} jobs)",
            paper_bgcolor="#09090b",
            plot_bgcolor="#111113",
            font_color="#fafafa",
            title_font_color="#6366f1",
            xaxis=dict(
                title=dict(text=f"Salary ({primary_currency}/year)", standoff=12),
                automargin=True,
                gridcolor="rgba(255,255,255,0.06)",
            ),
            yaxis=dict(
                title="Number of Jobs",
                automargin=True,
                gridcolor="rgba(255,255,255,0.06)",
            ),
            showlegend=False,
            margin=dict(l=64, r=28, t=56, b=80),
            height=400,
        )
    else:
        fig_salary = _empty_fig(
            "Salary Distribution", "#6366f1", "No salary data in primary currency"
        )
    chart_salary = _to_json(fig_salary)

    if category_counts:
        cats = list(reversed(category_counts[:10]))
        fig_cat = go.Figure(
            go.Bar(
                x=[c for _, c in cats],
                y=[name[:36] for name, _ in cats],
                orientation="h",
                marker_color="#D85A30",
                text=[c for _, c in cats],
                textposition="inside",
                insidetextanchor="end",
                textfont=dict(color="#042f2e", size=11),
                hovertemplate="%{y}: %{x} jobs<extra></extra>",
            )
        )
        fig_cat.update_layout(
            title=f"Jobs by Category (top {len(cats)})",
            paper_bgcolor="#09090b",
            plot_bgcolor="#111113",
            font_color="#fafafa",
            title_font_color="#D85A30",
            xaxis=dict(
                title=dict(text="Jobs", standoff=12),
                automargin=True,
                gridcolor="rgba(255,255,255,0.06)",
            ),
            yaxis=dict(title="", automargin=True, tickfont=dict(size=11)),
            margin=dict(l=24, r=40, t=56, b=72),
            height=460,
            showlegend=False,
            bargap=0.28,
        )
    else:
        fig_cat = _empty_fig("Jobs by Category", "#D85A30")
    chart_category = _to_json(fig_cat)

    if skill_avg_salary:
        items = list(reversed(list(skill_avg_salary.items())))
        fig_skill_sal = go.Figure(
            go.Bar(
                x=[avg for _, avg in items],
                y=[sk.title() for sk, _ in items],
                orientation="h",
                marker_color="#0d9488",
                text=[f"{avg:,.0f}" for _, avg in items],
                textposition="inside",
                insidetextanchor="end",
                textfont=dict(color="#042f2e", size=11),
                hovertemplate="%{y}: %{x:,.0f} " + primary_currency + "<extra></extra>",
            )
        )
        fig_skill_sal.update_layout(
            title=f"Average Salary by Skill ({primary_currency}/year)",
            paper_bgcolor="#09090b",
            plot_bgcolor="#111113",
            font_color="#fafafa",
            title_font_color="#0d9488",
            xaxis=dict(
                title=dict(text=f"Avg ({primary_currency}/year)", standoff=12),
                automargin=True,
                gridcolor="rgba(255,255,255,0.06)",
            ),
            yaxis=dict(title="", automargin=True, tickfont=dict(size=12)),
            margin=dict(l=24, r=48, t=56, b=80),
            height=440,
            showlegend=False,
            bargap=0.28,
        )
    else:
        fig_skill_sal = _empty_fig(
            f"Average Salary by Skill ({primary_currency})",
            "#0d9488",
            "Need more jobs with both skills + salary",
        )
    chart_skill_salary = _to_json(fig_skill_sal)

    if remote_jobs + onsite_jobs > 0:
        fig_remote = go.Figure(
            go.Pie(
                values=[remote_jobs, onsite_jobs],
                labels=["Remote", "Onsite / Hybrid"],
                marker_colors=["#14b8a6", "#0d9488"],
                textinfo="percent",
                textposition="inside",
                hole=0.42,
                hovertemplate="%{label}: %{value} jobs (%{percent})<extra></extra>",
            )
        )
        fig_remote.update_layout(
            title=f"Remote vs Onsite (Remote {remote_jobs} · Onsite {onsite_jobs})",
            paper_bgcolor="#09090b",
            plot_bgcolor="#111113",
            font_color="#fafafa",
            title_font_color="#14b8a6",
            showlegend=True,
            legend=dict(
                orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5
            ),
            margin=dict(l=24, r=24, t=60, b=64),
            height=400,
        )
    else:
        fig_remote = _empty_fig("Remote vs Onsite")
    chart_remote = _to_json(fig_remote)

    return {
        "total_jobs": total_jobs,
        "skill_counts": skill_counts,
        "avg_salary": avg_salary,
        "avg_salary_currency": avg_salary_currency,
        "salary_coverage": salary_coverage,
        "location_counts": location_counts,
        "last_updated": last_updated,
        "jobs": jobs[:12],
        "pakistan_jobs": pakistan_jobs,
        "india_jobs": india_jobs,
        "bangladesh_jobs": bangladesh_jobs,
        "remote_jobs": remote_jobs,
        "onsite_jobs": onsite_jobs,
        "uk_jobs": uk_jobs,
        "canada_jobs": canada_jobs,
        "australia_jobs": australia_jobs,
        "germany_jobs": germany_jobs,
        "top_location_label": top_location_label,
        "chart_skills": chart_skills,
        "chart_location": chart_location,
        "chart_salary": chart_salary,
        "chart_category": chart_category,
        "chart_skill_salary": chart_skill_salary,
        "chart_remote": chart_remote,
    }
