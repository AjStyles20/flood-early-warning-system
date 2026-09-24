"""Focused tests for telemetry application-service orchestration."""

import os
import tempfile
import unittest
from datetime import datetime, timezone


class TelemetryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/telemetry_service.db"
        import database, models, telemetry_service
        cls.database, cls.models, cls.service = database, models, telemetry_service
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
        self.alerts = []

    def tearDown(self): self.db.close()

    def reading(self, source="hardware", minute=1, level=1.6):
        return self.models.TelemetryCreate(
            station_id="SERVICE-01", station_name="Service station", data_source=source,
            lat=7.8, lon=6.7667,
            timestamp=datetime(2026, 9, 24, 4, minute, tzinfo=timezone.utc),
            water_level_m=level, danger_level_m=2.0, threshold_type="prototype_demo",
            rainfall_mm_hr=None if source == "hardware" else 2.0,
            flow_rate_m3s=None if source == "hardware" else 4.0,
            battery_pct=None, signal="online",
        )

    def persist_alert(self, db, station_id, station_name, source, risk, message):
        self.alerts.append((station_id, source, risk, message))

    def test_ingest_owns_dual_write_and_immediate_alert_orchestration(self):
        row = self.service.ingest(self.db, self.reading(), persist_alert_event=self.persist_alert)
        self.assertEqual(row.data_source, "hardware")
        self.assertEqual(self.db.query(self.models.TelemetryRecord).count(), 1)
        self.assertEqual(self.db.query(self.models.Observation).count(), 1)
        self.assertEqual(len(self.alerts), 1)
        self.assertEqual(self.alerts[0][2], "High")

    def test_risk_statuses_reads_normalized_current_state(self):
        self.service.ingest(self.db, self.reading(minute=1, level=0.8), persist_alert_event=self.persist_alert)
        self.service.ingest(self.db, self.reading(minute=2, level=1.6), persist_alert_event=self.persist_alert)
        statuses = self.service.risk_statuses(
            self.db, data_source="hardware", language="en",
            alert_channels={"web": "available", "email": "simulated", "sms": "simulated"},
            risk_rank={"Low": 0, "Moderate": 1, "High": 2, "Severe": 3},
        )
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].risk_level, "High")
        self.assertEqual(statuses[0].rate_of_rise_m, 0.8)
        self.assertIsNone(statuses[0].ml_probability)


if __name__ == "__main__":
    unittest.main()
