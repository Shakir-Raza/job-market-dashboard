from flask import Flask, render_template, request
from supabase import create_client
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import plotly.express as px
import plotly.graph_objects as go
import plotly
import json
from analytics.ml_model import train_model, predict_salary
from collections import Counter

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# ── Helper ────────────────────────────────
def count_by_country(jobs, keyword):
    return len([j for j in jobs if keyword.lower() in (j.get("location") or "").lower()])

# ── Context processor ─────────────────────
@app.context_processor
def inject_job_count():
    try:
        result = supabase.table("jobs").select("id", count="exact").execute()
        count = len(result.data)
    except:
        count = 0
    return dict(nav_job_count=count)

# ── Dashboard ─────────────────────────────
@app.route("/")
def dashboard():
    result = supabase.table("jobs").select("*").execute()
    jobs = result.data

    total_jobs = len(jobs)

    # skills
    all_skills = []
    for job in jobs:
        all_skills.extend(job.get("skills") or [])
    skill_counts = Counter(all_skills).most_common(10)

    # salary
    salaries = [j["salary_min"] for j in jobs if j.get("salary_min")]
    avg_salary = round(sum(salaries) / len(salaries)) if salaries else 0

    # locations
    locations = [j["location"] for j in jobs if j.get("location")]
    location_counts = Counter(locations).most_common(5)

    # last updated
    last_updated = None
    if jobs:
        dates = [j.get("scraped_at") for j in jobs if j.get("scraped_at")]
        if dates:
            last_updated = max(dates)[:10]

    # country breakdown
    pakistan_jobs   = count_by_country(jobs, "pakistan")
    india_jobs      = count_by_country(jobs, "india")
    bangladesh_jobs = count_by_country(jobs, "bangladesh")
    remote_jobs     = count_by_country(jobs, "remote")
    uk_jobs         = count_by_country(jobs, "united kingdom")
    canada_jobs     = count_by_country(jobs, "canada")
    australia_jobs  = count_by_country(jobs, "australia")
    germany_jobs    = count_by_country(jobs, "germany")
    onsite_jobs     = len([j for j in jobs if "Remote" not in (j.get("location") or "")])

    # category breakdown
    category_counts = Counter([j["category"] for j in jobs if j.get("category")]).most_common(8)

    # avg salary by skill
    skill_salary = {}
    skill_salary_count = {}
    for job in jobs:
        sal = job.get("salary_min")
        if not sal:
            continue
        try:
            sal = float(sal)
            if sal < 1000:
                continue
        except:
            continue
        for skill in (job.get("skills") or []):
            if skill not in skill_salary:
                skill_salary[skill] = 0
                skill_salary_count[skill] = 0
            skill_salary[skill] += sal
            skill_salary_count[skill] += 1

    skill_avg_salary = {
        skill: round(skill_salary[skill] / skill_salary_count[skill])
        for skill in skill_salary
        if skill_salary_count[skill] >= 3
    }
    skill_avg_salary = dict(sorted(skill_avg_salary.items(), key=lambda x: x[1], reverse=True)[:10])

    # ── Charts ────────────────────────────
    # Skills chart
    skills_df_data = {"Skill": [s[0] for s in skill_counts], "Jobs": [s[1] for s in skill_counts]}
    fig_skills = px.bar(skills_df_data, x="Jobs", y="Skill", orientation="h",
        title="Top Skills in Demand", color_discrete_sequence=["#c9a84c"])
    fig_skills.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#c9a84c",
        yaxis=dict(autorange="reversed", categoryorder="total ascending"))
    chart_skills = json.dumps(fig_skills, cls=plotly.utils.PlotlyJSONEncoder)

    # Location chart
    loc_data = {"Location": [l[0] for l in location_counts], "Jobs": [l[1] for l in location_counts]}
    fig_loc = px.bar(loc_data, x="Location", y="Jobs",
        title="Top Hiring Locations", color_discrete_sequence=["#1D9E75"])
    fig_loc.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#1D9E75")
    chart_location = json.dumps(fig_loc, cls=plotly.utils.PlotlyJSONEncoder)

    # Salary histogram
    salary_data = []
    for j in jobs:
        try:
            val = j.get("salary_min")
            if val is not None:
                f = float(val)
                if f > 1000:
                    salary_data.append(f)
        except:
            pass

    if salary_data:
        fig_salary = go.Figure(data=[go.Histogram(x=salary_data, nbinsx=20, marker_color="#7F77DD")])
        fig_salary.update_layout(
            title=f"Salary Distribution ({len(salary_data)} jobs with salary data)",
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#7F77DD",
            showlegend=False, xaxis_title="Salary (£/year)", yaxis_title="Number of Jobs")
    else:
        fig_salary = go.Figure()
        fig_salary.update_layout(
            title="Salary Distribution — No salary data available",
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#7F77DD",
            annotations=[dict(text="Most remote jobs don't list salary publicly",
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(color="#555", size=14))])
    chart_salary = json.dumps(fig_salary, cls=plotly.utils.PlotlyJSONEncoder)

    # Category chart
    cat_data = {"Category": [c[0] for c in category_counts], "Jobs": [c[1] for c in category_counts]}
    fig_cat = px.bar(cat_data, x="Category", y="Jobs",
        title="Jobs by Category", color_discrete_sequence=["#D85A30"])
    fig_cat.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#D85A30")
    chart_category = json.dumps(fig_cat, cls=plotly.utils.PlotlyJSONEncoder)

    # Avg salary by skill chart
    if skill_avg_salary:
        fig_skill_sal = px.bar(
            x=list(skill_avg_salary.values()),
            y=list(skill_avg_salary.keys()),
            orientation="h",
            title="Average Salary by Skill (£/year)",
            color_discrete_sequence=["#1D9E75"])
        fig_skill_sal.update_layout(
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#1D9E75",
            yaxis=dict(autorange="reversed"),
            xaxis_title="Avg Salary (£/year)", yaxis_title="Skill", showlegend=False)
    else:
        fig_skill_sal = go.Figure()
        fig_skill_sal.update_layout(
            title="Average Salary by Skill — Not enough data yet",
            paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
            font_color="#e8e6df", title_font_color="#1D9E75",
            annotations=[dict(text="Run scraper with more salary-inclusive sources",
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(color="#555", size=13))])
    chart_skill_salary = json.dumps(fig_skill_sal, cls=plotly.utils.PlotlyJSONEncoder)

    # Remote vs onsite pie
    fig_remote = px.pie(
        values=[remote_jobs, onsite_jobs],
        names=["Remote", "Onsite/Hybrid"],
        title="Remote vs Onsite Jobs",
        color_discrete_sequence=["#c9a84c", "#1D9E75"])
    fig_remote.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#c9a84c", showlegend=True)
    chart_remote = json.dumps(fig_remote, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template("dashboard.html",
        total_jobs=total_jobs,
        skill_counts=skill_counts,
        avg_salary=avg_salary,
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

# ── Jobs listing ──────────────────────────
@app.route("/jobs")
def jobs_page():
    # Accept both new (q/country/sort) and legacy (search/location/category) params
    q = (request.args.get("q") or request.args.get("search") or "")[:100].strip()
    country = (request.args.get("country") or request.args.get("location") or "")[:100].strip()
    category = (request.args.get("category") or "")[:100].strip()
    sort_by = (request.args.get("sort") or "newest")[:20].strip()
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        page = 1
    per_page = 20

    result = supabase.table("jobs").select("*").order("scraped_at", desc=True).execute()
    all_jobs = result.data or []

    # Search: title, company, location, skills
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

    # Country / location filter
    if country:
        c_lower = country.lower()
        aliases = {
            "uk": ["uk", "united kingdom", "england", "britain"],
            "united kingdom": ["uk", "united kingdom", "england", "britain"],
            "usa": ["usa", "united states", "us", "america"],
            "united states": ["usa", "united states", "us", "america"],
            "remote": ["remote", "worldwide", "anywhere"],
            "remote worldwide": ["remote", "worldwide", "anywhere"],
        }
        terms = aliases.get(c_lower, [c_lower])

        def matches_country(job):
            loc = str(job.get("location") or "").lower()
            ctry = str(job.get("country") or "").lower()
            blob = f"{loc} {ctry}"
            return any(t in blob for t in terms)

        all_jobs = [j for j in all_jobs if matches_country(j)]

    # Category filter (legacy)
    if category:
        cat_lower = category.lower()
        all_jobs = [
            j for j in all_jobs
            if cat_lower in str(j.get("category") or "").lower()
        ]

    # Sort
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
    # else newest — already ordered by scraped_at from Supabase; keep list order

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
    })
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

# ── Job detail ────────────────────────────
@app.route("/job/<job_id>")
def job_detail(job_id):
    result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not result.data:
        return render_template("404.html"), 404
    job = result.data[0]
    return render_template("job_detail.html", job=job)

# ── Salary predictor ──────────────────────
@app.route("/predict", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def predict():
    predicted_salary = None
    selected_skills = []
    location = ""

    result = supabase.table("jobs").select("*").execute()
    jobs = result.data
    model, mlb, avg_sal = train_model(jobs)

    if request.method == "POST":
        selected_skills = request.form.getlist("skills")
        location = request.form.get("location", "")[:100]
        if model and selected_skills:
            predicted = predict_salary(model, mlb, selected_skills, location)
            predicted_salary = predicted
        elif not selected_skills:
            predicted_salary = None

    from scraper.clean_data import SKILLS_LIST
    return render_template(
        "predict.html",
        skills_list=SKILLS_LIST,
        available_skills=SKILLS_LIST,
        prediction=predicted_salary,
        predicted_salary=predicted_salary,
        selected_skills=selected_skills,
        location=location,
    )

# ── Debug route (remove after fixing) ────
@app.route("/debug")
def debug():
    result = supabase.table("jobs").select("location").execute()
    jobs = result.data
    locations = [(j.get("location") or "") for j in jobs[:30]]
    return "<br>".join(locations)

# ── Error handlers ────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(429)
def rate_limited(e):
    return render_template("404.html"), 429

if __name__ == "__main__":
    app.run(debug=True)