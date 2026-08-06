from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import sys
import logging
from pathlib import Path

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_KEY", "SECRET_KEY")
_missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
if _missing:
    raise SystemExit(f"Missing required environment variables: {', '.join(_missing)}")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["WTF_CSRF_TIME_LIMIT"] = 3600
# Harden cookies in production
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.getenv("FLASK_ENV") == "production" or os.getenv("RENDER"):
    app.config["SESSION_COOKIE_SECURE"] = True

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)

# Shared helpers on path
_root = Path(__file__).resolve().parent
_scraper = _root / "scraper"
for p in (_root, _scraper):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from location_utils import matches_country  # noqa: E402
from analytics.ml_model import train_model, predict_salary  # noqa: E402
from services.db import fetch_all_jobs, fetch_job_count, fetch_job_by_id, get_supabase  # noqa: E402
from services.formatters import format_salary  # noqa: E402
from services.dashboard import build_dashboard_context  # noqa: E402


@app.context_processor
def inject_globals():
    try:
        count = fetch_job_count()
    except Exception:
        count = 0
    from services.formatters import format_salary as _fmt, resolve_job_currency

    def format_salary(amount, currency=None, job=None):
        return _fmt(amount, currency=currency, job=job)

    return dict(
        nav_job_count=count,
        format_salary=format_salary,
        resolve_job_currency=resolve_job_currency,
    )


@app.route("/health")
@app.route("/healthz")
def health():
    try:
        get_supabase().table("jobs").select("id").limit(1).execute()
        return jsonify(status="ok"), 200
    except Exception as e:
        logger.exception("health check failed")
        return jsonify(status="error", detail=str(e)[:200]), 503


@app.route("/")
def dashboard():
    try:
        jobs = fetch_all_jobs()
    except Exception as e:
        logger.error("dashboard fetch failed: %s", e)
        jobs = []
    total_jobs = fetch_job_count() or len(jobs)
    ctx = build_dashboard_context(jobs, total_jobs)
    return render_template("dashboard.html", **ctx)


def _pagination_window(current, total, width=2):
    """Return list of page numbers and None for ellipsis gaps."""
    if total <= 1:
        return [1]
    pages = set([1, total, current])
    for i in range(current - width, current + width + 1):
        if 1 <= i <= total:
            pages.add(i)
    ordered = sorted(pages)
    result = []
    prev = None
    for p in ordered:
        if prev is not None and p - prev > 1:
            result.append(None)  # ellipsis
        result.append(p)
        prev = p
    return result


@app.route("/jobs")
def jobs_page():
    q = (request.args.get("q") or request.args.get("search") or "")[:100].strip()
    country = (request.args.get("country") or request.args.get("location") or "")[:100].strip()
    category = (request.args.get("category") or "")[:100].strip()
    job_type = (request.args.get("job_type") or request.args.get("type") or "")[:20].strip().lower()
    sort_by = (request.args.get("sort") or "newest")[:20].strip()
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        page = 1
    per_page = 20

    try:
        all_jobs = fetch_all_jobs()
        raw_all = list(all_jobs)
    except Exception as e:
        app.logger.error("jobs_page fetch failed: %s", e)
        all_jobs = []
        raw_all = []

    if q:
        q_lower = q.lower()

        def matches_search(job):
            title = str(job.get("title") or "").lower()
            company = str(job.get("company") or "").lower()
            loc = str(job.get("location") or "").lower()
            skills = job.get("skills") or []
            if isinstance(skills, str):
                skills_text = skills.lower()
            else:
                skills_text = " ".join(str(s).lower() for s in skills)
            return (
                q_lower in title
                or q_lower in company
                or q_lower in loc
                or q_lower in skills_text
            )

        all_jobs = [j for j in all_jobs if matches_search(j)]

    if country:
        all_jobs = [
            j for j in all_jobs
            if matches_country(j.get("location"), country, j.get("country"))
        ]

    if job_type in ("remote", "onsite", "hybrid"):
        all_jobs = [
            j for j in all_jobs
            if (j.get("job_type") or "").lower() == job_type
            or (
                job_type == "remote"
                and "remote" in str(j.get("location") or "").lower()
            )
            or (
                job_type == "onsite"
                and "remote" not in str(j.get("location") or "").lower()
                and (j.get("job_type") or "onsite").lower() in ("onsite", "hybrid", "")
            )
        ]

    if category:
        cat_lower = category.lower()
        all_jobs = [
            j for j in all_jobs
            if cat_lower in str(j.get("category") or "").lower()
        ]

    if sort_by == "salary_high":
        all_jobs = sorted(
            all_jobs,
            key=lambda j: float(j.get("salary_min") or 0),
            reverse=True,
        )
    elif sort_by == "salary_low":
        all_jobs = sorted(
            all_jobs,
            key=lambda j: float(j.get("salary_min") or 0),
        )

    total_jobs = len(all_jobs)
    total_pages = max(1, (total_jobs + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    jobs = all_jobs[start:start + per_page]

    # Fixed dropdown — no duplicates (no UK+United Kingdom, no raw DB keys)
    available_countries = [
        "Pakistan", "India", "Bangladesh",
        "United Kingdom", "United States",
        "Canada", "Australia", "Germany", "Remote",
    ]
    page_numbers = _pagination_window(page, total_pages, width=2)

    return render_template(
        "jobs.html",
        jobs=jobs,
        total_jobs=total_jobs,
        total_pages=total_pages,
        current_page=page,
        page=page,
        page_numbers=page_numbers,
        query=q,
        search=q,
        selected_country=country,
        location=country,
        category=category,
        job_type=job_type,
        sort_by=sort_by,
        available_countries=available_countries,
    )


@app.route("/job/<job_id>")
def job_detail(job_id):
    job_id = (job_id or "")[:64]
    try:
        job = fetch_job_by_id(job_id)
    except Exception as e:
        logger.error("job_detail failed: %s", e)
        job = None
    if not job:
        return render_template("404.html"), 404
    return render_template("job_detail.html", job=job)


# In-process model cache (avoids full retrain on every request)
_model_cache = {"model": None, "mlb": None, "avg": None, "currency": None, "n_jobs": 0, "loc_key": None}


@app.route("/predict", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def predict():
    predicted_salary = None
    salary_low = None
    salary_high = None
    selected_skills = []
    custom_skills_raw = ""
    location = ""
    prediction_currency = None

    try:
        jobs = fetch_all_jobs()
    except Exception as e:
        logger.error("predict fetch failed: %s", e)
        jobs = []

    if request.method == "POST":
        selected_skills = list(request.form.getlist("skills") or [])
        custom_skills_raw = (request.form.get("custom_skills") or "")[:300]
        location = (request.form.get("location") or "")[:100]
        # Split custom skills by comma / newline
        for part in custom_skills_raw.replace("\n", ",").split(","):
            s = part.strip()
            if s and s not in selected_skills:
                selected_skills.append(s)

    # Region → training currency. Auto / mixed → USD
    loc_lower = (location or "").lower().strip()
    if not loc_lower or loc_lower in ("auto", "mixed", "auto / mixed"):
        preferred_currency = "USD"
    elif "pakistan" in loc_lower or loc_lower == "pk":
        preferred_currency = "PKR"
    elif "india" in loc_lower:
        preferred_currency = "INR"
    elif "bangladesh" in loc_lower or loc_lower == "bd":
        preferred_currency = "BDT"
    elif "united kingdom" in loc_lower or loc_lower in ("uk", "britain"):
        preferred_currency = "GBP"
    elif "united states" in loc_lower or loc_lower in ("usa", "us"):
        preferred_currency = "USD"
    elif "canada" in loc_lower:
        preferred_currency = "CAD"
    elif "australia" in loc_lower:
        preferred_currency = "AUD"
    elif "germany" in loc_lower:
        preferred_currency = "EUR"
    elif "remote" in loc_lower:
        preferred_currency = "USD"
    else:
        preferred_currency = "USD"

    try:
        from skills import SKILLS_LIST
    except Exception:
        from scraper.skills import SKILLS_LIST

    # Map free-text skills onto taxonomy where possible (case-insensitive)
    known_lower = {s.lower(): s for s in SKILLS_LIST}
    model_skills = []
    for s in selected_skills:
        key = s.lower().strip()
        if key in known_lower:
            model_skills.append(known_lower[key])
        else:
            # partial match e.g. "react.js" → "react"
            matched = False
            for k, orig in known_lower.items():
                if k in key or key in k:
                    model_skills.append(orig)
                    matched = True
                    break
            if not matched:
                # keep original lower for display; model may ignore unknown classes
                model_skills.append(key)

    n = len(jobs)
    cache_key = preferred_currency or "USD"
    if (
        _model_cache["model"] is None
        or _model_cache["n_jobs"] != n
        or _model_cache.get("loc_key") != cache_key
    ):
        model, mlb, avg_sal, currency_used = train_model(jobs, currency=preferred_currency)
        _model_cache.update(
            model=model,
            mlb=mlb,
            avg=avg_sal,
            currency=currency_used or preferred_currency,
            n_jobs=n,
            loc_key=cache_key,
        )
    else:
        model = _model_cache["model"]
        mlb = _model_cache["mlb"]
        currency_used = _model_cache["currency"]

    prediction_currency = currency_used or preferred_currency or "USD"

    if request.method == "POST":
        if model and model_skills:
            predicted_salary = predict_salary(model, mlb, model_skills, location)
            if predicted_salary and predicted_salary > 0:
                salary_low = max(0, int(round(predicted_salary * 0.85)))
                salary_high = int(round(predicted_salary * 1.15))
            else:
                predicted_salary = None
        else:
            predicted_salary = None

    return render_template(
        "predict.html",
        skills_list=SKILLS_LIST,
        available_skills=SKILLS_LIST,
        prediction=predicted_salary,
        predicted_salary=predicted_salary,
        salary_low=salary_low,
        salary_high=salary_high,
        prediction_currency=prediction_currency,
        selected_skills=selected_skills,
        custom_skills=custom_skills_raw,
        location=location,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(429)
def rate_limited(e):
    return render_template("429.html"), 429


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)
