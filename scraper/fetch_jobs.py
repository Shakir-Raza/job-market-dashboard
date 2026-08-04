"""Adzuna job search client with pagination and retry."""

import os
import time
from dotenv import load_dotenv

from http_utils import request_with_retry

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
API_KEY = os.getenv("ADZUNA_API_KEY")

# Valid Adzuna country indexes (no PK / BD)
VALID_COUNTRIES = {"gb", "us", "ca", "au", "de", "in", "fr", "nl", "pl", "sg", "za", "br", "mx"}


def fetch_jobs(
    what="python developer",
    where="london",
    results_per_page=20,
    page=1,
    country="gb",
    max_pages=1,
):
    """
    Fetch jobs from Adzuna.
    If max_pages > 1, loops through pages (up to max_pages) with a short delay.
    """
    country = (country or "gb").lower()
    if country not in VALID_COUNTRIES:
        print(f"Warning: Adzuna has no index for '{country}' — falling back to 'gb'")
        country = "gb"

    all_jobs = []
    for p in range(page, page + max_pages):
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{p}"
        params = {
            "app_id": APP_ID,
            "app_key": API_KEY,
            "results_per_page": min(results_per_page, 50),
            "what": what,
            "where": where,
            "content-type": "application/json",
        }

        response = request_with_retry("GET", url, params=params, timeout=15)
        if response is None or response.status_code != 200:
            if response is not None:
                print(f"Error: {response.status_code} — {response.text[:200]}")
            break

        data = response.json()
        jobs = data.get("results") or []
        print(f"Fetched {len(jobs)} jobs for '{what}' in '{where}' ({country}) page {p}")
        all_jobs.extend(jobs)

        if len(jobs) < results_per_page:
            break
        if max_pages > 1 and p < page + max_pages - 1:
            time.sleep(0.6)

    return all_jobs


if __name__ == "__main__":
    jobs = fetch_jobs(what="python developer", where="london", country="gb", max_pages=1)
    for job in jobs[:3]:
        print("---")
        print("Title:   ", job.get("title"))
        print("Company: ", (job.get("company") or {}).get("display_name"))
        print("Location:", (job.get("location") or {}).get("display_name"))
        print("Salary:  ", job.get("salary_min"), "-", job.get("salary_max"))
        print("URL:     ", job.get("redirect_url"))
