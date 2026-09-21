"""Scientific separation checks for current-state assessment."""

from risk_engine import classify


def test_forecast_probability_does_not_override_current_threshold_state():
    assessment = classify(1.0, 5.0, ml_probability=0.99)
    assert assessment.risk_level == "Low"
    assert assessment.ml_probability == 0.99


def test_threshold_state_still_reaches_severe_at_threshold():
    assessment = classify(5.0, 5.0, ml_probability=0.01)
    assert assessment.risk_level == "Severe"


if __name__ == "__main__":
    test_forecast_probability_does_not_override_current_threshold_state()
    test_threshold_state_still_reaches_severe_at_threshold()
    print("2 risk-separation tests passed.")
