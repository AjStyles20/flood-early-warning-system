"""Persistence boundary for FloodWatch telemetry.

This module keeps SQLAlchemy query details out of HTTP route handlers.  It is a
small, backward-compatible step toward the architecture documented in
software_engineering_methodology_and_design.md: routes validate transport
contracts, repositories persist/retrieve evidence, and services interpret it.

The existing telemetry table remains the compatibility store during migration.
No scientific meaning is inferred here; source and threshold provenance are
stored exactly as validated by the API contract.
"""

from typing import Literal

from sqlalchemy.orm import Session

import models
import telemetry_normalization_adapter


TelemetrySource = Literal["simulated", "hardware"]


def create_record(db: Session, reading: models.TelemetryCreate) -> models.TelemetryRecord:
    """Persist one already-validated telemetry payload."""
    record = models.TelemetryRecord(**reading.model_dump())
    db.add(record)
    try:
        # DB-3 controlled dual-write: legacy compatibility record and normalized
        # observations share one transaction. A normalization failure therefore
        # cannot leave the two persistence representations silently divergent.
        telemetry_normalization_adapter.stage_normalized_mirror(db, reading)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(record)
    return record


def list_records(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    data_source: TelemetrySource | None = None,
) -> list[models.TelemetryRecord]:
    """Return telemetry newest-first, optionally restricted by evidence source."""
    query = db.query(models.TelemetryRecord)
    if data_source is not None:
        query = query.filter(models.TelemetryRecord.data_source == data_source)
    return (
        query.order_by(models.TelemetryRecord.timestamp.desc(), models.TelemetryRecord.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def latest_for_station(
    db: Session,
    station_id: str,
    *,
    data_source: TelemetrySource | None = None,
) -> models.TelemetryRecord | None:
    """Return the newest stored reading for a station/source boundary."""
    query = db.query(models.TelemetryRecord).filter(models.TelemetryRecord.station_id == station_id)
    if data_source is not None:
        query = query.filter(models.TelemetryRecord.data_source == data_source)
    return query.order_by(models.TelemetryRecord.timestamp.desc(), models.TelemetryRecord.id.desc()).first()
