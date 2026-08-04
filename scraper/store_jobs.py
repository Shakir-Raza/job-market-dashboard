"""Ingest jobs from Adzuna, Himalayas, Remotive (and optionally Jooble) into Supabase."""

from __future__ import annotations

import math
import os
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

from fetch_jobs import fetch_jobs
from clean_data import clean_jobs
from fetch_himalayas_jobs import fetch_himalayas_jobs
from clean_himalayas_jobs import clean_himalayas_jobs
from fetch_remote_jobs import fetch_remote_jobs
from clean_remote_jobs import clean_remote_jobs

load_dotenv()

_supabase_url = os.getenv("SUPABASE_URL")
_supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
if not _supabase_url or not _supabase_key:
    raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment")

supabase = create_client(_supabase_url, _supabase_key)


def _safe_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _row_payload(row) -> dict:
    """Build insert dict including optional multi-source columns."""
    return {
        "title": row.get("title"),
        "company": row.get("company"),
        "location": row.get("location"),
        "salary_min": _safe_float(row.get("salary_min")),
        "salary_max": _safe_float(row.get("salary_max")),
        "skills": list(row.get("skills") or []),
        "category": row.get("category"),
        "source_url": row.get("source_url"),
        "posted_date": row.get("posted_date"),
        "description": row.get("description"),
        "job_type": row.get("job_type"),
        "currency": row.get("currency"),
        "source": row.get("source"),
        "country": row.get("country"),
    }


def insert_dataframe(df, label: str = "jobs") -> tuple[int, int]:
    """Insert rows with per-row error handling and source_url dedup."""
    if df is None or df.empty:
        print(f"  [{label}] nothing to insert")
        return 0, 0

    inserted = 0
    skipped = 0
    for _, row in df.iterrows():
        source_url = row.get("source_url") or ""
        if not source_url:
            skipped += 1
            continue
        try:
            existing = (
                supabase.table("jobs")
                .select("id")
                .eq("source_url", source_url)
                .execute()
            )
            if existing.data:
                skipped += 1
                continue
            supabase.table("jobs").insert(_row_payload(row)).execute()
            inserted += 1
        except Exception as e:
            print(f"  insert error ({label}): {e}")
            skipped += 1
    print(f"  [{label}] {inserted} inserted, {skipped} skipped")
    return inserted, skipped


def delete_old_jobs(days: int = 30) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        supabase.table("jobs").delete().lt("scraped_at", cutoff).execute()
        print(f"Deleted jobs older than {days} days (before {cutoff[:10]})")
    except Exception as e:
        print(f"delete_old_jobs failed: {e}")


def store_jobs(what, where, country="gb", page=1, max_pages=1):
    print(f"Adzuna: '{what}' in '{where}' ({country})")
    raw = fetch_jobs(
        what=what, where=where, country=country, page=page, max_pages=max_pages
    )
    if not raw:
        return
    df = clean_jobs(raw, source="adzuna", country_hint=country)
    insert_dataframe(df, label=f"adzuna/{country}/{what}")
    time.sleep(0.5)


def store_himalayas_jobs(keyword, country=None):
    print(f"Himalayas: '{keyword}'" + (f" in {country}" if country else ""))
    raw = fetch_himalayas_jobs(keyword=keyword, country=country, limit=20)
    if not raw:
        return
    df = clean_himalayas_jobs(raw, country_hint=country)
    insert_dataframe(df, label=f"himalayas/{country or 'worldwide'}/{keyword}")
    time.sleep(0.4)


def store_remotive_jobs(category="software-dev"):
    print(f"Remotive: category '{category}'")
    raw = fetch_remote_jobs(category=category)
    if not raw:
        return
    df = clean_remote_jobs(raw)
    insert_dataframe(df, label=f"remotive/{category}")
    time.sleep(0.4)


# Optional Jooble integration (requires JOOBLE_API_KEY)
def store_jooble_jobs(keywords: str, location: str):
    """POST to Jooble if JOOBLE_API_KEY is set; otherwise no-op."""
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        print("  Jooble skipped (JOOBLE_API_KEY not set)")
        return
    try:
        from fetch_jooble_jobs import fetch_jooble_jobs
        from clean_jooble_jobs import clean_jooble_jobs
    except ImportError:
        print("  Jooble modules not present — skip")
        return

    print(f"Jooble: '{keywords}' in '{location}'")
    raw = fetch_jooble_jobs(keywords=keywords, location=location)
    if not raw:
        return
    df = clean_jooble_jobs(raw, location_hint=location)
    insert_dataframe(df, label=f"jooble/{location}/{keywords}")
    time.sleep(0.5)


if __name__ == "__main__":
    delete_old_jobs(days=30)

    # ── Adzuna — real markets (physical + remote) ──────────────
    adzuna_queries = [
        # UK
        ("python developer", "london", "gb"),
        ("data scientist", "london", "gb"),
        ("machine learning", "london", "gb"),
        ("software engineer", "manchester", "gb"),
        # US
        ("python developer", "new york", "us"),
        ("data scientist", "san francisco", "us"),
        ("software engineer", "seattle", "us"),
        # India (physical jobs available on Adzuna)
        ("python developer", "bangalore", "in"),
        ("data scientist", "hyderabad", "in"),
        ("software engineer", "mumbai", "in"),
        # Canada / Australia / Germany
        ("python developer", "toronto", "ca"),
        ("python developer", "sydney", "au"),
        ("software engineer", "berlin", "de"),
    ]
    for what, where, country in adzuna_queries:
        store_jobs(what, where, country=country, max_pages=1)

    # ── Himalayas — Pakistan / India / Bangladesh + remote ─────
    # Broad IT coverage for Pakistan (remote-friendly roles)
    pk_himalayas_kws = (
        "python developer", "data scientist", "software engineer", "machine learning",
        "backend developer", "frontend developer", "full stack", "web developer",
        "mobile developer", "react", "nodejs", "devops", "blockchain", "solidity",
        "flutter", "android", "ios", "qa engineer", "cyber security", "cloud engineer",
        "data engineer", "php developer", "java developer", "dotnet",
    )
    for kw in pk_himalayas_kws:
        store_himalayas_jobs(kw, country="Pakistan")

    for kw in ("python developer", "data scientist", "software engineer", "machine learning", "blockchain"):
        store_himalayas_jobs(kw, country="India")
    for kw in ("python developer", "software engineer", "web developer", "blockchain"):
        store_himalayas_jobs(kw, country="Bangladesh")
    for kw in ("python developer", "data scientist", "machine learning engineer", "flask developer", "backend developer", "data engineer", "blockchain"):
        store_himalayas_jobs(kw)
    for country in ("United Kingdom", "Canada", "Australia", "Germany"):
        for kw in ("python developer", "software engineer"):
            store_himalayas_jobs(kw, country=country)

    # ── Remotive — worldwide remote ────────────────────────────
    for cat in ("software-dev", "data", "devops-sysadmin", "backend"):
        store_remotive_jobs(cat)

    # ── Jooble — heavy Pakistan IT volume + BD/IN ─────────────
    # Broader keywords (Jooble often returns 0 for narrow "python developer" in PK)
    jooble_it_keywords = (
        "software", "software engineer", "software developer", "web developer",
        "full stack", "frontend", "backend", "developer", "programmer",
        "IT", "information technology", "computer science",
        "python", "javascript", "react", "nodejs", "php", "java", "dotnet", ".net",
        "mobile", "android", "ios", "flutter", "react native",
        "blockchain", "solidity", "web3", "crypto",
        "devops", "cloud", "aws", "azure", "network",
        "data", "data scientist", "machine learning", "AI",
        "QA", "tester", "cyber security", "wordpress",
    )
    # Country + major cities (city queries often return more hits)
    jooble_pk_locations = (
        "Pakistan", "Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad",
    )
    for loc in jooble_pk_locations:
        for kw in jooble_it_keywords:
            store_jooble_jobs(kw, loc)

    for loc in ("Bangladesh", "Dhaka"):
        for kw in ("software", "developer", "web developer", "blockchain", "IT", "python"):
            store_jooble_jobs(kw, loc)

    for loc in ("India", "Bangalore", "Hyderabad", "Mumbai"):
        for kw in ("python developer", "software engineer", "data scientist", "blockchain"):
            store_jooble_jobs(kw, loc)

    print("Ingestion complete.")
