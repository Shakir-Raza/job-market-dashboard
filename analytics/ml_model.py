import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import MultiLabelBinarizer
import numpy as np

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

def train_model(jobs):
    # filter jobs with salary data
    jobs_with_salary = [j for j in jobs if j.get("salary_min") and float(j.get("salary_min", 0)) > 1000]

    if len(jobs_with_salary) < 10:
        return None, None, None

    # build features
    df = pd.DataFrame(jobs_with_salary)
    df["salary_min"] = df["salary_min"].astype(float)
    df["skills"] = df["skills"].apply(lambda x: x if isinstance(x, list) else [])

    # one-hot encode skills
    mlb = MultiLabelBinarizer(classes=SKILLS_LIST)
    skills_encoded = mlb.fit_transform(df["skills"])
    skills_df = pd.DataFrame(skills_encoded, columns=mlb.classes_)

    # encode location (simple — UK vs US)
    df["is_us"] = df["location"].str.contains("New York|San Francisco|Chicago|Seattle|Austin|Manhattan", case=False, na=False).astype(int)

    # combine features
    X = pd.concat([skills_df, df[["is_us"]].reset_index(drop=True)], axis=1)
    y = df["salary_min"].values

    # train Ridge regression
    model = Ridge(alpha=1.0)
    model.fit(X, y)

    return model, mlb, df["salary_min"].mean()

def predict_salary(model, mlb, user_skills, location):
    if model is None:
        return 0

    if not user_skills:
        return 0

    # encode user skills
    skills_encoded = mlb.transform([user_skills])
    skills_df = pd.DataFrame(skills_encoded, columns=mlb.classes_)

    # encode location
    is_us = 1 if any(city in location.lower() for city in [
        "new york", "san francisco", "chicago", "seattle",
        "austin", "manhattan", "us", "usa", "america", "canada", "australia"
    ]) else 0
    skills_df["is_us"] = is_us

    prediction = model.predict(skills_df)[0]

    # if prediction is unrealistically low, return 0
    if prediction < 5000:
        return 0

    return max(0, round(prediction))