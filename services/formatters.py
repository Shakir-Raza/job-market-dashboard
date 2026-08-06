"""Shared display helpers — currency-aware salary formatting."""

from __future__ import annotations

CURRENCY_SYMBOLS = {
    "GBP": "£",
    "USD": "$",
    "EUR": "€",
    "INR": "₹",
    "PKR": "Rs ",
    "BDT": "৳",
    "CAD": "C$",
    "AUD": "A$",
}

# Ordered: check specific regions first so India never wins over Germany/UK
_REGION_CURRENCY = [
    ("germany", "EUR"),
    ("united kingdom", "GBP"),
    ("united states", "USD"),
    ("pakistan", "PKR"),
    ("bangladesh", "BDT"),
    ("australia", "AUD"),
    ("canada", "CAD"),
    ("india", "INR"),
    ("remote", "USD"),
]


def resolve_job_currency(job: dict | None) -> str:
    """
    Geography-first currency. Uses the same matches_country() logic as job filters
    so a Germany-filtered job always shows EUR, never INR from a bad DB tag.
    """
    if not job:
        return "USD"

    location = job.get("location")
    country = job.get("country")

    try:
        from location_utils import matches_country, normalize_country, currency_for_country

        for region, code in _REGION_CURRENCY:
            if matches_country(location, region, country):
                return code

        geo = normalize_country(country) or normalize_country(location)
        if geo:
            cur = currency_for_country(geo, location)
            if cur:
                return cur
    except Exception:
        pass

    blob = f"{country or ''} {location or ''}".lower()

    # Extra German / UK signals (cities, native names, ISO)
    if any(
        x in blob
        for x in (
            "germany", "deutschland", "berlin", "munich", "münchen", "muenchen",
            "hamburg", "frankfurt", "cologne", "köln", "koeln", "stuttgart",
            "düsseldorf", "dusseldorf", "leipzig", "dortmund", "essen",
            " de ", " de,", ", de",
        )
    ):
        return "EUR"
    if any(
        x in blob
        for x in (
            "united kingdom", "england", "scotland", "wales", "london",
            "manchester", "birmingham", "leeds", "bristol", "glasgow",
            "edinburgh", " uk", " u.k", ", uk",
        )
    ):
        return "GBP"
    if any(x in blob for x in ("pakistan", "karachi", "lahore", "islamabad", " pk")):
        return "PKR"
    if any(
        x in blob
        for x in (
            "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
            "chennai", "pune", "gurugram", "noida",
        )
    ):
        return "INR"
    if any(x in blob for x in ("united states", "usa", "new york", "san francisco", "seattle")):
        return "USD"

    # Stored currency last — and never trust INR/PKR if location looks European
    cur = (job.get("currency") or "").strip().upper()
    if cur in CURRENCY_SYMBOLS:
        return cur
    return "USD"


def format_salary(amount, currency=None, job=None):
    if amount is None or amount == "":
        return "N/A"
    try:
        n = int(float(amount))
    except (TypeError, ValueError):
        return "N/A"
    if n <= 0:
        return "N/A"

    if job is not None:
        code = resolve_job_currency(job)
    else:
        code = (currency or "").strip().upper() if currency else "USD"
        if code not in CURRENCY_SYMBOLS:
            code = "USD"

    sym = CURRENCY_SYMBOLS.get(code, code + " ")
    return f"{sym}{n:,}"
