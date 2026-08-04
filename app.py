from flask import Flask, render_template, request, jsonify
from supabase import create_client
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import sys
import plotly.express as px
import plotly.graph_objects as go
import plotly
import json
from collections import Counter
from pathlib import Path

load_dotenv()

# ── Startup env validation ─────────────────────────────────────
REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_KEY", "SECRET_KEY")
_missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
if _missing:
    raise SystemExit(f"Missing required environment variables: {', '.join(_missing)}")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["WTF_CSRF_TIME_LIMIT"] = 3600

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)

# Shared location helpers
_scraper_path = Path(__file__).resolve().parent / "scraper"
if str(_scraper_path) not in sys.path:
    sys.path.insert(0, str(_scraper_path))
from location_utils import matches_country, normalize_country  # noqa: E402
from analytics.ml_model import train_model, predict_salary


def count_by_country(jobs, keyword):
    """Count jobs whose location/country match a keyword via shared aliases."""
    return len([
        j for j in jobs
        if matches_country(j.get("location"), keyword, j.get("country"))
    ])


CURRENCY_SYMBOLS = {
    "GBP": "£",
    "USD": "$",
    "EUR": "€",
    "INR": "₹",
    "PKR": "₨",
    "BDT": "৳",
    "CAD": "C$",
    "AUD": "A$",
}


def format_salary(amount, currency=None):
    if amount is None:
        return "N/A"
    try:
        n = int(float(amount))
    except (TypeError, ValueError):
        return "N/A"
    sym = CURRENCY_SYMBOLS.get((currency or "GBP").upper(), (currency or "£") + " ")
    return f"{sym}{n:,}"


@app.context_processor
def inject_globals():
    """Nav job count + salary formatter available in all templates."""
    count = 0
    try:
        result = supabase.table("jobs").select("id", count="exact").limit(1).execute()
        # Prefer exact count from response if available
        count = getattr(result, "count", None)
        if count is None:
            count = len(result.data or [])
    except Exception as e:
        app.logger.warning("inject_job_count failed: %s", e)
        count = 0
    return dict(nav_job_count=count, format_salary=format_salary)


@app.route("/health")
@app.route("/healthz")
def health():
    try:
        supabase.table("jobs").select("id").limit(1).execute()
        return jsonify(status="ok"), 200
    except Exception as e:
        return jsonify(status="error", detail=str(e)), 503


@app.route("/")
def dashboard():
    try:
        result = supabase.table("jobs").select("*").execute()
        jobs = result.data or []
    except Exception as e:
        app.logger.error("dashboard fetch failed: %s", e)
        jobs = []

    total_jobs = len(jobs)

    all_skills = []
    for job in jobs:
        all_skills.extend(job.get("skills") or [])
    skill_counts = Counter(all_skills).most_common(10)

    # Segment salary stats by currency to avoid mixing £ and PKR etc.
    salaries_by_currency = {}
    for j in jobs:
        try:
            val = float(j.get("salary_min"))
            if val <= 1000:
                continue
        except (TypeError, ValueError):
            continue
        cur = (j.get("currency") or "GBP").upper()
        salaries_by_currency.setdefault(cur, []).append(val)

    # Prefer GBP for headline avg when available, else largest sample
    primary_currency = "GBP"
    if primary_currency not in salaries_by_currency and salaries_by_currency:
        primary_currency = max(salaries_by_currency, key=lambda c: len(salaries_by_currency[c]))
    primary_sals = salaries_by_currency.get(primary_currency, [])
    avg_salary = round(sum(primary_sals) / len(primary_sals)) if primary_sals else 0
    avg_salary_currency = primary_currency if primary_sals else None
    salary_coverage = round(100 * sum(len(v) for v in salaries_by_currency.values()) / total_jobs) if total_jobs else 0

    locations = [j["location"] for j in jobs if j.get("location")]
    location_counts = Counter(locations).most_common(5)

    last_updated = None
    if jobs:
        dates = [j.get("scraped_at") for j in jobs if j.get("scraped_at")]
        if dates:
            last_updated = max(dates)[:10]

    pakistan_jobs = count_by_country(jobs, "pakistan")
    india_jobs = count_by_country(jobs, "india")
    bangladesh_jobs = count_by_country(jobs, "bangladesh")
    remote_jobs = count_by_country(jobs, "remote")
    uk_jobs = count_by_country(jobs, "united kingdom")
    canada_jobs = count_by_country(jobs, "canada")
    australia_jobs = count_by_country(jobs, "australia")
    germany_jobs = count_by_country(jobs, "germany")

    # Prefer job_type column when present
    if any(j.get("job_type") for j in jobs):
        remote_jobs = len([j for j in jobs if (j.get("job_type") or "") == "remote"])
        onsite_jobs = len([j for j in jobs if (j.get("job_type") or "") in ("onsite", "hybrid")])
    else:
        onsite_jobs = len([j for j in jobs if "remote" not in (j.get("location") or "").lower()])

    category_counts = Counter([j["category"] for j in jobs if j.get("category")]).most_common(8)

    skill_salary = {}
    skill_salary_count = {}
    for job in jobs:
        try:
            sal = float(job.get("salary_min"))
            if sal < 1000:
                continue
        except (TypeError, ValueError):
            continue
        # Only aggregate GBP (or primary) to avoid cross-currency averages
        cur = (job.get("currency") or "GBP").upper()
        if cur != primary_currency:
            continue
        for skill in (job.get("skills") or []):
            skill_salary[skill] = skill_salary.get(skill, 0) + sal
            skill_salary_count[skill] = skill_salary_count.get(skill, 0) + 1

    skill_avg_salary = {
        skill: round(skill_salary[skill] / skill_salary_count[skill])
        for skill in skill_salary
        if skill_salary_count[skill] >= 3
    }
    skill_avg_salary = dict(sorted(skill_avg_salary.items(), key=lambda x: x[1], reverse=True)[:10])

    # ── Charts ─────────────────────────────────────────────────
    skills_df_data = {"Skill": [s[0] for s in skill_counts], "Jobs": [s[1] for s in skill_counts]}
    fig_skills = px.bar(
        skills_df_data, x="Jobs", y="Skill", orientation="h",
        title="Top Skills in Demand", color_discrete_sequence=["#c9a84c"],
    )
    fig_skills.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#c9a84c",
        yaxis=dict(autorange="reversed", categoryorder="total ascending"),
    )
    chart_skills = json.dumps(fig_skills, cls=plotly.utils.PlotlyJSONEncoder)

    loc_data = {"Location": [l[0] for l in location_counts], "Jobs": [l[1] for l in location_counts]}
    fig_loc = px.bar(
        loc_data, x="Location", y="Jobs",
        title="Top Hiring Locations", color_discrete_sequence=["#1D9E75"],
    )
    fig_loc.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#1D9E75",
    )
    chart_location = json.dumps(fig_loc, cls=plotly.utils.PlotlyJSONEncoder)

    salary_data = primary_sals
    if salary_data:
        fig_salary = go.Figure(data=[go.Histogram(x=salary_data, nbinsx=20, marker_color="#7F77DD")])
        fig_salary.update_layout(
            title=f"Salary Distribution — {primary_currency} ({len(salary_data)} jobs)",
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#7F77DD",
            showlegend=False,
            xaxis_title=f"Salary ({primary_currency}/year)",
            yaxis_title="Number of Jobs",
        )
    else:
        fig_salary = go.Figure()
        fig_salary.update_layout(
            title="Salary Distribution — No salary data available",
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#7F77DD",
            annotations=[dict(
                text="Most remote jobs don't list salary publicly",
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(color="#555", size=14),
            )],
        )
    chart_salary = json.dumps(fig_salary, cls=plotly.utils.PlotlyJSONEncoder)

    cat_data = {"Category": [c[0] for c in category_counts], "Jobs": [c[1] for c in category_counts]}
    fig_cat = px.bar(
        cat_data, x="Category", y="Jobs",
        title="Jobs by Category", color_discrete_sequence=["#D85A30"],
    )
    fig_cat.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#D85A30",
    )
    chart_category = json.dumps(fig_cat, cls=plotly.utils.PlotlyJSONEncoder)

    if skill_avg_salary:
        fig_skill_sal = px.bar(
            x=list(skill_avg_salary.values()),
            y=list(skill_avg_salary.keys()),
            orientation="h",
            title=f"Average Salary by Skill ({primary_currency}/year)",
            color_discrete_sequence=["#1D9E75"],
        )
        fig_skill_sal.update_layout(
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#1D9E75",
            yaxis=dict(autorange="reversed"),
            xaxis_title=f"Avg Salary ({primary_currency}/year)",
            yaxis_title="Skill", showlegend=False,
        )
    else:
        fig_skill_sal = go.Figure()
        fig_skill_sal.update_layout(
            title="Average Salary by Skill — Not enough data yet",
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#1D9E75",
            annotations=[dict(
                text="Run scraper with more salary-inclusive sources",
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(color="#555", size=13),
            )],
        )
    chart_skill_salary = json.dumps(fig_skill_sal, cls=plotly.utils.PlotlyJSONEncoder)

    fig_remote = px.pie(
        values=[remote_jobs, onsite_jobs],
        names=["Remote", "Onsite/Hybrid"],
        title="Remote vs Onsite Jobs",
        color_discrete_sequence=["#c9a84c", "#1D9E75"],
    )
    fig_remote.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#c9a84c", showlegend=True,
    )
    chart_remote = json.dumps(fig_remote, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template(
        "dashboard.html",
        total_jobs=total_jobs,
        skill_counts=skill_counts,
        avg_salary=avg_salary,
        avg_salary_currency=avg_salary_currency,
        salary_coverage=salary_coverage,
        location_counts=location_counts,
        last_updated=last_updated,
        jobs=jobs[:5],
        pakistan_jobs=pakistan_jobs,
        india_jobs=india_jobs,
        bangladesh_jobs=bangladesh_jobs,
        remote_jobs=remote_jobs,
        uk_jobs=uk_jobs,
        canada_jobs=canada_jobs,
        australia_jobs=australia_jobs,
        germany_jobs=germany_jobs,
        chart_skills=chart_skills,
        chart_location=chart_location,
        chart_salary=chart_salary,
        chart_category=chart_category,
        chart_skill_salary=chart_skill_salary,
        chart_remote=chart_remote,
    )


@app.route("/jobs")
def jobs_page():
    q = (request.args.get("q") or request.args.get("search") or "")[:100].strip()
    country = (request.args.get("country") or request.args.get("location") or "")[:100].strip()
    category = (request.args.get("category") or "")[:100].strip()
    sort_by = (request.args.get("sort") or "newest")[:20].strip()
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        page = 1
    per_page = 20

    try:
        result = supabase.table("jobs").select("*").order("scraped_at", desc=True).execute()
        all_jobs = result.data or []
    except Exception as e:
        app.logger.error("jobs_page fetch failed: %s", e)
        all_jobs = []

    if q:
        q_lower = q.lower()

        def matches_search(job):
            title = str(job.get("title") or "").lower()
            company = str(job.get("company") or "").lower()
            loc = str(job.get("location") or "").lower()
            skills = job.get("skills") or []
            if isinstance(skills, str):
                skills_text = skills.lower()
            else:
                skills_text = " ".join(str(s).lower() for s in skills)
            return (
                q_lower in title
                or q_lower in company
                or q_lower in loc
                or q_lower in skills_text
            )

        all_jobs = [j for j in all_jobs if matches_search(j)]

    if country:
        all_jobs = [
            j for j in all_jobs
            if matches_country(j.get("location"), country, j.get("country"))
        ]

    if category:
        cat_lower = category.lower()
        all_jobs = [
            j for j in all_jobs
            if cat_lower in str(j.get("category") or "").lower()
        ]

    if sort_by == "salary_high":
        all_jobs = sorted(
            all_jobs,
            key=lambda j: float(j.get("salary_min") or 0),
            reverse=True,
        )
    elif sort_by == "salary_low":
        all_jobs = sorted(
            all_jobs,
            key=lambda j: float(j.get("salary_min") or 0),
        )

    total_jobs = len(all_jobs)
    total_pages = max(1, (total_jobs + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    jobs = all_jobs[start:start + per_page]

    static_countries = [
        "Pakistan", "India", "Bangladesh",
        "United Kingdom", "UK", "USA", "United States",
        "Canada", "Australia", "Germany",
        "Remote", "Remote Worldwide",
    ]
    from_data = sorted({
        str(j.get("country") or "").strip()
        for j in (result.data or [])
        if j.get("country")
    }) if "result" in dir() else []
    available_countries = list(dict.fromkeys(static_countries + from_data))

    return render_template(
        "jobs.html",
        jobs=jobs,
        total_jobs=total_jobs,
        total_pages=total_pages,
        current_page=page,
        page=page,
        query=q,
        search=q,
        selected_country=country,
        location=country,
        category=category,
        sort_by=sort_by,
        available_countries=available_countries,
    )


@app.route("/job/<job_id>")
def job_detail(job_id):
    try:
        result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    except Exception as e:
        app.logger.error("job_detail failed: %s", e)
        return render_template("404.html"), 404
    if not result.data:
        return render_template("404.html"), 404
    job = result.data[0]
    return render_template("job_detail.html", job=job)


# Simple in-process model cache (avoids full retrain on every GET)
_model_cache = {"model": None, "mlb": None, "avg": None, "currency": None, "n_jobs": 0}


@app.route("/predict", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def predict():
    predicted_salary = None
    selected_skills = []
    location = ""
    prediction_currency = None

    try:
        result = supabase.table("jobs").select("*").execute()
        jobs = result.data or []
    except Exception as e:
        app.logger.error("predict fetch failed: %s", e)
        jobs = []

    # Retrain only when job count changes (or cache empty)
    n = len(jobs)
    if _model_cache["model"] is None or _model_cache["n_jobs"] != n:
        model, mlb, avg_sal, currency_used = train_model(jobs)
        _model_cache.update(
            model=model, mlb=mlb, avg=avg_sal, currency=currency_used, n_jobs=n
        )
    else:
        model = _model_cache["model"]
        mlb = _model_cache["mlb"]
        currency_used = _model_cache["currency"]

    prediction_currency = currency_used

    if request.method == "POST":
        selected_skills = request.form.getlist("skills")
        location = (request.form.get("location") or "")[:100]
        if model and selected_skills:
            predicted_salary = predict_salary(model, mlb, selected_skills, location)
        else:
            predicted_salary = None

    from scraper.skills import SKILLS_LIST
    return render_template(
        "predict.html",
        skills_list=SKILLS_LIST,
        available_skills=SKILLS_LIST,
        prediction=predicted_salary,
        predicted_salary=predicted_salary,
        prediction_currency=prediction_currency,
        selected_skills=selected_skills,
        location=location,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(429)
def rate_limited(e):
    return render_template("404.html"), 429


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)
