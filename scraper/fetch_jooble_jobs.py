"""Jooble API client (free key required). Covers Pakistan, India, Bangladesh."""

import os
from dotenv import load_dotenv

from http_utils import request_with_retry

load_dotenv()

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")


def fetch_jooble_jobs(keywords="python developer", location="Pakistan", page=1):
    if not JOOBLE_API_KEY:
        print("JOOBLE_API_KEY not set")
        return []

    url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
    payload = {
        "keywords": keywords,
        "location": location,
        "page": page,
    }
    response = request_with_retry(
        "POST",
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if response is None:
        return []
    if response.status_code == 200:
        data = response.json()
        jobs = data.get("jobs") or []
        print(f"Fetched {len(jobs)} Jooble jobs for '{keywords}' in '{location}'")
        return jobs
    print(f"Jooble error: {response.status_code} — {response.text[:200]}")
    return []
