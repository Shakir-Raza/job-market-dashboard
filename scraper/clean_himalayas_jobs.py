"""Normalize Himalayas API job payloads."""

import re
import pandas as pd

from skills import extract_skills
from location_utils import infer_job_type, normalize_country, currency_for_country


def clean_himalayas_jobs(raw_jobs, country_hint=None):
    cleaned = []
    for job in raw_jobs:
        title = (job.get("title") or "").strip()
        company = (job.get("companyName") or "").strip()
        location = job.get("locationRestrictions", [])
        if isinstance(location, list) and location:
            location_str = ", ".join(str(x) for x in location) + " (Remote)"
        else:
            location_str = "Worldwide (Remote)"

        description = job.get("description") or ""
        clean_desc = re.sub(r"<[^>]+>", " ", description)
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        source_url = job.get("applicationLink") or job.get("url") or ""
        posted_date = job.get("createdAt") or ""
        categories = job.get("categories") or []
        category = categories[0] if categories else ""

        skills = extract_skills(f"{title} {clean_desc[:500]}")

        salary_min = None
        salary_max = None
        try:
            if job.get("salaryMin") is not None:
                salary_min = float(job["salaryMin"])
        except (TypeError, ValueError):
            pass
        try:
            if job.get("salaryMax") is not None:
                salary_max = float(job["salaryMax"])
        except (TypeError, ValueError):
            pass

        country = (
            normalize_country(country_hint)
            or normalize_country(location_str)
            or "remote"
        )
        job_type = infer_job_type(location_str, explicit="remote")
        currency = currency_for_country(country, location_str)

        cleaned.append({
            "title": title,
            "company": company,
            "location": location_str,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "skills": skills,
            "category": category,
            "source_url": source_url,
            "posted_date": posted_date,
            "description": clean_desc[:500],
            "job_type": job_type,
            "currency": currency,
            "source": "himalayas",
            "country": country,
        })

    return pd.DataFrame(cleaned)
