"""MySQL DB-1 smoke/integration gate.

Run only against a disposable MySQL schema via FLOOD_EWS_DATABASE_URL.
It verifies schema creation, atomic dual-write and normalized risk-state reads.
"""

import os
import sys
from datetime import datetime, timezone


url = os.getenv("FLOOD_EWS_DATABASE_URL", "")
if not url.startswith("mysql"):
    raise SystemExit("DB-1 requires FLOOD_EWS_DATABASE_URL=mysql+pymysql://...")

import database
import models
import telemetry_repository
import normalized_read_repository
import normalized_current_state_service
import telemetry_service
import alert_service
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError


def main() -> int:
    models.Base.metadata.drop_all(bind=database.engine)
    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    try:
        reading = models.TelemetryCreate(
            station_id="MYSQL-DB1",
            station_name="MySQL integration station",
            data_source="hardware",
            lat=7.8,
            lon=6.7667,
            timestamp=datetime(2026, 9, 24, 3, 0, tzinfo=timezone.utc),
            water_level_m=1.6,
            danger_level_m=2.0,
            threshold_type="prototype_demo",
            rainfall_mm_hr=None,
            flow_rate_m3s=None,
            battery_pct=None,
            signal="online",
        )
        legacy = telemetry_repository.create_record(db, reading)
        evidence = normalized_read_repository.latest_per_station(db, data_source="hardware")
        assert len(evidence) == 1
        assert evidence[0].station_id == legacy.station_id
        assert evidence[0].water_level_m == legacy.water_level_m
        assert evidence[0].danger_level_m == legacy.danger_level_m
        status = normalized_current_state_service.status_from_evidence(evidence[0], db)
        assert status.risk_level == "High"
        assert status.risk_ratio == 0.8
        assert status.ml_probability is None
        assert db.query(models.TelemetryRecord).count() == 1
        assert db.query(models.Observation).count() == 1

        # Exercise MySQL SELECT ... FOR UPDATE around the provider decision;
        # a second high reading must reuse the persisted dispatch outcome.
        for minute in (1, 2):
            next_reading = reading.model_copy(update={
                "timestamp": datetime(2026, 9, 24, 3, minute, tzinfo=timezone.utc),
            })
            with patch.object(telemetry_service.notifications, "notify", return_value={
                "web": "available", "email": "sent", "sms": "not_configured",
            }) as notify:
                telemetry_service.ingest(db, next_reading, persist_alert_event=alert_service.persist_event)
                assert notify.call_count == (1 if minute == 1 else 0)
        assert db.query(models.AlertEvent).count() == 1
        assert db.query(models.Threshold).count() == 1

        # DB-level evidence identity must remain unique even if a caller
        # bypasses the shared application write policy.
        stage = db.query(models.Variable).filter(models.Variable.code == "river_stage").one()
        source = db.query(models.DataSource).filter(models.DataSource.code == "LOCAL_SENSOR").one()
        station = db.query(models.Station).filter(models.Station.station_code == "MYSQL-DB1").one()
        db.add(models.Observation(
            station_id=station.id,
            variable_id=stage.id,
            source_id=source.id,
            observed_at=reading.timestamp,
            value=reading.water_level_m,
        ))
        try:
            db.commit()
            raise AssertionError("MySQL accepted duplicate normalized observation identity")
        except IntegrityError:
            db.rollback()
        assert db.query(models.Observation).count() == 3
        print("MYSQL_DB1_PASS")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
