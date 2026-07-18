import pandas as pd
import re

SKILLS_LIST = [
    "python", "flask", "django", "fastapi",
    "sql", "postgresql", "mysql", "mongodb",
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "machine learning", "deep learning", "nlp",
    "javascript", "react", "node.js", "typescript",
    "docker", "kubernetes", "aws", "azure", "gcp",
    "git", "linux", "rest api", "graphql",
    "data analysis", "data science", "tableau", "power bi",
]

def extract_skills(text):
    if not text:
        return []
    text = text.lower()
    return [skill for skill in SKILLS_LIST if skill in text]

def clean_himalayas_jobs(raw_jobs):
    cleaned = []
    for job in raw_jobs:
        title    = job.get("title", "").strip()
        company  = job.get("companyName", "").strip()
        location = job.get("locationRestrictions", [])
        if isinstance(location, list) and location:
            location_str = ", ".join(location) + " (Remote)"
        else:
            location_str = "Worldwide (Remote)"

        description = job.get("description", "") or ""
        clean_desc  = re.sub(r'<[^>]+>', ' ', description)
        clean_desc  = re.sub(r'\s+', ' ', clean_desc).strip()

        source_url  = job.get("applicationLink") or job.get("url", "")
        posted_date = job.get("createdAt", "")
        category    = job.get("categories", [""])[0] if job.get("categories") else ""

        skills = extract_skills(title + " " + clean_desc[:500])

        salary_min = None
        salary_max = None
        if job.get("salaryMin"):
            try:
                salary_min = float(job["salaryMin"])
            except:
                pass
        if job.get("salaryMax"):
            try:
                salary_max = float(job["salaryMax"])
            except:
                pass

        cleaned.append({
            "title":       title,
            "company":     company,
            "location":    location_str,
            "salary_min":  salary_min,
            "salary_max":  salary_max,
            "skills":      skills,
            "category":    category,
            "source_url":  source_url,
            "posted_date": posted_date,
            "description": clean_desc[:500],
        })

    return pd.DataFrame(cleaned)