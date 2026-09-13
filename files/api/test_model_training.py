"""Focused test for the ML training target.

This catches the exact circularity bug that made the old threshold baseline
score perfectly.  The model must learn a future crossing target, not a label
that is identical to the current water-level threshold rule.
"""

from train_model import train_and_evaluate


def check(condition, message):
    """Raise a clear error when a leakage guard fails."""
    if not condition:
        raise AssertionError(message)


print("\n>>> STARTING FLOODWATCH MODEL LEAKAGE-GUARD TEST...")
print("-" * 68)

report, bundle = train_and_evaluate(episodes_per_class=40, ticks=30, horizon=6, save_artifacts=False)
baseline = report["results"]["threshold_baseline"]
label_policy = report["label_policy"]

print(f"   prediction target:          {report['prediction_target']}")
print(f"   horizon ticks:              {report['prediction_horizon_ticks']}")
print(f"   baseline warning ratio:     {report['baseline_warning_ratio']}")
print(f"   positive samples:           {label_policy['positive_samples']}")
print(f"   positives below danger now: {label_policy['positive_samples_below_current_danger']}")
print(f"   current-threshold samples:   {label_policy['current_threshold_positive_samples_used']}")
print(f"   max current ratio used:      {label_policy['max_current_water_level_ratio_used']}")
print(f"   excluded current-danger rows:{label_policy['current_danger_rows_excluded']}")
print(f"   threshold baseline F1:      {baseline['f1']}")
print(f"   random forest F1:           {report['results']['random_forest']['f1']}\n")

check(report["prediction_target"] == "future_threshold_crossing", "Training target must be future threshold crossing.")
check(bundle["prediction_target"] == "future_threshold_crossing", "Saved model bundle must describe the corrected target.")
check(report["prediction_horizon_ticks"] == 6, "Training report must store the prediction horizon.")
check(label_policy["positive_samples"] > 0, "Synthetic future-crossing positives must exist.")
check(label_policy["current_threshold_positive_samples_used"] == 0, "No used row may already be at the danger threshold.")
check(label_policy["max_current_water_level_ratio_used"] < 1.0, "All training/evaluation rows must be below danger level now.")
check(
    label_policy["positive_samples_below_current_danger"] == label_policy["positive_samples"],
    "Every positive training sample must still be below danger level at the current tick.",
)
check(baseline["f1"] < 1.0, "Threshold baseline must no longer score perfectly from label circularity.")

print("-" * 68)
print("[PASS] Future-horizon ML target verified; circular current-threshold label leakage removed.")
