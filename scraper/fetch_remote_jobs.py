import requests

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
        "limit": 100
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobs", [])
            print(f"Fetched {len(jobs)} remote jobs for category '{category}'")
            return jobs
        else:
            print(f"Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching remote jobs: {e}")
        return []