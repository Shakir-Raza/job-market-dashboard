"""Shared location → country / region mapping used by app, scrapers, and ML."""

from __future__ import annotations

import re

# Canonical country names and common aliases (lowercase keys).
# Short codes like "in", "us", "uk", "pk" must match as whole words only.
COUNTRY_ALIASES: dict[str, list[str]] = {
    "pakistan": ["pakistan", "pk", "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad"],
    "india": ["india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune", "gurugram", "noida"],
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
    "germany": ["germany", "deutschland", "berlin", "munich", "muenchen", "münchen", "hamburg", "frankfurt", "cologne", "koeln", "köln", "stuttgart", "dusseldorf", "düsseldorf", "leipzig", "dortmund"],
    "remote": ["remote", "worldwide", "anywhere", "work from home", "wfh"],
}

# Aliases that are 1–3 chars must use word-boundary matching
_SHORT_ALIASES = {"us", "uk", "pk", "bd", "ca", "au", "de"}

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

# Display order / dedup map for country filter dropdown
COUNTRY_DISPLAY = [
    "Pakistan",
    "India",
    "Bangladesh",
    "United Kingdom",
    "United States",
    "Canada",
    "Australia",
    "Germany",
    "Remote",
]


def _alias_matches(alias: str, blob: str) -> bool:
    """Substring match for long aliases; whole-word for short codes."""
    a = alias.lower()
    if a in _SHORT_ALIASES or len(a) <= 2:
        return re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", blob) is not None
    return a in blob


def normalize_country(text: str | None) -> str | None:
    """Map free-text location/country to a canonical country key, or None."""
    if not text:
        return None
    blob = text.lower().strip()
    # Prefer longer / more specific matches first (pakistan before remote, etc.)
    # Order: check multi-word and city names before short codes
    priority = [
        "pakistan", "bangladesh", "united kingdom", "united states",
        "australia", "germany", "canada", "india", "remote",
    ]
    for canonical in priority:
        aliases = COUNTRY_ALIASES.get(canonical, [])
        if any(_alias_matches(a, blob) for a in aliases):
            return canonical
    return None


def matches_country(location: str | None, country: str | None, country_field: str | None = None) -> bool:
    """True if job location/country matches the filter country string."""
    if not country:
        return True
    c_lower = country.lower().strip()
    # Map filter label to canonical
    canonical = None
    for key, aliases in COUNTRY_ALIASES.items():
        if c_lower == key or c_lower in aliases or c_lower.replace(" ", "") == key.replace(" ", ""):
            canonical = key
            break
    if c_lower in ("uk", "u.k."):
        canonical = "united kingdom"
    if c_lower in ("usa", "u.s.", "u.s.a.", "united states of america"):
        canonical = "united states"
    if c_lower in ("remote worldwide", "worldwide"):
        canonical = "remote"

    if canonical:
        terms = COUNTRY_ALIASES[canonical]
    else:
        terms = [c_lower]

    blob = f"{location or ''} {country_field or ''}".lower()
    # Prefer country_field exact match when present
    if country_field:
        cf = country_field.lower().strip()
        if canonical and (cf == canonical or cf in COUNTRY_ALIASES.get(canonical, [])):
            return True
        if normalize_country(country_field) == canonical:
            return True
    return any(_alias_matches(t, blob) for t in terms)


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
