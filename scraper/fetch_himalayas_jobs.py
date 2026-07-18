import requests

def fetch_himalayas_jobs(keyword="python", country=None, limit=20, page=1):
    url = "https://himalayas.app/jobs/api/search"
    params = {
        "q": keyword,
        "limit": limit,
        "page": page
    }
    if country:
        params["country"] = country

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobs", [])
            print(f"Fetched {len(jobs)} Himalayas jobs for '{keyword}'" + (f" in {country}" if country else ""))
            return jobs
        else:
            print(f"Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []