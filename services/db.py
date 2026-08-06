"""Supabase access with light TTL caching."""

from __future__ import annotations

import os
import logging
from supabase import create_client

from services.cache import cached, cache_clear

logger = logging.getLogger(__name__)

_supabase = None

# Cache TTLs (seconds)
JOBS_TTL = int(os.getenv("CACHE_JOBS_TTL", "180"))
COUNT_TTL = int(os.getenv("CACHE_COUNT_TTL", "120"))


def get_supabase():
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")
        _supabase = create_client(url, key)
    return _supabase


def fetch_all_jobs(columns="*", order_col="scraped_at", desc=True):
    """Fetch jobs with pagination; cached briefly to ease load."""

    def _load():
        client = get_supabase()
        page_size = 1000
        all_rows = []
        start = 0
        while True:
            q = client.table("jobs").select(columns)
            if order_col:
                q = q.order(order_col, desc=desc)
            q = q.range(start, start + page_size - 1)
            result = q.execute()
            batch = result.data or []
            all_rows.extend(batch)
            if len(batch) < page_size:
                break
            start += page_size
            if start > 50000:
                break
        return all_rows

    cache_key = f"jobs:{columns}:{order_col}:{desc}"
    return cached(cache_key, JOBS_TTL, _load)


def fetch_job_count() -> int:
    def _load():
        try:
            client = get_supabase()
            result = client.table("jobs").select("id", count="exact").limit(1).execute()
            if getattr(result, "count", None) is not None:
                return int(result.count)
        except Exception as e:
            logger.warning("fetch_job_count failed: %s", e)
        return 0

    return cached("jobs:count", COUNT_TTL, _load)


def fetch_job_by_id(job_id: str):
    client = get_supabase()
    result = client.table("jobs").select("*").eq("id", job_id).limit(1).execute()
    rows = result.data or []
    return rows[0] if rows else None


def invalidate_jobs_cache():
    cache_clear("jobs:")
