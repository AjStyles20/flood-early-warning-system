"""DB-4 parity tests: normalized reads must reproduce dual-written evidence."""

import os
import tempfile
import unittest
from datetime import datetime, timezone


class NormalizedReadParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/read_parity.db"
        import database, models, telemetry_repository, normalized_read_repository
        cls.database, cls.models = database, models
        cls.legacy, cls.normalized = telemetry_repository, normalized_read_repository
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

    def tearDown(self):
        self.db.close()

    def add(self, station, source, minute, level, rainfall=None, flow=None, battery=None):
        reading = self.models.TelemetryCreate(
            station_id=station, station_name=f"{station} name", data_source=source,
            lat=7.8, lon=6.7667,
            timestamp=datetime(2026, 9, 24, 0, minute, tzinfo=timezone.utc),
            water_level_m=level, danger_level_m=2.5, threshold_type="prototype_demo",
            rainfall_mm_hr=rainfall, flow_rate_m3s=flow, battery_pct=battery,
            signal="online",
        )
        return self.legacy.create_record(self.db, reading)

    @staticmethod
    def comparable(row):
        return (
            row.station_id, row.station_name, row.data_source,
            round(row.lat, 6), round(row.lon, 6), row.timestamp,
            row.water_level_m, row.rainfall_mm_hr, row.flow_rate_m3s,
            row.battery_pct, row.signal,
        )

    def test_latest_station_source_evidence_matches_legacy(self):
        self.add("STN-01", "simulated", 1, 0.8, 1.0, 2.0, 90)
        self.add("STN-01", "simulated", 2, 1.1, 1.5, 2.4, 88)
        self.add("STN-01", "hardware", 3, 0.7)
        self.add("STN-02", "hardware", 4, 1.4)

        legacy = sorted(map(self.comparable, self.legacy.latest_per_station_and_source(self.db)))
        normalized = sorted(map(self.comparable, self.normalized.latest_evidence(self.db)))
        self.assertEqual(normalized, legacy)

    def test_null_optional_measurements_remain_null_on_normalized_read(self):
        self.add("HW-01", "hardware", 5, 1.42)
        row = self.normalized.latest_evidence(self.db)[0]
        self.assertIsNone(row.rainfall_mm_hr)
        self.assertIsNone(row.flow_rate_m3s)
        self.assertIsNone(row.battery_pct)


if __name__ == "__main__":
    unittest.main()
