"""Focused tests for the scientific observation/provenance contract.

These tests do not train ML or run Experiment 001.
"""

from datetime import datetime, timezone

from pydantic import ValidationError

from observation_contract import (
    EvidenceClass,
    Observation,
    QualityState,
    SourceType,
    ThresholdDefinition,
    ThresholdType,
    unavailable_observation,
)


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def test_valid_grdc_observation():
    item = Observation(
        variable="river_discharge",
        value=18906.4,
        unit="m3/s",
        timestamp=NOW,
        station_id="GRDC-1834101",
        station_name="Lokoja",
        lat=7.8,
        lon=6.7667,
        provider="GRDC",
        source_type=SourceType.AUTHORITATIVE_OBSERVATION,
        evidence_class=EvidenceClass.OBSERVED,
        quality=QualityState.VALID,
    )
    assert item.value == 18906.4
    assert item.source_type == SourceType.AUTHORITATIVE_OBSERVATION


def test_not_measured_is_none_not_zero():
    item = unavailable_observation(
        variable="local_rainfall",
        unit="mm/hr",
        timestamp=NOW,
        station_id="HW-01",
        station_name="Prototype Hardware Gauge",
        provider="FloodWatch prototype",
        source_type=SourceType.LOCAL_SENSOR,
        evidence_class=EvidenceClass.OBSERVED,
    )
    assert item.value is None
    assert item.quality == QualityState.NOT_MEASURED


def test_absent_quality_rejects_numeric_placeholder():
    try:
        Observation(
            variable="river_discharge",
            value=0.0,
            unit="m3/s",
            timestamp=NOW,
            provider="FloodWatch prototype",
            source_type=SourceType.LOCAL_SENSOR,
            evidence_class=EvidenceClass.OBSERVED,
            quality=QualityState.NOT_MEASURED,
        )
    except ValidationError:
        return
    raise AssertionError("NOT_MEASURED must reject a fabricated numeric zero")


def test_coordinates_are_a_pair():
    try:
        Observation(
            variable="river_stage",
            value=1.2,
            unit="m",
            timestamp=NOW,
            lat=7.8,
            provider="FloodWatch prototype",
            source_type=SourceType.LOCAL_SENSOR,
            evidence_class=EvidenceClass.OBSERVED,
        )
    except ValidationError:
        return
    raise AssertionError("a lone latitude/longitude should be rejected")


def test_demo_threshold_is_explicitly_demo():
    threshold = ThresholdDefinition(
        variable="river_stage",
        value=2.0,
        unit="m",
        threshold_type=ThresholdType.PROTOTYPE_DEMO,
        provider="FloodWatch prototype",
        station_id="HW-01",
        notes="Controlled integration threshold; not an official Lokoja threshold.",
    )
    assert threshold.threshold_type == ThresholdType.PROTOTYPE_DEMO


if __name__ == "__main__":
    tests = [
        test_valid_grdc_observation,
        test_not_measured_is_none_not_zero,
        test_absent_quality_rejects_numeric_placeholder,
        test_coordinates_are_a_pair,
        test_demo_threshold_is_explicitly_demo,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)} observation-contract tests passed.")
