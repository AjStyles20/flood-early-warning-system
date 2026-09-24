"""DB-4 parity reconstruction from normalized observations.

This module reconstructs the telemetry-shaped evidence needed for parity
checking. It does not switch public/dashboard reads away from the legacy table.
Threshold configuration is resolved from the typed Threshold entity and must be applicable at the observation timestamp.
"""

from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session

import models
import threshold_repository


_SOURCE_TO_LEGACY = {"LOCAL_SENSOR": "hardware", "SIMULATED": "simulated"}


@dataclass(frozen=True)
class NormalizedTelemetryEvidence:
    station_id: str
    station_name: str
    data_source: str
    lat: float
    lon: float
    timestamp: datetime
    water_level_m: float
    rainfall_mm_hr: float | None
    flow_rate_m3s: float | None
    battery_pct: float | None
    signal: str | None
    danger_level_m: float
    threshold_type: str


def _latest_stage_rows(db: Session):
    stage = db.query(models.Variable).filter(models.Variable.code == "river_stage").first()
    if stage is None:
        return []
    rows = (
        db.query(models.Observation, models.Station, models.DataSource)
        .join(models.Station, models.Observation.station_id == models.Station.id)
        .join(models.DataSource, models.Observation.source_id == models.DataSource.id)
        .filter(
            models.Observation.variable_id == stage.id,
            models.DataSource.code.in_(tuple(_SOURCE_TO_LEGACY)),
        )
        .order_by(
            models.Station.station_code.asc(),
            models.DataSource.code.asc(),
            models.Observation.observed_at.desc(),
            models.Observation.id.desc(),
        )
        .all()
    )
    latest = {}
    for obs, station, source in rows:
        latest.setdefault((station.id, source.id), (obs, station, source))
    return list(latest.values())


def _value_at(db: Session, *, station_id: int, source_id: int, code: str, observed_at: datetime):
    variable = db.query(models.Variable).filter(models.Variable.code == code).first()
    if variable is None:
        return None
    row = (
        db.query(models.Observation)
        .filter(
            models.Observation.station_id == station_id,
            models.Observation.source_id == source_id,
            models.Observation.variable_id == variable.id,
            models.Observation.observed_at == observed_at,
        )
        .order_by(models.Observation.id.desc())
        .first()
    )
    return row.value if row is not None else None


def latest_evidence(
    db: Session,
    *,
    data_source: str | None = None,
) -> list[NormalizedTelemetryEvidence]:
    """Reconstruct newest normalized evidence per station/source.

    data_source filters the normalized provenance mapping without falling back
    to the legacy telemetry table.
    """
    result = []
    for stage_obs, station, source in _latest_stage_rows(db):
        legacy_source = _SOURCE_TO_LEGACY[source.code]
        if data_source is not None and legacy_source != data_source:
            continue
        threshold = threshold_repository.applicable_threshold(
            db,
            station_id=station.id,
            variable_id=stage_obs.variable_id,
            observed_at=stage_obs.observed_at,
        )
        if threshold is None:
            # No silent fallback: current-state interpretation requires an
            # explicit threshold with provenance/type.
            continue
        result.append(NormalizedTelemetryEvidence(
            station_id=station.station_code,
            station_name=station.name,
            data_source=legacy_source,
            lat=station.latitude,
            lon=station.longitude,
            timestamp=stage_obs.observed_at,
            water_level_m=stage_obs.value,
            rainfall_mm_hr=_value_at(db, station_id=station.id, source_id=source.id, code="rainfall_rate", observed_at=stage_obs.observed_at),
            flow_rate_m3s=_value_at(db, station_id=station.id, source_id=source.id, code="river_discharge", observed_at=stage_obs.observed_at),
            battery_pct=_value_at(db, station_id=station.id, source_id=source.id, code="battery_pct", observed_at=stage_obs.observed_at),
            signal=stage_obs.signal_status,
            danger_level_m=threshold.value,
            threshold_type=threshold.threshold_type,
        ))
    return result


def latest_per_station(
    db: Session,
    *,
    data_source: str | None = None,
) -> list[NormalizedTelemetryEvidence]:
    """Newest normalized evidence per station, matching legacy tie semantics."""
    rows = latest_evidence(db, data_source=data_source)
    rows.sort(key=lambda row: (row.station_id, row.timestamp), reverse=True)
    latest = {}
    for row in rows:
        latest.setdefault(row.station_id, row)
    return list(latest.values())
