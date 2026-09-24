"""Read-only verifier for the physical Pico regression gate.

Run this only AFTER the Pico/COM4 serial bridge has posted a fresh hardware
reading to the local FloodWatch API. It does not talk to COM4 itself and cannot
prove sensor calibration; it verifies the downstream application/database path.

Example:
    python verify_physical_hardware_regression.py HW-01
"""

import sys
from datetime import datetime, timezone

import models
from database import SessionLocal


def fail(message: str) -> int:
    print(f"PHYSICAL_REGRESSION_FAIL: {message}")
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python verify_physical_hardware_regression.py <station_id>")
        return 2

    station_code = sys.argv[1].strip()
    if not station_code:
        return fail("station_id is blank")

    db = SessionLocal()
    try:
        station = db.query(models.Station).filter(models.Station.station_code == station_code).first()
        if station is None:
            return fail("normalized Station not found")

        source = db.query(models.DataSource).filter(models.DataSource.code == "LOCAL_SENSOR").first()
        stage = db.query(models.Variable).filter(models.Variable.code == "river_stage").first()
        if source is None or stage is None:
            return fail("normalized LOCAL_SENSOR/river_stage catalogue is missing")

        obs = (
            db.query(models.Observation)
            .filter(
                models.Observation.station_id == station.id,
                models.Observation.source_id == source.id,
                models.Observation.variable_id == stage.id,
            )
            .order_by(models.Observation.observed_at.desc(), models.Observation.id.desc())
            .first()
        )
        if obs is None:
            return fail("no normalized hardware river-stage Observation found")

        threshold = (
            db.query(models.Threshold)
            .filter(
                models.Threshold.station_id == station.id,
                models.Threshold.variable_id == stage.id,
                models.Threshold.active.is_(True),
            )
            .order_by(models.Threshold.id.desc())
            .first()
        )
        if threshold is None:
            return fail("no active normalized stage threshold found")

        legacy = (
            db.query(models.TelemetryRecord)
            .filter(
                models.TelemetryRecord.station_id == station_code,
                models.TelemetryRecord.data_source == "hardware",
            )
            .order_by(models.TelemetryRecord.timestamp.desc(), models.TelemetryRecord.id.desc())
            .first()
        )
        if legacy is None:
            return fail("dual-write rollback TelemetryRecord not found")
        if legacy.timestamp != obs.observed_at or legacy.water_level_m != obs.value:
            return fail("latest legacy and normalized hardware stage values do not match")
        if legacy.rainfall_mm_hr is not None or legacy.flow_rate_m3s is not None or legacy.battery_pct is not None:
            return fail("unmeasured hardware rainfall/flow/battery must remain null")

        age_seconds = (datetime.now(timezone.utc) - obs.observed_at).total_seconds()
        print("PHYSICAL_REGRESSION_EVIDENCE")
        print(f"station_id={station_code}")
        print(f"observed_at={obs.observed_at.isoformat()}")
        print(f"age_seconds={age_seconds:.1f}")
        print(f"water_level_m={obs.value}")
        print(f"threshold_type={threshold.threshold_type}")
        print(f"threshold_value={threshold.value}")
        print(f"quality_flag={obs.quality_flag}")
        print(f"signal_status={obs.signal_status}")
        print("optional_unmeasured_values=null")
        print("dual_write_parity=PASS")
        print("normalized_local_sensor_observation=PASS")
        print("PHYSICAL_REGRESSION_DB_PATH_PASS")
        print("NOTE: confirm the dashboard/risk-status display visually during the same run.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
