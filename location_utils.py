# Aliases for country matching
COUNTRY_ALIASES = {
    "pakistan": ["pakistan", "pk"],
    "india": ["india", "in"],
    "bangladesh": ["bangladesh", "bd"],
    "remote": ["remote", "worldwide", "anywhere"],
    "united kingdom": ["united kingdom", "uk", "england", "britain", "london", "manchester"],
    "canada": ["canada", "ca"],
    "australia": ["australia", "au"],
    "germany": ["germany", "de", "berlin"],
    "united states": ["united states", "usa", "us", "new york", "san francisco", "chicago", "seattle", "austin"],
}

def normalize_country(text):
    if not text:
        return ""
    return text.lower().strip()

def matches_country(location, keyword, country=None):
    """Check if a job's location or country field matches a keyword."""
    if not keyword:
        return True

    keyword_lower = keyword.lower().strip()
    location_lower = (location or "").lower()
    country_lower = (country or "").lower()

    # Direct match
    if keyword_lower in location_lower or keyword_lower in country_lower:
        return True

    # Alias match
    for canonical, aliases in COUNTRY_ALIASES.items():
        if keyword_lower == canonical or keyword_lower in aliases:
            for alias in aliases:
                if alias in location_lower or alias in country_lower:
                    return True

    return False