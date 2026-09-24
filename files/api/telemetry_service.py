"""Telemetry/current-state application orchestration.

Transport concerns stay in FastAPI routes; this service owns the reusable
workflow shared by REST and CSV ingestion and normalized risk-status reads.
"""

from collections import defaultdict
import json
from sqlalchemy import text
from sqlalchemy.orm import Session

import models
import notifications
import telemetry_repository
import normalized_read_repository
import normalized_current_state_service
from risk_engine import classify


_RISK_ORDER = {"Low": 0, "Moderate": 1, "High": 2, "Severe": 3}


def ingest(
    db: Session,
    reading: models.TelemetryCreate,
    *,
    persist_alert_event,
) -> models.TelemetryRecord:
    """Persist validated telemetry and run immediate threshold notification flow."""
    record = telemetry_repository.create_record(db, reading)
    assessment = classify(record.water_level_m, record.danger_level_m)
    station_id, station_name, data_source = record.station_id, record.station_name, record.data_source
    # Serialize the read/dispatch/persist decision across API workers using the
    # database. This lock ends when persist_event commits the alert outcome.
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        db.rollback()  # refresh(record) began a read transaction after telemetry commit
        db.execute(text("BEGIN IMMEDIATE"))
    elif dialect == "mysql":
        db.query(models.Station).filter(models.Station.station_code == station_id).with_for_update().one()
    else:
        raise RuntimeError(f"Alert dispatch requires a supported locking database: {dialect}")
    try:
        return _dispatch_locked(db, record, assessment, station_id, station_name, data_source, persist_alert_event)
    except Exception:
        db.rollback()
        raise


def _dispatch_locked(db, record, assessment, station_id, station_name, data_source, persist_alert_event):
    """Decide and persist a dispatch while holding the station's DB lock."""
    active = (
        db.query(models.AlertEvent)
        .filter(
            models.AlertEvent.station_id == station_id,
            models.AlertEvent.data_source == data_source,
            models.AlertEvent.status.in_(("new", "acknowledged", "escalated")),
        )
        .order_by(models.AlertEvent.updated_at.desc(), models.AlertEvent.id.desc())
        .first()
    ) if assessment.should_alert else None
    # A new alert or a higher risk level warrants a provider attempt. Keep the
    # original outcome on repeated readings so the dashboard stays auditable.
    if active and _RISK_ORDER.get(assessment.risk_level, 0) <= _RISK_ORDER.get(active.risk_level, 0):
        try:
            delivery_channels = json.loads(active.channels_json or "{}")
            if not isinstance(delivery_channels, dict):
                delivery_channels = {}
        except (TypeError, ValueError):
            delivery_channels = {}
    else:
        delivery_channels = notifications.notify(
            station_id,
            station_name,
            assessment,
            data_source=data_source,
        )
    persist_alert_event(
        db,
        station_id,
        station_name,
        data_source,
        assessment.risk_level,
        assessment.message,
        channels=delivery_channels,
    )
    if db.in_transaction():
        db.commit()
    return record


def risk_statuses(
    db: Session,
    *,
    data_source: str | None,
    language: str,
    alert_channels: dict[str, str],
    risk_rank: dict[str, int],
) -> list[models.RiskStatus]:
    """Return normalized current-state statuses using existing hybrid semantics."""
    if data_source == "hybrid":
        grouped = defaultdict(list)
        for record in normalized_read_repository.latest_evidence(db):
            grouped[record.station_id].append(record)
        statuses = []
        for station_records in grouped.values():
            candidates = [
                normalized_current_state_service.status_from_evidence(
                    record, db, dict(alert_channels), language=language
                )
                for record in station_records
            ]
            statuses.append(
                max(candidates, key=lambda item: (risk_rank.get(item.risk_level, 0), item.timestamp))
            )
        return statuses

    records = normalized_read_repository.latest_per_station(db, data_source=data_source)
    return [
        normalized_current_state_service.status_from_evidence(
            record, db, dict(alert_channels), language=language
        )
        for record in records
    ]
