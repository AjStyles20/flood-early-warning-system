"""Compatibility adapter from the proven legacy telemetry contract to normalized evidence.

The legacy table remains the external compatibility record during DB-3.  This
adapter mirrors only values actually present in TelemetryCreate.  It never
creates rainfall/flow/battery observations when those fields are None.
"""

from sqlalchemy.orm import Session

import models
import observation_repository


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
    row = models.Observation(
        station_id=station.id,
        variable_id=variable.id,
        source_id=source.id,
        dataset_id=None,
        observed_at=reading.timestamp,
        value=value,
        quality_flag="controlled_prototype" if reading.data_source == "hardware" else "simulated",
        signal_status=reading.signal,
    )
    db.add(row)
    return row


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

    # Threshold is a decision/configuration value, not an observation. During
    # compatibility mirroring it is intentionally not copied into Observation.
    return rows
