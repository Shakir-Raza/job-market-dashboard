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

def clean_remote_jobs(raw_jobs):
    cleaned = []
    for job in raw_jobs:
        title       = job.get("title", "").strip()
        company     = job.get("company_name", "").strip()
        location    = job.get("candidate_required_location") or "Remote"
        description = job.get("description", "")
        source_url  = job.get("url", "")
        posted_date = job.get("publication_date", "")
        category    = job.get("category", "")
        tags        = job.get("tags", [])

        # clean HTML from description
        clean_desc = re.sub(r'<[^>]+>', ' ', description)
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

        # extract skills from title + tags + description
        skills = extract_skills(title + " " + " ".join(tags) + " " + clean_desc[:500])

        # salary not usually provided by Remotive
        cleaned.append({
            "title":       title,
            "company":     company,
            "location":    location + " (Remote)",
            "salary_min":  None,
            "salary_max":  None,
            "skills":      skills,
            "category":    category,
            "source_url":  source_url,
            "posted_date": posted_date,
            "description": clean_desc[:500],
        })

    df = pd.DataFrame(cleaned)
    return df