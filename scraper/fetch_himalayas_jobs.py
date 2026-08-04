"""Himalayas.app job search client with retry."""

from http_utils import request_with_retry


def fetch_himalayas_jobs(keyword="python", country=None, limit=20, page=1):
    url = "https://himalayas.app/jobs/api/search"
    params = {
        "q": keyword,
        "limit": limit,
        "page": page,
    }
    if country:
        params["country"] = country

    response = request_with_retry("GET", url, params=params, timeout=12)
    if response is None:
        return []
    if response.status_code == 200:
        data = response.json()
        jobs = data.get("jobs") or []
        suffix = f" in {country}" if country else ""
        print(f"Fetched {len(jobs)} Himalayas jobs for '{keyword}'{suffix}")
        return jobs
    print(f"Error: {response.status_code}")
    return []
