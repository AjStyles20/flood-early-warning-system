"""Compatibility adapter from the proven legacy telemetry contract to normalized evidence.

The legacy table remains the external compatibility record during DB-3.  This
adapter mirrors only values actually present in TelemetryCreate.  It never
creates rainfall/flow/battery observations when those fields are None.
"""

from sqlalchemy.orm import Session

import models
import observation_repository
import observation_write_policy
import threshold_repository


_SOURCE_MAP = {"hardware": "LOCAL_SENSOR", "simulated": "SIMULATED"}


def _station(db: Session, reading: models.TelemetryCreate) -> models.Station:
    row = db.query(models.Station).filter(models.Station.station_code == reading.station_id).first()
    if row is None:
        row = models.Station(
            station_code=reading.station_id,
            name=reading.station_name,
            latitude=reading.lat,
            longitude=reading.lon,
            station_type="prototype" if reading.data_source == "hardware" else "simulator",
        )
        db.add(row)
        db.flush()
    else:
        # Station identity is stable, while display metadata/location may be
        # corrected by a later validated payload.
        row.name = reading.station_name
        row.latitude = reading.lat
        row.longitude = reading.lon
    return row


def _observation(
    db: Session,
    *,
    station: models.Station,
    variable: models.Variable,
    source: models.DataSource,
    reading: models.TelemetryCreate,
    value: float,
) -> models.Observation:
    return observation_write_policy.stage_observation(
        db,
        station=station,
        variable=variable,
        source=source,
        observed_at=reading.timestamp,
        value=value,
        dataset=None,
        quality_flag="controlled_prototype" if reading.data_source == "hardware" else "simulated",
        signal_status=reading.signal,
    )


def stage_normalized_mirror(db: Session, reading: models.TelemetryCreate) -> list[models.Observation]:
    """Stage normalized rows in the caller's transaction; do not commit."""
    observation_repository.seed_catalogues(db, commit=False)
    station = _station(db, reading)
    source = observation_repository.get_source(db, _SOURCE_MAP[reading.data_source])
    if source is None:
        raise RuntimeError("Required normalized data-source catalogue entry is missing.")

    values = [
        ("river_stage", reading.water_level_m),
        ("rainfall_rate", reading.rainfall_mm_hr),
        ("river_discharge", reading.flow_rate_m3s),
        ("battery_pct", reading.battery_pct),
    ]
    rows = []
    for code, value in values:
        if value is None:
            continue
        variable = observation_repository.get_variable(db, code)
        if variable is None:
            raise RuntimeError(f"Required normalized variable catalogue entry is missing: {code}")
        rows.append(_observation(
            db, station=station, variable=variable, source=source,
            reading=reading, value=value,
        ))

    # Threshold is decision/configuration evidence, never an Observation.
    # Legacy prototype thresholds have no independent external source, so their
    # provenance is explicitly compatibility-derived rather than "official".
    stage_variable = observation_repository.get_variable(db, "river_stage")
    # The generic telemetry ingestion contract is not an authority channel.
    # A caller may preserve a supplied type label for compatibility, but it
    # cannot create an authoritative threshold claim through this path.
    threshold_type = reading.threshold_type
    source_reference = (
        "legacy_telemetry_compatibility: validated TelemetryCreate payload; "
        "not independently verified as an official hydrological threshold"
    )
    if threshold_type == "official_operational":
        threshold_type = "prototype_demo"
        source_reference = (
            "legacy_telemetry_compatibility: caller supplied official_operational, "
            "but generic telemetry ingestion is not an authorized official-threshold "
            "channel; stored as prototype_demo pending independent authority evidence"
        )

    threshold_repository.stage_compatibility_threshold(
        db,
        station=station,
        variable=stage_variable,
        threshold_type=threshold_type,
        value=reading.danger_level_m,
        source_reference=source_reference,
        observed_at=reading.timestamp,
    )
    return rows
