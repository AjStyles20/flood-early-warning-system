"""Duplicate/correction policy for normalized observations.

A repeated station/variable/source/timestamp is not silently accepted. Exact
replays are idempotent; conflicting values require an explicit future
correction workflow rather than guessing which measurement is authoritative.
"""

from sqlalchemy.orm import Session

import models


class ObservationConflictError(ValueError):
    pass


def stage_observation(
    db: Session,
    *,
    station: models.Station,
    variable: models.Variable,
    source: models.DataSource,
    observed_at,
    value: float,
    dataset: models.Dataset | None = None,
    quality_flag: str | None = None,
    signal_status: str | None = None,
) -> models.Observation:
    existing = (
        db.query(models.Observation)
        .filter(
            models.Observation.station_id == station.id,
            models.Observation.variable_id == variable.id,
            models.Observation.source_id == source.id,
            models.Observation.observed_at == observed_at,
        )
        .order_by(models.Observation.id.desc())
        .first()
    )
    if existing is not None:
        same_dataset = existing.dataset_id == (dataset.id if dataset else None)
        if (
            existing.value == value
            and existing.quality_flag == quality_flag
            and existing.signal_status == signal_status
            and same_dataset
        ):
            return existing
        raise ObservationConflictError(
            "Conflicting observation already exists for station/variable/source/timestamp; "
            "use an explicit correction/revision workflow rather than overwriting evidence."
        )

    row = models.Observation(
        station_id=station.id,
        variable_id=variable.id,
        source_id=source.id,
        dataset_id=dataset.id if dataset else None,
        observed_at=observed_at,
        value=value,
        quality_flag=quality_flag,
        signal_status=signal_status,
    )
    db.add(row)
    return row
