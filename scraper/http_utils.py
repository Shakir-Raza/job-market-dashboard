"""Shared HTTP helpers with retry / backoff for scrapers."""

from __future__ import annotations

import time
import random
import requests


def request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: int = 15,
    **kwargs,
) -> requests.Response | None:
    """
    Perform an HTTP request with exponential backoff on transient failures.
    Retries on connection errors, timeouts, and 429 / 5xx responses.
    Returns Response on success, or None after exhausting retries.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    print(f"  retry {attempt + 1}/{max_retries} after {delay:.1f}s ({last_error})")
                    time.sleep(delay)
                    continue
                print(f"  giving up: {last_error}")
                return None
            return resp
        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                print(f"  retry {attempt + 1}/{max_retries} after {delay:.1f}s ({last_error})")
                time.sleep(delay)
            else:
                print(f"  giving up: {last_error}")
                return None
        except Exception as e:
            print(f"  unexpected error: {e}")
            return None
    return None
