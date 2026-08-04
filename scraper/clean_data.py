"""Normalize Adzuna API job payloads into a consistent DataFrame."""

import pandas as pd

from skills import SKILLS_LIST, extract_skills  # noqa: F401 — re-export
from location_utils import infer_job_type, normalize_country, currency_for_country


def clean_jobs(raw_jobs, source="adzuna", country_hint=None):
    """Normalize raw Adzuna job list into a clean Pandas DataFrame."""
    cleaned = []
    for job in raw_jobs:
        title = (job.get("title") or "").strip()
        company = (job.get("company") or {}).get("display_name", "") or ""
        company = company.strip()
        location = (job.get("location") or {}).get("display_name", "") or ""
        location = location.strip()
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        description = job.get("description") or ""
        source_url = job.get("redirect_url") or ""
        posted_date = job.get("created") or ""
        category = (job.get("category") or {}).get("label", "") or ""

        skills = extract_skills(f"{title} {description}")
        country = normalize_country(location) or normalize_country(country_hint)
        job_type = infer_job_type(location)
        currency = currency_for_country(country, location)

        cleaned.append({
            "title": title,
            "company": company,
            "location": location,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "skills": skills,
            "category": category,
            "source_url": source_url,
            "posted_date": posted_date,
            "description": description[:500],
            "job_type": job_type,
            "currency": currency,
            "source": source,
            "country": country,
        })

    return pd.DataFrame(cleaned)


if __name__ == "__main__":
    from fetch_jobs import fetch_jobs

    raw = fetch_jobs()
    df = clean_jobs(raw)
    cols = [c for c in ["title", "company", "location", "salary_min", "skills", "job_type", "currency", "source"] if c in df.columns]
    print(df[cols].to_string())
