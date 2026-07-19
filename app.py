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
import pandas as pd
from analytics.ml_model import train_model, predict_salary
from collections import Counter

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

csrf = CSRFProtect(app)
@app.context_processor
def inject_job_count():
    try:
        result = supabase.table("jobs").select("id", count="exact").execute()
        count = len(result.data)
    except:
        count = 0
    return dict(nav_job_count=count)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

@app.route("/")
def dashboard():
    result = supabase.table("jobs").select("*").execute()
    jobs = result.data
    # last updated
    last_updated = None
    if jobs:
        dates = [j.get("scraped_at") for j in jobs if j.get("scraped_at")]
        if dates:
            last_updated = max(dates)[:10]  # just the date part YYYY-MM-DD
    model, mlb, avg = train_model(jobs)
    total_jobs = len(jobs)

    all_skills = []
    for job in jobs:
        all_skills.extend(job.get("skills") or [])
    skill_counts = Counter(all_skills).most_common(10)

    salaries = [j["salary_min"] for j in jobs if j.get("salary_min")]
    avg_salary = round(sum(salaries) / len(salaries)) if salaries else 0

    locations = [j["location"] for j in jobs if j.get("location")]
    location_counts = Counter(locations).most_common(5)
    # category breakdown
    category_counts = Counter([j["category"] for j in jobs if j.get("category")]).most_common(8)
    
    # country breakdown
    
    pakistan_jobs = len([j for j in jobs if "Pakistan" in (j.get("location") or "")])
    india_jobs = len([j for j in jobs if "India" in (j.get("location") or "")])
    bangladesh_jobs = len([j for j in jobs if "Bangladesh" in (j.get("location") or "")])
    remote_jobs = len([j for j in jobs if "Remote" in (j.get("location") or "")])
    
    # Category chart
    cat_data = {"Category": [c[0] for c in category_counts], "Jobs": [c[1] for c in category_counts]}
    fig_cat = px.bar(cat_data, x="Category", y="Jobs",                
        title="Jobs by Category", color_discrete_sequence=["#D85A30"])
    fig_cat.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
        font_color="#e8e6df", title_font_color="#D85A30"
)
    chart_category = json.dumps(fig_cat, cls=plotly.utils.PlotlyJSONEncoder)

    skills_df_data = {"Skill": [s[0] for s in skill_counts], "Jobs": [s[1] for s in skill_counts]}
    fig_skills = px.bar(skills_df_data, x="Jobs", y="Skill", orientation="h",
                        title="Top Skills in Demand", color_discrete_sequence=["#c9a84c"])
    fig_skills.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
                        font_color="#e8e6df", title_font_color="#c9a84c",
                        yaxis=dict(autorange="reversed", categoryorder="total ascending"))
    chart_skills = json.dumps(fig_skills, cls=plotly.utils.PlotlyJSONEncoder)

    loc_data = {"Location": [l[0] for l in location_counts], "Jobs": [l[1] for l in location_counts]}
    fig_loc = px.bar(loc_data, x="Location", y="Jobs",
                    title="Top Hiring Locations", color_discrete_sequence=["#1D9E75"])
    fig_loc.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
                    font_color="#e8e6df", title_font_color="#1D9E75")
    chart_location = json.dumps(fig_loc, cls=plotly.utils.PlotlyJSONEncoder)

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
        fig_salary = go.Figure(data=[go.Histogram(     
            x=salary_data,
            nbinsx=20,
            marker_color="#7F77DD"
    )])
        fig_salary.update_layout(
            title=f"Salary Distribution ({len(salary_data)} jobs with salary data)",
            paper_bgcolor="#0d0d0d",
            plot_bgcolor="#1a1a1a",
            font_color="#e8e6df",
            title_font_color="#7F77DD",
            showlegend=False,
            xaxis_title="Salary (£/year)",
            yaxis_title="Number of Jobs",
    )
    else:
        
        fig_salary = go.Figure()
        
        fig_salary.update_layout(
            
            title="Salary Distribution — No salary data available for current jobs",
            paper_bgcolor="#0d0d0d",
            plot_bgcolor="#1a1a1a",
            font_color="#e8e6df",
            title_font_color="#7F77DD",
            annotations=[dict(
                
                text="Most remote jobs don't list salary publicly",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(color="#555", size=14)
        )]
    )
    chart_salary = json.dumps(fig_salary, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template("dashboard.html",
        pakistan_jobs=pakistan_jobs,
        india_jobs=india_jobs,
        bangladesh_jobs=bangladesh_jobs,
        remote_jobs=remote_jobs,                   
        total_jobs=total_jobs,
        skill_counts=skill_counts,
        avg_salary=avg_salary,
        location_counts=location_counts,
        jobs=jobs[:5],
        chart_skills=chart_skills,
        chart_location=chart_location,
        chart_salary=chart_salary,
        category_counts=category_counts,
        chart_category=chart_category,                   
        last_updated=last_updated,
    )

@app.route("/jobs")
def jobs_page():
    # sanitize inputs
    category = request.args.get("category", "")[:100]
    location = request.args.get("location", "")[:100]
    search   = request.args.get("search", "")[:100]
    page     = int(request.args.get("page", 1))
    per_page = 20

    query = supabase.table("jobs").select("*").order("scraped_at", desc=True)

    if category:
        query = query.ilike("category", f"%{category}%")
    if location:
        query = query.ilike("location", f"%{location}%")
    
    if search:
        query = query.ilike("title", f"%{search}%")
    
    total_jobs = len(all_jobs)
    total_pages = (total_jobs + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    jobs = all_jobs[start:end]

    return render_template("jobs.html",
        jobs=jobs,
        category=category,
        location=location,
        search=search,
        page=page,
        total_pages=total_pages,
        total_jobs=total_jobs,
    )

@app.route("/jobs/<job_id>")
def job_detail(job_id):
    result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not result.data:
        return render_template("404.html"), 404
    job = result.data[0]
    return render_template("job_detail.html", job=job)

@app.route("/predict", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def predict():
    prediction = None
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
            prediction = predicted

    from scraper.clean_data import SKILLS_LIST
    return render_template("predict.html",
        skills_list=SKILLS_LIST,
        prediction=prediction,
        selected_skills=selected_skills,
        location=location
    )

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(429)
def rate_limited(e):
    return render_template("404.html"), 429

if __name__ == "__main__":
    app.run(debug=True)