"""
train_model.py
================

Trains the flood-risk classifier used by ml_model.py.

Honesty note (important for Chapter 3/4 and for defense): this script
trains on SIMULATOR-GENERATED data, not real historical Nigerian
hydrological data. That is a deliberate, documented limitation (Section
1.6), not something to hide. Its purpose here is to prove the *pipeline*
works end-to-end -- ingestion, feature engineering, model comparison,
serialization, and serving -- so that real historical/open data (CHIRPS
rainfall, NIHSA records, etc., per the Chapter 3 methodology checklist)
can be substituted in later without changing any downstream code.

Methodology, matching the NOAH AI review already incorporated into
Chapter 2:
  - A simple threshold baseline is reported alongside the learned models,
    not just the learned models alone.
  - Two learned models are compared: Logistic Regression (interpretable)
    and Random Forest (nonlinear, feature importance available).
  - The train/test split is done by RUN (a whole simulated flood/normal
    episode), not by individual random rows, so the model is evaluated on
    entire unseen episodes -- the closest a synthetic-data setup can get
    to the chronological-split principle recommended for real time-series
    data.
"""

import sys
import os
import random
import json

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
import joblib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "simulator"))
from flood_sensor_simulator import DEFAULT_STATIONS, generate_reading  # noqa: E402

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
FEATURE_NAMES = ["water_level_ratio", "rainfall_mm_hr", "flow_rate_m3s", "rate_of_rise"]


def _simulate_episode(station, mode, n_ticks):
    """Generate one simulated episode (a run of readings) for one station."""
    rows = []
    prev_level = station["baseline_m"]
    for tick in range(n_ticks):
        reading = generate_reading(station, tick, n_ticks, mode)
        rate_of_rise = reading["water_level_m"] - prev_level
        prev_level = reading["water_level_m"]
        ratio = reading["water_level_m"] / reading["danger_level_m"]
        label = 1 if reading["water_level_m"] >= reading["danger_level_m"] else 0
        rows.append({
            "water_level_ratio": ratio,
            "rainfall_mm_hr": reading["rainfall_mm_hr"],
            "flow_rate_m3s": reading["flow_rate_m3s"],
            "rate_of_rise": rate_of_rise,
            "label": label,
        })
    return rows


def build_dataset(n_episodes_per_class=120, n_ticks=30, seed=42):
    random.seed(seed)
    np.random.seed(seed)
    episodes = []
    for _ in range(n_episodes_per_class):
        station = random.choice(DEFAULT_STATIONS)
        episodes.append(("flood", _simulate_episode(station, "flood", n_ticks)))
    for _ in range(n_episodes_per_class):
        station = random.choice(DEFAULT_STATIONS)
        episodes.append(("normal", _simulate_episode(station, "normal", n_ticks)))
    random.shuffle(episodes)
    return episodes


def episodes_to_arrays(episodes):
    X, y = [], []
    for _mode, rows in episodes:
        for row in rows:
            X.append([row[f] for f in FEATURE_NAMES])
            y.append(row["label"])
    return np.array(X), np.array(y)


def threshold_baseline_predict(X):
    """Naive baseline: flag as flood risk whenever water_level_ratio >= 1.0."""
    ratio_idx = FEATURE_NAMES.index("water_level_ratio")
    return (X[:, ratio_idx] >= 1.0).astype(int)


def evaluate(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    print(f"  {name:22s} accuracy={acc:.3f}  precision={prec:.3f}  recall={rec:.3f}  f1={f1:.3f}")
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1}


def main():
    print("[train] Generating synthetic episodes (flood + normal)...")
    episodes = build_dataset(n_episodes_per_class=120, n_ticks=30)

    # Episode-level split: 80% of episodes for training, 20% held out entirely,
    # so evaluation is on whole unseen episodes, not individual leaked rows.
    split = int(len(episodes) * 0.8)
    train_episodes = episodes[:split]
    test_episodes = episodes[split:]

    X_train, y_train = episodes_to_arrays(train_episodes)
    X_test, y_test = episodes_to_arrays(test_episodes)
    print(f"[train] {len(train_episodes)} training episodes ({len(X_train)} readings), "
          f"{len(test_episodes)} test episodes ({len(X_test)} readings)")

    results = {}

    print("[train] Evaluating threshold baseline...")
    y_pred_baseline = threshold_baseline_predict(X_test)
    results["threshold_baseline"] = evaluate("Threshold baseline", y_test, y_pred_baseline)

    print("[train] Training Logistic Regression...")
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_train, y_train)
    results["logistic_regression"] = evaluate("Logistic Regression", y_test, lr.predict(X_test))

    print("[train] Training Random Forest...")
    rf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)
    rf.fit(X_train, y_train)
    results["random_forest"] = evaluate("Random Forest", y_test, rf.predict(X_test))

    importances = dict(zip(FEATURE_NAMES, rf.feature_importances_.round(3).tolist()))
    print(f"[train] Random Forest feature importances: {importances}")

    # Random Forest is selected as the serving model (best F1 in this synthetic
    # setup and gives feature importances for explainability); this is a
    # documented, changeable choice, not a hard-coded assumption.
    joblib.dump({"model": rf, "feature_names": FEATURE_NAMES}, MODEL_PATH)
    print(f"[train] Saved serving model to {MODEL_PATH}")

    metrics_path = os.path.join(os.path.dirname(__file__), "model_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump({"results": results, "feature_importances": importances}, f, indent=2)
    print(f"[train] Saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
