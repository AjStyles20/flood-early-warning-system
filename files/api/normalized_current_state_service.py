"""Current-state interpretation from normalized observation evidence.

This is the DB-4 candidate path. It deliberately reuses the same risk engine
and frozen simulator-only ML wrapper as the legacy current-state service.
"""

from sqlalchemy.orm import Session

import ml_model
import models
import normalized_read_repository
from risk_engine import classify


def _previous_stage(db: Session, record: normalized_read_repository.NormalizedTelemetryEvidence):
    source_code = {"hardware": "LOCAL_SENSOR", "simulated": "SIMULATED"}[record.data_source]
    station = db.query(models.Station).filter(models.Station.station_code == record.station_id).first()
    variable = db.query(models.Variable).filter(models.Variable.code == "river_stage").first()
    source = db.query(models.DataSource).filter(models.DataSource.code == source_code).first()
    if not station or not variable or not source:
        return None
    return (
        db.query(models.Observation)
        .filter(
            models.Observation.station_id == station.id,
            models.Observation.variable_id == variable.id,
            models.Observation.source_id == source.id,
            models.Observation.observed_at < record.timestamp,
        )
        .order_by(models.Observation.observed_at.desc(), models.Observation.id.desc())
        .first()
    )


def compute_rate_of_rise_m(
    record: normalized_read_repository.NormalizedTelemetryEvidence,
    db: Session,
) -> float:
    """Return change in metres since the previous reading for this source.

    This is deliberately a per-reading delta, not metres/hour.  Timestamp
    spacing may vary, so callers must not reinterpret the value as a time-rate
    without separately validating the sampling interval.
    """
    previous = _previous_stage(db, record)
    return record.water_level_m - previous.value if previous else 0.0


def status_from_evidence(
    record: normalized_read_repository.NormalizedTelemetryEvidence,
    db: Session,
    alert_channels: dict[str, str] | None = None,
    *,
    language: str = "en",
) -> models.RiskStatus:
    """Build the existing public status contract from normalized evidence."""
    rate = compute_rate_of_rise_m(record, db)
    probability = None
    if (
        record.data_source == "simulated"
        and record.rainfall_mm_hr is not None
        and record.flow_rate_m3s is not None
    ):
        probability = ml_model.predict(
            water_level_m=record.water_level_m,
            danger_level_m=record.danger_level_m,
            rainfall_mm_hr=record.rainfall_mm_hr,
            flow_rate_m3s=record.flow_rate_m3s,
            rate_of_rise=rate,
        )
    assessment = classify(
        record.water_level_m,
        record.danger_level_m,
        probability,
        language=language,
    )
    return models.RiskStatus(
        station_id=record.station_id,
        station_name=record.station_name,
        data_source=record.data_source,
        lat=record.lat,
        lon=record.lon,
        timestamp=record.timestamp,
        water_level_m=record.water_level_m,
        danger_level_m=record.danger_level_m,
        threshold_type=record.threshold_type,
        rainfall_mm_hr=record.rainfall_mm_hr,
        flow_rate_m3s=record.flow_rate_m3s,
        rate_of_rise_m=round(rate, 4),
        battery_pct=record.battery_pct,
        signal=record.signal or "unknown",
        risk_level=assessment.risk_level,
        risk_ratio=assessment.ratio,
        ml_probability=assessment.ml_probability,
        model_available=(record.data_source == "simulated" and ml_model.model_available()),
        message=assessment.message,
        color=assessment.color,
        language=language,
        alert_channels=alert_channels or {"web": "available", "email": "simulated", "sms": "simulated"},
    )
