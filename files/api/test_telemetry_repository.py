"""Focused tests for the telemetry repository boundary."""

import os
import tempfile
import unittest
from datetime import datetime, timezone


class TelemetryRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/repository_test.db"

        import database
        import models
        import telemetry_repository

        cls.database = database
        cls.models = models
        cls.repository = telemetry_repository
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        self.db.query(self.models.TelemetryRecord).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def reading(self, station_id: str, source: str, level: float, minute: int):
        return self.models.TelemetryCreate(
            station_id=station_id,
            station_name=f"{source} station",
            data_source=source,
            lat=7.8,
            lon=6.7667,
            timestamp=datetime(2026, 9, 23, 10, minute, tzinfo=timezone.utc),
            water_level_m=level,
            danger_level_m=2.0,
            threshold_type="prototype_demo",
            rainfall_mm_hr=None if source == "hardware" else 1.0,
            flow_rate_m3s=None if source == "hardware" else 2.0,
            battery_pct=None,
            signal="online",
        )

    def test_create_preserves_provenance_and_null_measurements(self):
        record = self.repository.create_record(self.db, self.reading("HW-01", "hardware", 1.25, 1))
        self.assertEqual(record.data_source, "hardware")
        self.assertEqual(record.threshold_type, "prototype_demo")
        self.assertIsNone(record.rainfall_mm_hr)
        self.assertIsNone(record.flow_rate_m3s)
        self.assertIsNone(record.battery_pct)

    def test_list_filters_source_and_orders_newest_first(self):
        self.repository.create_record(self.db, self.reading("SIM-01", "simulated", 0.8, 1))
        self.repository.create_record(self.db, self.reading("HW-01", "hardware", 1.0, 2))
        newest = self.repository.create_record(self.db, self.reading("HW-01", "hardware", 1.4, 3))

        hardware = self.repository.list_records(self.db, data_source="hardware")
        self.assertEqual([row.id for row in hardware], [newest.id, newest.id - 1])
        self.assertTrue(all(row.data_source == "hardware" for row in hardware))

    def test_latest_for_station_respects_source_boundary(self):
        self.repository.create_record(self.db, self.reading("STN-01", "simulated", 1.8, 1))
        hardware = self.repository.create_record(self.db, self.reading("STN-01", "hardware", 0.7, 2))

        latest = self.repository.latest_for_station(self.db, "STN-01", data_source="hardware")
        self.assertEqual(latest.id, hardware.id)
        self.assertEqual(latest.water_level_m, 0.7)


if __name__ == "__main__":
    unittest.main()
