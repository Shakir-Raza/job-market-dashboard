"""Single source of truth for the skill taxonomy used across cleaners and ML."""

SKILLS_LIST = [
    "python", "flask", "django", "fastapi",
    "sql", "postgresql", "mysql", "mongodb",
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "machine learning", "deep learning", "nlp",
    "javascript", "react", "node.js", "typescript",
    "docker", "kubernetes", "aws", "azure", "gcp",
    "git", "linux", "rest api", "graphql",
    "data analysis", "data science", "tableau", "power bi",
]


def extract_skills(text):
    """Scan text for known skills; return list of matches (lowercase)."""
    if not text:
        return []
    text_lower = text.lower()
    return [skill for skill in SKILLS_LIST if skill in text_lower]
