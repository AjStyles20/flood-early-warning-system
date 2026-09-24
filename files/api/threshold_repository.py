"""Repository for typed, time-applicable decision thresholds.

Thresholds are configuration/evidence metadata, never sensor observations.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models


def stage_threshold(
    db: Session,
    *,
    station: models.Station,
    variable: models.Variable,
    threshold_type: str,
    value: float,
    source_reference: str | None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> models.Threshold:
    """Stage one threshold, reusing an identical active compatibility row."""
    existing = (
        db.query(models.Threshold)
        .filter(
            models.Threshold.station_id == station.id,
            models.Threshold.variable_id == variable.id,
            models.Threshold.threshold_type == threshold_type,
            models.Threshold.value == value,
            models.Threshold.active.is_(True),
            models.Threshold.valid_from.is_(valid_from) if valid_from is None else models.Threshold.valid_from == valid_from,
            models.Threshold.valid_to.is_(valid_to) if valid_to is None else models.Threshold.valid_to == valid_to,
        )
        .order_by(models.Threshold.id.desc())
        .first()
    )
    if existing is not None:
        return existing
    row = models.Threshold(
        station_id=station.id,
        variable_id=variable.id,
        threshold_type=threshold_type,
        value=value,
        source_reference=source_reference,
        valid_from=valid_from,
        valid_to=valid_to,
        active=True,
    )
    db.add(row)
    return row


def applicable_threshold(
    db: Session,
    *,
    station_id: int,
    variable_id: int,
    observed_at: datetime,
    threshold_type: str | None = None,
) -> models.Threshold | None:
    """Return the latest active threshold whose validity contains observed_at."""
    query = db.query(models.Threshold).filter(
        models.Threshold.station_id == station_id,
        models.Threshold.variable_id == variable_id,
        models.Threshold.active.is_(True),
        or_(models.Threshold.valid_from.is_(None), models.Threshold.valid_from <= observed_at),
        or_(models.Threshold.valid_to.is_(None), models.Threshold.valid_to >= observed_at),
    )
    if threshold_type is not None:
        query = query.filter(models.Threshold.threshold_type == threshold_type)
    return query.order_by(models.Threshold.valid_from.desc(), models.Threshold.id.desc()).first()


def stage_compatibility_threshold(
    db: Session,
    *,
    station: models.Station,
    variable: models.Variable,
    threshold_type: str,
    value: float,
    source_reference: str | None,
    observed_at: datetime,
) -> models.Threshold:
    """Stage a compatibility threshold as a temporal change point.

    Reuse the open interval when its type/value are unchanged. When the value
    or type changes, close the prior open compatibility interval immediately
    before observed_at and open the replacement at observed_at.
    """
    current = (
        db.query(models.Threshold)
        .filter(
            models.Threshold.station_id == station.id,
            models.Threshold.variable_id == variable.id,
            models.Threshold.active.is_(True),
            models.Threshold.valid_to.is_(None),
            models.Threshold.source_reference.like("legacy_telemetry_compatibility:%"),
        )
        .order_by(models.Threshold.valid_from.desc(), models.Threshold.id.desc())
        .first()
    )
    if current is not None and current.threshold_type == threshold_type and current.value == value:
        return current

    if current is not None:
        current_start = current.valid_from
        comparison_time = observed_at
        # SQLite commonly returns timezone-naive DateTime values even when the
        # ingested compatibility timestamp was UTC-aware. Normalize only for
        # the ordering comparison; persisted timestamps keep the DB contract.
        if current_start is not None and current_start.tzinfo is None and comparison_time.tzinfo is not None:
            current_start = current_start.replace(tzinfo=timezone.utc)
        elif current_start is not None and current_start.tzinfo is not None and comparison_time.tzinfo is None:
            comparison_time = comparison_time.replace(tzinfo=timezone.utc)
        if current_start is not None and comparison_time <= current_start:
            raise ValueError("Compatibility threshold change points must be ingested in chronological order.")
        current.valid_to = observed_at - timedelta(microseconds=1)

    row = models.Threshold(
        station_id=station.id,
        variable_id=variable.id,
        threshold_type=threshold_type,
        value=value,
        source_reference=source_reference,
        valid_from=observed_at,
        valid_to=None,
        active=True,
    )
    db.add(row)
    return row
