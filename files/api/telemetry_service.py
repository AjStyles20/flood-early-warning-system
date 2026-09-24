"""Telemetry/current-state application orchestration.

Transport concerns stay in FastAPI routes; this service owns the reusable
workflow shared by REST and CSV ingestion and normalized risk-status reads.
"""

from collections import defaultdict
from sqlalchemy.orm import Session

import models
import notifications
import telemetry_repository
import normalized_read_repository
import normalized_current_state_service
from risk_engine import classify


def ingest(
    db: Session,
    reading: models.TelemetryCreate,
    *,
    persist_alert_event,
) -> models.TelemetryRecord:
    """Persist validated telemetry and run immediate threshold notification flow."""
    record = telemetry_repository.create_record(db, reading)
    assessment = classify(record.water_level_m, record.danger_level_m)
    notifications.notify(
        record.station_id,
        record.station_name,
        assessment,
        data_source=record.data_source,
    )
    persist_alert_event(
        db,
        record.station_id,
        record.station_name,
        record.data_source,
        assessment.risk_level,
        assessment.message,
    )
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
