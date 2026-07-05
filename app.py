from flask import Flask, render_template, request
from supabase import create_client
from dotenv import load_dotenv
import os
import plotly.express as px
import plotly.graph_objects as go
import plotly
import json
import pandas as pd
from analytics.ml_model import train_model, predict_salary

load_dotenv()

app = Flask(__name__)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
    
)

@app.route("/")
def dashboard():
    # fetch all jobs
    result = supabase.table("jobs").select("*").execute()
    jobs = result.data
    # train ML model
    model, mlb, avg = train_model(jobs)

    # total count
    total_jobs = len(jobs)

    # top skills
    all_skills = []
    for job in jobs:
        all_skills.extend(job.get("skills") or [])
    from collections import Counter
    skill_counts = Counter(all_skills).most_common(10)

    # avg salary
    salaries = [j["salary_min"] for j in jobs if j.get("salary_min")]
    avg_salary = round(sum(salaries) / len(salaries)) if salaries else 0

    # top locations
    locations = [j["location"] for j in jobs if j.get("location")]
    location_counts = Counter(locations).most_common(5)
    
    # Skills bar chart
    skills_df_data = {"Skill": [s[0] for s in skill_counts], "Jobs": [s[1] for s in skill_counts]}
    fig_skills = px.bar(skills_df_data, x="Jobs", y="Skill", orientation="h",
                        title="Top Skills in Demand", color_discrete_sequence=["#c9a84c"])
    fig_skills.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#1a1a1a",
                        font_color="#e8e6df", title_font_color="#c9a84c", yaxis=dict(autorange="reversed", categoryorder="total ascending"))
    chart_skills = json.dumps(fig_skills, cls=plotly.utils.PlotlyJSONEncoder)

    # Location bar chart
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
                if f > 1000:  # filter out obviously wrong values        
                    salary_data.append(f)
        except:
            pass
    print("Salary sample:", salary_data[:5])
    print("Salary count:", len(salary_data))    
    

    fig_salary = go.Figure(data=[go.Histogram(
        
        x=salary_data,
        nbinsx=20,
        marker_color="#7F77DD"
)])
    fig_salary.update_layout(
        
        title="Salary Distribution",
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#1a1a1a",
        font_color="#e8e6df",
        title_font_color="#7F77DD",
        showlegend=False,
        xaxis_title="Salary (£/year)",
        yaxis_title="Number of Jobs",
)
    
    chart_salary = json.dumps(fig_salary, cls=plotly.utils.PlotlyJSONEncoder)


    return render_template("dashboard.html",
    total_jobs=total_jobs,
    skill_counts=skill_counts,
    avg_salary=avg_salary,
    location_counts=location_counts,
    jobs=jobs[:5],
    chart_skills=chart_skills,
    chart_location=chart_location,
    chart_salary=chart_salary,
)
    
@app.route("/jobs")
def jobs_page():
    category = request.args.get("category", "")
    location = request.args.get("location", "")

    query = supabase.table("jobs").select("*").order("scraped_at", desc=True)

    if category:
        query = query.ilike("category", f"%{category}%")
    if location:
        query = query.ilike("location", f"%{location}%")

    result = query.execute()
    jobs = result.data

    return render_template("jobs.html", jobs=jobs, category=category, location=location)


@app.route("/predict", methods=["GET", "POST"])
def predict():
    prediction = None
    selected_skills = []
    location = ""

    result = supabase.table("jobs").select("*").execute()
    jobs = result.data
    model, mlb, avg_sal = train_model(jobs)

    if request.method == "POST":
        selected_skills = request.form.getlist("skills")
        location = request.form.get("location", "")
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


if __name__ == "__main__":
    app.run(debug=True)