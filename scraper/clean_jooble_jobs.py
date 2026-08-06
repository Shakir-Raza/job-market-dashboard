"""Normalize Jooble API job payloads."""

import re
import pandas as pd

from skills import extract_skills
from location_utils import infer_job_type, normalize_country, currency_for_country


def clean_jooble_jobs(raw_jobs, location_hint=None):
    cleaned = []
    for job in raw_jobs:
        title = (job.get("title") or "").strip()
        company = (job.get("company") or "").strip()
        location = (job.get("location") or location_hint or "").strip()
        description = job.get("snippet") or job.get("description") or ""
        source_url = job.get("link") or job.get("url") or ""
        posted_date = job.get("updated") or job.get("posted") or ""
        category = job.get("type") or ""

        clean_desc = re.sub(r"<[^>]+>", " ", description)
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        skills = extract_skills(f"{title} {clean_desc}")

        salary_min = None
        salary_max = None
        salary_text = job.get("salary") or ""
        # Jooble sometimes returns free-text salary; leave numeric as None if unparseable
        if isinstance(salary_text, (int, float)):
            salary_min = float(salary_text)

        country = normalize_country(location) or normalize_country(location_hint)
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
            "description": clean_desc[:500],
            "job_type": job_type,
            "currency": currency,
            "source": "jooble",
            "country": country,
        })

    return pd.DataFrame(cleaned)
