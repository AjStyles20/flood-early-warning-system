"""Regression proof for normalized /api/telemetry history reads."""

import os
import tempfile
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient


class NormalizedTelemetryHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/history.db"
        import database, models, main
        cls.database, cls.models = database, models
        models.Base.metadata.create_all(bind=database.engine)
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close(); cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        db = self.database.SessionLocal()
        for model in (self.models.AlertAuditLog, self.models.AlertEvent,
                      self.models.Observation, self.models.Threshold, self.models.Dataset,
                      self.models.Station, self.models.Variable, self.models.DataSource,
                      self.models.TelemetryRecord):
            db.query(model).delete()
        db.commit(); db.close()

    def post(self, station, source, minute, level, rainfall=None, flow=None):
        payload = {
            "station_id": station, "station_name": station, "data_source": source,
            "lat": 7.8, "lon": 6.7667,
            "timestamp": datetime(2026, 9, 24, 5, minute, tzinfo=timezone.utc).isoformat(),
            "water_level_m": level, "danger_level_m": 2.0,
            "threshold_type": "prototype_demo", "rainfall_mm_hr": rainfall,
            "flow_rate_m3s": flow, "battery_pct": None, "signal": "online",
        }
        response = self.client.post("/api/telemetry", json=payload)
        self.assertEqual(response.status_code, 200, response.text)

    def test_history_contract_survives_after_legacy_rows_are_deleted(self):
        self.post("HIST-01", "hardware", 1, 0.8)
        self.post("HIST-01", "hardware", 2, 1.2)
        self.post("HIST-02", "simulated", 3, 1.5, rainfall=3.0, flow=5.0)
        with self.database.SessionLocal() as db:
            db.query(self.models.TelemetryRecord).delete(); db.commit()

        response = self.client.get("/api/telemetry")
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()
        self.assertEqual(len(rows), 3)
        self.assertEqual([row["water_level_m"] for row in rows], [1.5, 1.2, 0.8])
        self.assertTrue(all(row["threshold_type"] == "prototype_demo" for row in rows))

        hardware = self.client.get("/api/telemetry?data_source=hardware").json()
        self.assertEqual(len(hardware), 2)
        self.assertTrue(all(row["data_source"] == "hardware" for row in hardware))

    def test_history_pagination_is_applied_to_normalized_stage_rows(self):
        self.post("PAGE-01", "hardware", 4, 0.4)
        self.post("PAGE-01", "hardware", 5, 0.5)
        self.post("PAGE-01", "hardware", 6, 0.6)
        rows = self.client.get("/api/telemetry?skip=1&limit=1").json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["water_level_m"], 0.5)


if __name__ == "__main__":
    unittest.main()
