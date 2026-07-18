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

from fetch_himalayas_jobs import fetch_himalayas_jobs
from clean_himalayas_jobs import clean_himalayas_jobs
from fetch_remote_jobs import fetch_remote_jobs
from clean_remote_jobs import clean_remote_jobs

def store_himalayas_jobs(keyword, country=None):
    print(f"Fetching Himalayas jobs for '{keyword}'" + (f" in {country}" if country else ""))
    raw = fetch_himalayas_jobs(keyword=keyword, country=country, limit=20)
    if not raw:
        return
    df = clean_himalayas_jobs(raw)

    inserted = 0
    skipped  = 0

    for _, row in df.iterrows():
        if not row["source_url"]:
            skipped += 1
            continue
        existing = supabase.table("jobs").select("id").eq("source_url", row["source_url"]).execute()
        if existing.data:
            skipped += 1
            continue
        supabase.table("jobs").insert({
            "title":       row["title"],
            "company":     row["company"],
            "location":    row["location"],
            "salary_min":  row["salary_min"],
            "salary_max":  row["salary_max"],
            "skills":      row["skills"],
            "category":    row["category"],
            "source_url":  row["source_url"],
            "posted_date": row["posted_date"],
            "description": row["description"],
        }).execute()
        inserted += 1

    print(f"Done — {inserted} inserted, {skipped} skipped")


def store_remotive_jobs(category="software-dev"):
    print(f"Fetching Remotive jobs for '{category}'...")
    raw = fetch_remote_jobs(category=category)
    if not raw:
        return
    df = clean_remote_jobs(raw)

    inserted = 0
    skipped  = 0

    for _, row in df.iterrows():
        if not row["source_url"]:
            skipped += 1
            continue
        existing = supabase.table("jobs").select("id").eq("source_url", row["source_url"]).execute()
        if existing.data:
            skipped += 1
            continue
        supabase.table("jobs").insert({
            "title":       row["title"],
            "company":     row["company"],
            "location":    row["location"],
            "salary_min":  None,
            "salary_max":  None,
            "skills":      row["skills"],
            "category":    row["category"],
            "source_url":  row["source_url"],
            "posted_date": row["posted_date"],
            "description": row["description"],
        }).execute()
        inserted += 1

    print(f"Done — {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    # Himalayas — Pakistan specific
    store_himalayas_jobs("python developer", country="Pakistan")
    store_himalayas_jobs("data scientist", country="Pakistan")
    store_himalayas_jobs("software engineer", country="Pakistan")
    store_himalayas_jobs("machine learning", country="Pakistan")
    store_himalayas_jobs("backend developer", country="Pakistan")

    # Himalayas — India
    store_himalayas_jobs("python developer", country="India")
    store_himalayas_jobs("data scientist", country="India")
    store_himalayas_jobs("software engineer", country="India")
    store_himalayas_jobs("machine learning", country="India")

    # Himalayas — Bangladesh
    store_himalayas_jobs("python developer", country="Bangladesh")
    store_himalayas_jobs("software engineer", country="Bangladesh")

    # Himalayas — Worldwide remote
    store_himalayas_jobs("python developer")
    store_himalayas_jobs("data scientist")
    store_himalayas_jobs("machine learning engineer")
    store_himalayas_jobs("flask developer")
    store_himalayas_jobs("backend developer")
    store_himalayas_jobs("data engineer")

    # Remotive — worldwide remote tech
    store_remotive_jobs("software-dev")
    store_remotive_jobs("data")
    store_remotive_jobs("devops-sysadmin")
    store_remotive_jobs("backend")