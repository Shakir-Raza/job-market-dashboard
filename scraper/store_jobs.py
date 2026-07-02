import math
import os
from supabase import create_client
from dotenv import load_dotenv
from fetch_jobs import fetch_jobs
from clean_data import clean_jobs

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def store_jobs(what, where, country="pk", page=1):
    raw = fetch_jobs(what=what, where=where, country=country, page=page)
    df  = clean_jobs(raw)

    inserted = 0
    skipped  = 0

    for _, row in df.iterrows():
        # check if job already exists by source_url
        existing = supabase.table("jobs").select("id").eq("source_url", row["source_url"]).execute()

        if existing.data:
            skipped += 1
            continue

        supabase.table("jobs").insert({
            "title":       row["title"],
            "company":     row["company"],
            "location":    row["location"],
            "salary_min":  None if (row["salary_min"] is None or (isinstance(row["salary_min"], float) and math.isnan(row["salary_min"]))) else float(row["salary_min"]),
            "salary_max":  None if (row["salary_max"] is None or (isinstance(row["salary_max"], float) and math.isnan(row["salary_max"]))) else float(row["salary_max"]),
            "skills":      row["skills"],
            "category":    row["category"],
            "source_url":  row["source_url"],
            "posted_date": row["posted_date"],
            "description": row["description"],
        }).execute()
        inserted += 1

    print(f"Done — {inserted} inserted, {skipped} skipped (duplicates)")

if __name__ == "__main__":
    # UK jobs
    store_jobs("python developer", "london", country="gb")
    store_jobs("data scientist", "london", country="gb")
    store_jobs("machine learning engineer", "london", country="gb")
    store_jobs("flask developer", "london", country="gb")
    store_jobs("data engineer", "london", country="gb")
    store_jobs("backend developer", "manchester", country="gb")
    store_jobs("ai engineer", "london", country="gb")
    # US jobs
    store_jobs("python developer", "new york", country="us")
    store_jobs("data scientist", "san francisco", country="us")
    store_jobs("machine learning engineer", "new york", country="us")
    store_jobs("software engineer", "chicago", country="us")
    store_jobs("data engineer", "seattle", country="us")
    store_jobs("backend developer", "austin", country="us")
    # Europe
    store_jobs("python developer", "berlin", country="de")
    store_jobs("data scientist", "berlin", country="de")
    store_jobs("software engineer", "amsterdam", country="nl")
    store_jobs("python developer", "amsterdam", country="nl")
    store_jobs("machine learning", "paris", country="fr")
    store_jobs("data engineer", "paris", country="fr")