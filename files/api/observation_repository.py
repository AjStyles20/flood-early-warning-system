"""Repository helpers for the normalized observation/provenance model."""

from sqlalchemy.orm import Session

import models
from observation_catalogue import SOURCE_CATALOGUE, VARIABLE_CATALOGUE


def seed_catalogues(db: Session, *, commit: bool = True) -> None:
    """Idempotently seed controlled vocabulary, optionally in caller transaction."""
    for item in VARIABLE_CATALOGUE:
        row = db.query(models.Variable).filter(models.Variable.code == item["code"]).first()
        if row is None:
            db.add(models.Variable(**item))
    for item in SOURCE_CATALOGUE:
        row = db.query(models.DataSource).filter(models.DataSource.code == item["code"]).first()
        if row is None:
            db.add(models.DataSource(**item))
    if commit:
        db.commit()
    else:
        db.flush()


def get_variable(db: Session, code: str) -> models.Variable | None:
    return db.query(models.Variable).filter(models.Variable.code == code).first()


def get_source(db: Session, code: str) -> models.DataSource | None:
    return db.query(models.DataSource).filter(models.DataSource.code == code).first()


def create_observation(
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
    """Persist one atomic observation without inventing absent variables."""
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
    db.commit()
    db.refresh(row)
    return row


def observations_for(
    db: Session,
    *,
    station_id: int,
    variable_id: int,
    source_id: int | None = None,
    limit: int = 100,
) -> list[models.Observation]:
    query = db.query(models.Observation).filter(
        models.Observation.station_id == station_id,
        models.Observation.variable_id == variable_id,
    )
    if source_id is not None:
        query = query.filter(models.Observation.source_id == source_id)
    return query.order_by(models.Observation.observed_at.desc(), models.Observation.id.desc()).limit(limit).all()
