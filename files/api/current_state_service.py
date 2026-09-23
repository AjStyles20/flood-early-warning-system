"""Current-state application service for legacy telemetry compatibility.

This service owns interpretation/orchestration of a stored telemetry reading.
HTTP routes should not need to know how trend calculation, the frozen synthetic
development model, and the explainable threshold engine are combined.

Important scientific boundary:
- threshold state is the operational/current-state assessment;
- the saved ML model is simulator-only development evidence;
- ML probability is never merged numerically with the threshold ratio.
"""

from sqlalchemy.orm import Session

import ml_model
import models
from risk_engine import classify


def compute_rate_of_rise_m(record: models.TelemetryRecord, db: Session) -> float:
    """Return change since the previous compatible reading, in metres/reading.

    We deliberately do not call this metres/hour because simulator and hardware
    sampling intervals can differ.
    """
    previous = (
        db.query(models.TelemetryRecord)
        .filter(
            models.TelemetryRecord.station_id == record.station_id,
            models.TelemetryRecord.data_source == record.data_source,
            models.TelemetryRecord.timestamp < record.timestamp,
        )
        .order_by(models.TelemetryRecord.timestamp.desc(), models.TelemetryRecord.id.desc())
        .first()
    )
    return record.water_level_m - previous.water_level_m if previous else 0.0


def assess_record(
    record: models.TelemetryRecord,
    db: Session,
    *,
    language: str = "en",
    rate_of_rise: float | None = None,
):
    """Create an explainable current-state assessment from one stored reading."""
    measured_rate = compute_rate_of_rise_m(record, db) if rate_of_rise is None else rate_of_rise
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
            rate_of_rise=measured_rate,
        )
    return classify(
        record.water_level_m,
        record.danger_level_m,
        probability,
        language=language,
    )


def status_from_record(
    record: models.TelemetryRecord,
    db: Session,
    *,
    alert_channels: dict[str, str] | None = None,
    language: str = "en",
) -> models.RiskStatus:
    """Translate one stored reading into the public/display status contract."""
    rate_of_rise = compute_rate_of_rise_m(record, db)
    assessment = assess_record(record, db, language=language, rate_of_rise=rate_of_rise)
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
        rate_of_rise_m=round(rate_of_rise, 4),
        battery_pct=record.battery_pct,
        signal=record.signal,
        risk_level=assessment.risk_level,
        risk_ratio=assessment.ratio,
        ml_probability=assessment.ml_probability,
        model_available=(record.data_source == "simulated" and ml_model.model_available()),
        message=assessment.message,
        color=assessment.color,
        language=language,
        alert_channels=alert_channels or {"web": "available", "email": "simulated", "sms": "simulated"},
    )
