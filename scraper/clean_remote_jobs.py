"""Normalize Remotive API job payloads."""

import re
import pandas as pd

from skills import extract_skills
from location_utils import infer_job_type, normalize_country, currency_for_country


def clean_remote_jobs(raw_jobs):
    cleaned = []
    for job in raw_jobs:
        title = (job.get("title") or "").strip()
        company = (job.get("company_name") or "").strip()
        location = job.get("candidate_required_location") or "Remote"
        description = job.get("description") or ""
        source_url = job.get("url") or ""
        posted_date = job.get("publication_date") or ""
        category = job.get("category") or ""
        tags = job.get("tags") or []

        clean_desc = re.sub(r"<[^>]+>", " ", description)
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        skills = extract_skills(f"{title} {' '.join(tags)} {clean_desc[:500]}")

        location_str = f"{location} (Remote)" if "remote" not in location.lower() else location
        country = normalize_country(location) or "remote"
        job_type = infer_job_type(location_str, explicit="remote")
        currency = currency_for_country(country, location_str)

        cleaned.append({
            "title": title,
            "company": company,
            "location": location_str,
            "salary_min": None,
            "salary_max": None,
            "skills": skills,
            "category": category,
            "source_url": source_url,
            "posted_date": posted_date,
            "description": clean_desc[:500],
            "job_type": job_type,
            "currency": currency,
            "source": "remotive",
            "country": country,
        })

    return pd.DataFrame(cleaned)
