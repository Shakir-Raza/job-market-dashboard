"""Shared location → country / region mapping used by app, scrapers, and ML."""

from __future__ import annotations

# Canonical country names and common aliases (lowercase keys)
COUNTRY_ALIASES: dict[str, list[str]] = {
    "pakistan": ["pakistan", "pk", "karachi", "lahore", "islamabad"],
    "india": ["india", "in", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune"],
    "bangladesh": ["bangladesh", "bd", "dhaka", "chittagong"],
    "united kingdom": [
        "united kingdom", "uk", "england", "britain", "london", "manchester",
        "birmingham", "scotland", "wales", "edinburgh", "glasgow",
    ],
    "united states": [
        "united states", "usa", "us", "america", "new york", "san francisco",
        "chicago", "seattle", "austin", "manhattan", "california", "texas",
    ],
    "canada": ["canada", "toronto", "vancouver", "montreal", "ottawa"],
    "australia": ["australia", "sydney", "melbourne", "brisbane", "perth"],
    "germany": ["germany", "berlin", "munich", "hamburg", "frankfurt"],
    "remote": ["remote", "worldwide", "anywhere", "work from home", "wfh"],
}

# Adzuna country codes we actually use
ADZUNA_COUNTRIES = {
    "gb": "united kingdom",
    "us": "united states",
    "ca": "canada",
    "au": "australia",
    "de": "germany",
    "in": "india",
}

CURRENCY_BY_COUNTRY = {
    "pakistan": "PKR",
    "india": "INR",
    "bangladesh": "BDT",
    "united kingdom": "GBP",
    "united states": "USD",
    "canada": "CAD",
    "australia": "AUD",
    "germany": "EUR",
    "remote": "USD",
}


def normalize_country(text: str | None) -> str | None:
    """Map free-text location/country to a canonical country key, or None."""
    if not text:
        return None
    blob = text.lower().strip()
    for canonical, aliases in COUNTRY_ALIASES.items():
        if any(a in blob for a in aliases):
            return canonical
    return None


def matches_country(location: str | None, country: str | None, country_field: str | None = None) -> bool:
    """True if job location/country matches the filter country string."""
    if not country:
        return True
    c_lower = country.lower().strip()
    terms = COUNTRY_ALIASES.get(c_lower, [c_lower])
    # also allow reverse lookup when user passes a display name already in aliases
    for canonical, aliases in COUNTRY_ALIASES.items():
        if c_lower == canonical or c_lower in aliases:
            terms = aliases
            break
    blob = f"{location or ''} {country_field or ''}".lower()
    return any(t in blob for t in terms)


def infer_job_type(location: str | None, explicit: str | None = None) -> str:
    """Return remote | onsite | hybrid."""
    if explicit:
        e = explicit.lower()
        if "remote" in e:
            return "remote"
        if "hybrid" in e:
            return "hybrid"
        if "onsite" in e or "on-site" in e or "office" in e:
            return "onsite"
    loc = (location or "").lower()
    if "remote" in loc or "worldwide" in loc or "anywhere" in loc:
        return "remote"
    if "hybrid" in loc:
        return "hybrid"
    return "onsite"


def currency_for_country(country: str | None, location: str | None = None) -> str:
    """Best-effort currency code for a country/location."""
    key = normalize_country(country) or normalize_country(location)
    if key:
        return CURRENCY_BY_COUNTRY.get(key, "USD")
    return "USD"
