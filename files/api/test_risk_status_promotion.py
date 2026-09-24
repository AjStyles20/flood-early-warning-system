"""Regression tests for DB-4 operational /api/risk-status promotion."""

import os
import tempfile
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient


class RiskStatusPromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/promotion.db"
        os.environ.setdefault("FLOOD_EWS_INGESTION_TOKEN", "promotion-test-token")
        import database, models, main
        cls.database, cls.models, cls.main = database, models, main
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
            "timestamp": datetime(2026, 9, 24, 2, minute, tzinfo=timezone.utc).isoformat(),
            "water_level_m": level, "danger_level_m": 2.0,
            "threshold_type": "prototype_demo", "rainfall_mm_hr": rainfall,
            "flow_rate_m3s": flow, "battery_pct": None, "signal": "online",
        }
        response = self.client.post(
            "/api/telemetry", json=payload,
            headers={"X-Ingestion-Token": "promotion-test-token"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_hardware_route_uses_normalized_state_and_preserves_trend(self):
        self.post("HW-PROMO", "hardware", 1, 0.8)
        self.post("HW-PROMO", "hardware", 2, 1.6)
        response = self.client.get("/api/risk-status?data_source=hardware")
        self.assertEqual(response.status_code, 200)
        row = response.json()[0]
        self.assertEqual(row["station_id"], "HW-PROMO")
        self.assertEqual(row["risk_level"], "High")
        self.assertEqual(row["risk_ratio"], 0.8)
        self.assertEqual(row["rate_of_rise_m"], 0.8)
        self.assertIsNone(row["ml_probability"])

    def test_hybrid_keeps_highest_risk_source_for_station(self):
        self.post("HYBRID-PROMO", "hardware", 3, 0.6)
        self.post("HYBRID-PROMO", "simulated", 4, 1.7, rainfall=2.0, flow=4.0)
        response = self.client.get("/api/risk-status?data_source=hybrid")
        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.json() if item["station_id"] == "HYBRID-PROMO")
        self.assertEqual(row["data_source"], "simulated")
        self.assertEqual(row["risk_level"], "High")

    def test_source_filter_does_not_leak_other_source(self):
        self.post("FILTER-PROMO", "hardware", 5, 1.0)
        self.post("SIM-ONLY", "simulated", 6, 1.0, rainfall=1.0, flow=2.0)
        response = self.client.get("/api/risk-status?data_source=hardware")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(row["data_source"] == "hardware" for row in response.json()))


if __name__ == "__main__":
    unittest.main()
