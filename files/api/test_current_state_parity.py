"""DB-4 full current-state parity tests."""

import os
import tempfile
import unittest
from datetime import datetime, timezone


class CurrentStateParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/state_parity.db"
        import database, models, telemetry_repository
        import normalized_read_repository, current_state_service, normalized_current_state_service
        cls.database, cls.models, cls.telemetry = database, models, telemetry_repository
        cls.normalized_reads = normalized_read_repository
        cls.legacy_state, cls.normalized_state = current_state_service, normalized_current_state_service
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        for model in (self.models.Observation, self.models.Threshold, self.models.Dataset,
                      self.models.Station, self.models.Variable, self.models.DataSource,
                      self.models.TelemetryRecord):
            self.db.query(model).delete()
        self.db.commit()

    def tearDown(self): self.db.close()

    def add(self, source, minute, level, rainfall=None, flow=None, battery=None):
        reading = self.models.TelemetryCreate(
            station_id="PARITY-01", station_name="Parity station", data_source=source,
            lat=7.8, lon=6.7667,
            timestamp=datetime(2026, 9, 24, 1, minute, tzinfo=timezone.utc),
            water_level_m=level, danger_level_m=2.0, threshold_type="prototype_demo",
            rainfall_mm_hr=rainfall, flow_rate_m3s=flow, battery_pct=battery, signal="online",
        )
        return self.telemetry.create_record(self.db, reading)

    @staticmethod
    def comparable(status):
        return (
            status.station_id, status.station_name, status.data_source,
            round(status.lat, 6), round(status.lon, 6), status.timestamp,
            status.water_level_m, status.danger_level_m, status.threshold_type,
            status.rainfall_mm_hr, status.flow_rate_m3s, status.rate_of_rise_m,
            status.battery_pct, status.signal, status.risk_level, status.risk_ratio,
            status.ml_probability, status.model_available, status.message,
            status.color, status.language, status.alert_channels,
        )

    def normalized_for(self, source):
        return next(x for x in self.normalized_reads.latest_evidence(self.db) if x.data_source == source)

    def test_hardware_current_state_matches_legacy_including_trend(self):
        self.add("hardware", 1, 0.8)
        legacy = self.add("hardware", 2, 1.6)
        legacy_status = self.legacy_state.status_from_record(legacy, self.db)
        normalized_status = self.normalized_state.status_from_evidence(self.normalized_for("hardware"), self.db)
        self.assertEqual(self.comparable(normalized_status), self.comparable(legacy_status))
        self.assertEqual(normalized_status.rate_of_rise_m, 0.8)
        self.assertIsNone(normalized_status.ml_probability)

    def test_simulator_current_state_matches_legacy(self):
        self.add("simulated", 3, 0.9, rainfall=2.0, flow=4.0, battery=90)
        legacy = self.add("simulated", 4, 1.2, rainfall=3.0, flow=5.0, battery=88)
        legacy_status = self.legacy_state.status_from_record(legacy, self.db)
        normalized_status = self.normalized_state.status_from_evidence(self.normalized_for("simulated"), self.db)
        self.assertEqual(self.comparable(normalized_status), self.comparable(legacy_status))


if __name__ == "__main__":
    unittest.main()
