import requests
import os
from dotenv import load_dotenv

load_dotenv()

APP_ID  = os.getenv("ADZUNA_APP_ID")
API_KEY = os.getenv("ADZUNA_API_KEY")

def fetch_jobs(what="python developer", where="karachi", results_per_page=20, page=1, country="pk"):
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    
    params = {
        "app_id":           APP_ID,
        "app_key":          API_KEY,
        "results_per_page": results_per_page,
        "what":             what,
        "where":            where,
        "content-type":     "application/json",
    }
    

    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        jobs = data.get("results", [])
        print(f"Fetched {len(jobs)} jobs for '{what}' in '{where}'")
        return jobs
    else:
        print(f"Error: {response.status_code} — {response.text}")
        return []


if __name__ == "__main__":
    jobs = fetch_jobs()
    for job in jobs[:3]:
        print("---")
        print("Title:   ", job.get("title"))
        print("Company: ", job.get("company", {}).get("display_name"))
        print("Location:", job.get("location", {}).get("display_name"))
        print("Salary:  ", job.get("salary_min"), "-", job.get("salary_max"))
        print("URL:     ", job.get("redirect_url"))