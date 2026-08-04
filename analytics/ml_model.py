"""Ridge regression salary predictor trained on current jobs table contents."""

import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from collections import Counter

import sys
from pathlib import Path

_scraper = Path(__file__).resolve().parent.parent / "scraper"
if str(_scraper) not in sys.path:
    sys.path.insert(0, str(_scraper))

from skills import SKILLS_LIST  # noqa: E402
from location_utils import normalize_country  # noqa: E402


def _pick_primary_currency(jobs_with_salary):
    """Choose the currency with the most salary samples (prefer GBP if tied-ish)."""
    counts = Counter()
    for j in jobs_with_salary:
        cur = (j.get("currency") or "GBP").upper()
        counts[cur] += 1
    if not counts:
        return "GBP"
    # Prefer GBP if it has at least 10 samples, else largest group
    if counts.get("GBP", 0) >= 10:
        return "GBP"
    return counts.most_common(1)[0][0]


def train_model(jobs, currency=None):
    """
    Train on jobs that have salary_min > 1000.
    If currency is None, auto-select the dominant currency so we never blend PKR+GBP.
    Returns (model, mlb, mean_salary, currency_used) or (None, None, None, None).
    """
    jobs_with_salary = []
    for j in jobs:
        try:
            sal = float(j.get("salary_min") or 0)
            if sal > 1000:
                jobs_with_salary.append(j)
        except (TypeError, ValueError):
            continue

    if len(jobs_with_salary) < 10:
        return None, None, None, None

    currency_used = currency or _pick_primary_currency(jobs_with_salary)
    currency_used = currency_used.upper()

    filtered = [
        j for j in jobs_with_salary
        if (j.get("currency") or "GBP").upper() == currency_used
    ]
    # Fallback: if currency column missing on legacy rows, use all salary rows
    if len(filtered) < 10:
        filtered = jobs_with_salary
        currency_used = currency_used or "GBP"

    if len(filtered) < 10:
        return None, None, None, None

    df = pd.DataFrame(filtered)
    df["salary_min"] = df["salary_min"].astype(float)
    df["skills"] = df["skills"].apply(lambda x: x if isinstance(x, list) else [])

    mlb = MultiLabelBinarizer(classes=SKILLS_LIST)
    skills_encoded = mlb.fit_transform(df["skills"])
    skills_df = pd.DataFrame(skills_encoded, columns=mlb.classes_)

    if "country" in df.columns:
        countries = df.apply(
            lambda r: normalize_country(r.get("country"))
            or normalize_country(r.get("location"))
            or "",
            axis=1,
        )
    else:
        countries = df["location"].apply(lambda loc: normalize_country(loc) or "")

    region_df = pd.DataFrame({
        "is_us": (countries == "united states").astype(int).values,
        "is_uk": (countries == "united kingdom").astype(int).values,
        "is_in": (countries == "india").astype(int).values,
        "is_pk": (countries == "pakistan").astype(int).values,
        "is_remote": (countries == "remote").astype(int).values,
    })

    X = pd.concat([skills_df.reset_index(drop=True), region_df.reset_index(drop=True)], axis=1)
    y = df["salary_min"].values

    if len(df) >= 20:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        model = Ridge(alpha=1.0)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        print(
            f"ML hold-out MAE={mae:.0f} R²={r2:.3f} "
            f"currency={currency_used} (n_train={len(X_train)}, n_test={len(X_test)})"
        )
        model.fit(X, y)
    else:
        model = Ridge(alpha=1.0)
        model.fit(X, y)

    return model, mlb, float(df["salary_min"].mean()), currency_used


def predict_salary(model, mlb, user_skills, location):
    if model is None or not user_skills:
        return 0

    skills_encoded = mlb.transform([user_skills])
    skills_df = pd.DataFrame(skills_encoded, columns=mlb.classes_)

    country = normalize_country(location) or ""
    region_df = pd.DataFrame({
        "is_us": [1 if country == "united states" else 0],
        "is_uk": [1 if country == "united kingdom" else 0],
        "is_in": [1 if country == "india" else 0],
        "is_pk": [1 if country == "pakistan" else 0],
        "is_remote": [1 if country == "remote" else 0],
    })

    X = pd.concat([skills_df, region_df], axis=1)
    prediction = model.predict(X)[0]

    if prediction < 5000:
        return 0
    return max(0, round(prediction))
