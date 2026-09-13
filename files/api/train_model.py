"""Train and compare transparent synthetic-data flood early-warning models.

Important correction:
The model is not trained to answer "is the station already at danger level?"
That old target leaked the answer into the features because
``water_level_m / danger_level_m >= 1`` is the same rule as the label.

The corrected target is:
    "while the station is still below danger level now, will it reach danger
    level within the next HORIZON_TICKS simulator readings?"

That makes the ML task a genuine early-warning task.  The model only receives
current-tick features, while the label is derived from future ticks in the same
episode.
"""

import json
from datetime import datetime, timezone
import random
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

# The completed simulator remains in ``files/``. Adding that parent directory
# lets this backend use the same telemetry generator rather than duplicating it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flood_sensor_simulator import DEFAULT_STATIONS, generate_reading  # noqa: E402


MODEL_PATH = Path(__file__).with_name("model.pkl")
METRICS_PATH = Path(__file__).with_name("model_metrics.json")
FEATURE_NAMES = ["water_level_ratio", "rainfall_mm_hr", "flow_rate_m3s", "rate_of_rise"]
PREDICTION_TARGET = "future_threshold_crossing"
HORIZON_TICKS = 6
BASELINE_WARNING_RATIO = 0.85


def _simulate_episode(station: dict, mode: str, n_ticks: int, horizon: int) -> tuple[list[list[float]], dict[str, int]]:
    """Create one simulator episode and label each row with future risk.

    The row features are all known at the current tick:
    - water_level_ratio: current water level divided by station danger level.
    - rainfall_mm_hr: current rainfall intensity.
    - flow_rate_m3s: current flow estimate.
    - rate_of_rise: current water level minus previous water level.

    The row label is deliberately not current risk.  It is 1 only when a future
    reading within the next ``horizon`` ticks reaches the station danger level.
    Rows that are already at/above danger level are excluded because they are
    handled by the transparent risk engine, not by early-warning prediction.
    """
    readings = [generate_reading(station, tick, n_ticks, mode) for tick in range(n_ticks)]
    rows: list[list[float]] = []
    current_danger_rows_excluded = 0

    # Stop at ``n_ticks - horizon`` so every training row has a complete future
    # window.  This avoids quietly labelling final rows as safe just because the
    # simulator run ended.
    for tick in range(n_ticks - horizon):
        reading = readings[tick]
        previous_level = station["baseline_m"] if tick == 0 else readings[tick - 1]["water_level_m"]
        ratio = reading["water_level_m"] / reading["danger_level_m"]

        if reading["water_level_m"] >= reading["danger_level_m"]:
            current_danger_rows_excluded += 1
            continue

        future_window = readings[tick + 1 : tick + horizon + 1]
        future_crossing = any(
            future_reading["water_level_m"] >= future_reading["danger_level_m"]
            for future_reading in future_window
        )
        rows.append(
            [
                ratio,
                reading["rainfall_mm_hr"],
                reading["flow_rate_m3s"],
                reading["water_level_m"] - previous_level,
                int(future_crossing),
            ]
        )

    return rows, {"current_danger_rows_excluded": current_danger_rows_excluded}


def build_dataset(
    episodes_per_class: int = 120,
    ticks: int = 30,
    horizon: int = HORIZON_TICKS,
    seed: int = 42,
) -> tuple[list[tuple[str, list[list[float]]]], dict[str, int]]:
    """Build reproducible full episodes from synthetic simulator evidence.

    Whole episodes are returned so the train/test split can happen by episode,
    not by individual row.  That prevents adjacent readings from one flood run
    leaking into both training and testing.
    """
    random.seed(seed)
    episodes: list[tuple[str, list[list[float]]]] = []
    current_danger_rows_excluded = 0

    for mode in ("flood", "normal"):
        for _episode_number in range(episodes_per_class):
            station = random.choice(DEFAULT_STATIONS)
            rows, metadata = _simulate_episode(station, mode, ticks, horizon)
            episodes.append((mode, rows))
            current_danger_rows_excluded += metadata["current_danger_rows_excluded"]

    random.shuffle(episodes)
    return episodes, {"current_danger_rows_excluded": current_danger_rows_excluded}


def _arrays(episodes: list[tuple[str, list[list[float]]]]) -> tuple[np.ndarray, np.ndarray]:
    """Flatten whole episodes into feature and label arrays for scikit-learn."""
    rows = [row for _mode, episode in episodes for row in episode]
    return np.array([row[:-1] for row in rows]), np.array([row[-1] for row in rows])


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Return the same four metrics for each model and the threshold baseline."""
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def _label_policy_report(x_all: np.ndarray, y_all: np.ndarray, generation_metadata: dict[str, int]) -> dict[str, int | float]:
    """Summarize the leakage guard in the saved metrics file."""
    positives = int(y_all.sum())
    return {
        "current_danger_rows_excluded": generation_metadata["current_danger_rows_excluded"],
        "total_samples_used": int(len(y_all)),
        "positive_samples": positives,
        "negative_samples": int(len(y_all) - positives),
        "current_threshold_positive_samples_used": int((x_all[:, 0] >= 1.0).sum()),
        "max_current_water_level_ratio_used": float(round(x_all[:, 0].max(), 4)),
        "positive_samples_below_current_danger": int(((x_all[:, 0] < 1.0) & (y_all == 1)).sum()),
    }


def train_and_evaluate(
    episodes_per_class: int = 120,
    ticks: int = 30,
    horizon: int = HORIZON_TICKS,
    save_artifacts: bool = True,
) -> tuple[dict, dict]:
    """Compare threshold baseline, Logistic Regression, and Random Forest.

    ``threshold_baseline`` is now an early-warning rule:
    predict future crossing if the current water-level ratio is already at or
    above ``BASELINE_WARNING_RATIO``.  It is still simple and explainable, but
    it is no longer identical to the training label.
    """
    episodes, generation_metadata = build_dataset(episodes_per_class, ticks, horizon)
    split = int(len(episodes) * 0.8)
    train_episodes = episodes[:split]
    test_episodes = episodes[split:]
    x_train, y_train = _arrays(train_episodes)
    x_test, y_test = _arrays(test_episodes)
    x_all, y_all = _arrays(episodes)

    baseline = (x_test[:, 0] >= BASELINE_WARNING_RATIO).astype(int)
    logistic = LogisticRegression(max_iter=1000, class_weight="balanced").fit(x_train, y_train)
    forest = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
    ).fit(x_train, y_train)

    results = {
        "threshold_baseline": _metrics(y_test, baseline),
        "logistic_regression": _metrics(y_test, logistic.predict(x_test)),
        "random_forest": _metrics(y_test, forest.predict(x_test)),
    }
    bundle = {
        "model": forest,
        "feature_names": FEATURE_NAMES,
        "prediction_target": PREDICTION_TARGET,
        "prediction_horizon_ticks": horizon,
        "baseline_warning_ratio": BASELINE_WARNING_RATIO,
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "simulator-generated telemetry only",
        "prediction_target": PREDICTION_TARGET,
        "label_definition": (
            "Positive only when a station that is below danger level now reaches "
            f"danger level within the next {horizon} simulator ticks."
        ),
        "prediction_horizon_ticks": horizon,
        "baseline_warning_ratio": BASELINE_WARNING_RATIO,
        "train_episodes": split,
        "test_episodes": len(episodes) - split,
        "train_samples": int(len(y_train)),
        "test_samples": int(len(y_test)),
        "label_policy": _label_policy_report(x_all, y_all, generation_metadata),
        "results": results,
        "feature_importances": dict(zip(FEATURE_NAMES, forest.feature_importances_.round(4).tolist())),
    }
    if save_artifacts:
        joblib.dump(bundle, MODEL_PATH)
        METRICS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, bundle


if __name__ == "__main__":
    report, _bundle = train_and_evaluate()
    print(json.dumps(report, indent=2))
