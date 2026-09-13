"""Small serving wrapper around the model produced by :mod:`train_model`.

The trained model estimates future early-warning risk, not merely whether the
station is already above its danger threshold.  Direct threshold status remains
the job of ``risk_engine.py``.
"""

from pathlib import Path
from typing import Optional

import joblib


MODEL_PATH = Path(__file__).with_name("model.pkl")
FEATURE_NAMES = ["water_level_ratio", "rainfall_mm_hr", "flow_rate_m3s", "rate_of_rise"]
_cached_bundle = None
_load_attempted = False


def _load_bundle():
    """Load the trained artefact once; absence is a safe, supported state."""
    global _cached_bundle, _load_attempted
    if not _load_attempted:
        _load_attempted = True
        if MODEL_PATH.exists():
            # A partly copied or incompatible artefact must never make the
            # telemetry API fail. The transparent threshold rule remains the
            # safe fallback until the model can be retrained successfully.
            try:
                _cached_bundle = joblib.load(MODEL_PATH)
            except Exception:
                _cached_bundle = None
    return _cached_bundle


def model_available() -> bool:
    """Report whether this running API can make a trained-model prediction."""
    return _load_bundle() is not None


def reset_model_cache() -> None:
    """Test helper and development convenience after a model is freshly trained."""
    global _cached_bundle, _load_attempted
    _cached_bundle = None
    _load_attempted = False


def predict(*, water_level_m: float, danger_level_m: float, rainfall_mm_hr: float,
            flow_rate_m3s: float, rate_of_rise: float) -> Optional[float]:
    """Return flood probability, or ``None`` until a validated model is trained."""
    bundle = _load_bundle()
    if bundle is None:
        return None
    if danger_level_m <= 0:
        raise ValueError("danger_level_m must be positive")
    features = [[water_level_m / danger_level_m, rainfall_mm_hr, flow_rate_m3s, rate_of_rise]]
    # ``predict_proba`` column 1 is the probability of the trained positive
    # class: danger-level crossing within the configured future horizon.
    return float(bundle["model"].predict_proba(features)[0][1])
