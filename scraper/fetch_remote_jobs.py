"""Remotive remote-jobs client with retry."""

from http_utils import request_with_retry

REMOTIVE_CATEGORIES = [
    "software-dev",
    "data",
    "devops-sysadmin",
    "backend",
]


def fetch_remote_jobs(category="software-dev"):
    url = "https://remotive.com/api/remote-jobs"
    params = {
        "category": category,
        "limit": 100,
    }
    response = request_with_retry("GET", url, params=params, timeout=12)
    if response is None:
        return []
    if response.status_code == 200:
        data = response.json()
        jobs = data.get("jobs") or []
        print(f"Fetched {len(jobs)} remote jobs for category '{category}'")
        return jobs
    print(f"Error: {response.status_code}")
    return []
