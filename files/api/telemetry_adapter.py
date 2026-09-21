"""Compatibility adapter between legacy FloodWatch telemetry and observations.

The live API still accepts the original telemetry shape while the codebase is
migrated. This adapter makes the scientific meaning explicit without changing
Experiment 001 or requiring the dashboard to be rewritten in one step.
"""

from datetime import datetime

from observation_contract import (
    EvidenceClass,
    Observation,
    QualityState,
    SourceType,
    ThresholdDefinition,
    ThresholdType,
    unavailable_observation,
)


def legacy_source_type(data_source: str) -> SourceType:
    if data_source == "hardware":
        return SourceType.LOCAL_SENSOR
    if data_source == "simulated":
        return SourceType.SIMULATED
    raise ValueError(f"unsupported legacy data_source: {data_source}")


def legacy_evidence_class(data_source: str) -> EvidenceClass:
    if data_source == "hardware":
        return EvidenceClass.OBSERVED
    if data_source == "simulated":
        return EvidenceClass.SIMULATED
    raise ValueError(f"unsupported legacy data_source: {data_source}")


def telemetry_to_observations(
    *,
    station_id: str,
    station_name: str,
    data_source: str,
    timestamp: datetime,
    lat: float,
    lon: float,
    water_level_m: float,
    rainfall_mm_hr: float | None,
    flow_rate_m3s: float | None,
    battery_pct: float | None,
    signal: str,
    provider: str = "FloodWatch",
    placeholder_fields: set[str] | None = None,
) -> list[Observation]:
    """Translate one legacy telemetry row without turning absence into zero.

    placeholder_fields identifies legacy numeric fields whose values existed
    only because the old API required them. Such fields become NOT_MEASURED
    observations with value=None.
    """

    placeholders = placeholder_fields or set()
    source_type = legacy_source_type(data_source)
    evidence_class = legacy_evidence_class(data_source)
    common = {
        "timestamp": timestamp,
        "station_id": station_id,
        "station_name": station_name,
        "lat": lat,
        "lon": lon,
        "provider": provider,
        "source_type": source_type,
        "evidence_class": evidence_class,
        "metadata": {"legacy_data_source": data_source, "signal": signal},
    }

    observations = [
        Observation(
            variable="river_stage_like_level",
            value=water_level_m,
            unit="m",
            quality=QualityState.VALID,
            **common,
        )
    ]

    optional = [
        ("rainfall", rainfall_mm_hr, "mm/hr"),
        ("river_discharge", flow_rate_m3s, "m3/s"),
        ("battery_state", battery_pct, "%"),
    ]
    for variable, value, unit in optional:
        legacy_name = {
            "rainfall": "rainfall_mm_hr",
            "river_discharge": "flow_rate_m3s",
            "battery_state": "battery_pct",
        }[variable]
        if legacy_name in placeholders or value is None:
            observations.append(
                unavailable_observation(
                    variable=variable,
                    unit=unit,
                    timestamp=timestamp,
                    station_id=station_id,
                    station_name=station_name,
                    provider=provider,
                    source_type=source_type,
                    evidence_class=evidence_class,
                    metadata={
                        "legacy_data_source": data_source,
                        "signal": signal,
                        "legacy_placeholder": legacy_name in placeholders,
                    },
                )
            )
        else:
            observations.append(
                Observation(
                    variable=variable,
                    value=value,
                    unit=unit,
                    quality=QualityState.VALID,
                    **common,
                )
            )

    return observations


def prototype_demo_threshold(
    *,
    station_id: str,
    value_m: float,
    provider: str = "FloodWatch prototype",
) -> ThresholdDefinition:
    """Label a hardware-integration threshold honestly as prototype/demo."""

    return ThresholdDefinition(
        variable="river_stage_like_level",
        value=value_m,
        unit="m",
        threshold_type=ThresholdType.PROTOTYPE_DEMO,
        provider=provider,
        station_id=station_id,
        notes=(
            "Controlled integration threshold. It is not an official Lokoja "
            "flood-warning threshold and must not be presented as one."
        ),
    )
