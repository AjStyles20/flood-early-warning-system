"""Focused tests for the current-state service boundary."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta


class CurrentStateServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/state.db"
        import current_state_service
        import database
        import models
        cls.service = current_state_service
        cls.database = database
        cls.models = models
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

    def record(self, level, minute, source="hardware", rainfall=None, flow=None):
        row = self.models.TelemetryRecord(
            station_id="STATE-01", station_name="State test", data_source=source,
            lat=7.8, lon=6.7, timestamp=datetime(2026, 9, 23, 20, minute),
            water_level_m=level, danger_level_m=2.0, threshold_type="prototype_demo",
            rainfall_mm_hr=rainfall, flow_rate_m3s=flow, battery_pct=None, signal="online")
        self.db.add(row); self.db.commit(); self.db.refresh(row); return row

    def test_rate_of_rise_uses_same_station_and_source(self):
        self.record(0.8, 1, "hardware")
        self.record(1.9, 2, "simulated", 2.0, 4.0)
        current = self.record(1.1, 3, "hardware")
        self.assertAlmostEqual(self.service.compute_rate_of_rise_m(current, self.db), 0.3)

    def test_hardware_status_is_threshold_based_and_has_no_ml_probability(self):
        current = self.record(1.6, 1, "hardware")
        status = self.service.status_from_record(current, self.db)
        self.assertEqual(status.risk_level, "High")
        self.assertAlmostEqual(status.risk_ratio, 0.8)
        self.assertIsNone(status.ml_probability)
        self.assertFalse(status.model_available)
        self.assertEqual(status.threshold_type, "prototype_demo")

    def test_invalid_threshold_is_rejected_by_current_state_engine(self):
        current = self.record(1.0, 1, "hardware")
        current.danger_level_m = 0.0
        with self.assertRaises(ValueError):
            self.service.assess_record(current, self.db)


if __name__ == "__main__":
    unittest.main()
