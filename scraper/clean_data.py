import pandas as pd

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

def clean_jobs(raw_jobs):
    cleaned = []
    for job in raw_jobs:
        title       = job.get("title", "").strip()
        company     = job.get("company", {}).get("display_name", "").strip()
        location    = job.get("location", {}).get("display_name", "").strip()
        salary_min  = job.get("salary_min")
        salary_max  = job.get("salary_max")
        description = job.get("description", "")
        source_url  = job.get("redirect_url", "")
        posted_date = job.get("created", "")
        category    = job.get("category", {}).get("label", "")

        skills = extract_skills(title + " " + description)

        cleaned.append({
            "title":       title,
            "company":     company,
            "location":    location,
            "salary_min":  salary_min,
            "salary_max":  salary_max,
            "skills":      skills,
            "category":    category,
            "source_url":  source_url,
            "posted_date": posted_date,
            "description": description[:500],
        })

    df = pd.DataFrame(cleaned)
    return df


if __name__ == "__main__":
    from fetch_jobs import fetch_jobs
    raw = fetch_jobs()
    df = clean_jobs(raw)
    print(df[["title", "company", "location", "salary_min", "skills"]].to_string())