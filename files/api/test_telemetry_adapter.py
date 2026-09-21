"""Tests for migration from legacy telemetry to scientific observations."""

from datetime import datetime, timezone

from observation_contract import QualityState, SourceType, ThresholdType
from telemetry_adapter import prototype_demo_threshold, telemetry_to_observations


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def test_hardware_placeholders_are_not_zero_observations():
    observations = telemetry_to_observations(
        station_id="HW-01",
        station_name="Prototype Hardware Gauge",
        data_source="hardware",
        timestamp=NOW,
        lat=9.0579,
        lon=7.4951,
        water_level_m=1.25,
        rainfall_mm_hr=0.0,
        flow_rate_m3s=0.0,
        battery_pct=100.0,
        signal="online",
        placeholder_fields={"rainfall_mm_hr", "flow_rate_m3s", "battery_pct"},
    )
    by_variable = {item.variable: item for item in observations}
    assert by_variable["river_stage_like_level"].value == 1.25
    assert by_variable["river_stage_like_level"].source_type == SourceType.LOCAL_SENSOR
    assert by_variable["rainfall"].value is None
    assert by_variable["rainfall"].quality == QualityState.NOT_MEASURED
    assert by_variable["river_discharge"].value is None
    assert by_variable["battery_state"].value is None


def test_simulated_values_remain_simulated():
    observations = telemetry_to_observations(
        station_id="SIM-01",
        station_name="Controlled Scenario",
        data_source="simulated",
        timestamp=NOW,
        lat=7.8,
        lon=6.7667,
        water_level_m=4.0,
        rainfall_mm_hr=12.0,
        flow_rate_m3s=40.0,
        battery_pct=95.0,
        signal="online",
    )
    assert all(item.source_type == SourceType.SIMULATED for item in observations)


def test_prototype_threshold_cannot_look_official():
    threshold = prototype_demo_threshold(station_id="HW-01", value_m=2.0)
    assert threshold.threshold_type == ThresholdType.PROTOTYPE_DEMO
    assert "not an official Lokoja" in threshold.notes


if __name__ == "__main__":
    tests = [
        test_hardware_placeholders_are_not_zero_observations,
        test_simulated_values_remain_simulated,
        test_prototype_threshold_cannot_look_official,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)} telemetry-adapter tests passed.")
