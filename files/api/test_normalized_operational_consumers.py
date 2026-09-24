"""Regression tests for operational consumers after normalized read promotion."""

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient


class NormalizedOperationalConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/normalized_consumers.db"
        os.environ["FLOOD_EWS_NEWS_PROVIDER"] = "off"
        import database, models, main
        from manage_operator import assign_role
        cls.database, cls.models, cls.main = database, models, main
        cls.assign_role = staticmethod(assign_role)
        models.Base.metadata.create_all(bind=database.engine)
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close(); cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        db = self.database.SessionLocal()
        for model in (self.models.AlertAuditLog, self.models.AlertEvent, self.models.ScenarioRun,
                      self.models.UserSession, self.models.User, self.models.Observation,
                      self.models.Threshold, self.models.Dataset, self.models.Station,
                      self.models.Variable, self.models.DataSource, self.models.TelemetryRecord):
            db.query(model).delete()
        db.commit(); db.close()
        registration = self.client.post("/api/auth/register", json={
            "first_name": "Normalized", "last_name": "Operator",
            "email": "normalized.operator@example.com", "phone_number": "+2348000000002",
            "password": "NormalizedPass!42",
        })
        self.assertEqual(registration.status_code, 201, registration.text)
        with self.database.SessionLocal() as db:
            self.assign_role(db, "normalized.operator@example.com", "operator")
        login = self.client.post("/api/auth/login", json={
            "email": "normalized.operator@example.com", "password": "NormalizedPass!42"
        })
        self.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        seed = {
            "station_id": "OPS-NORM", "station_name": "Normalized operational station",
            "data_source": "hardware", "lat": 7.8, "lon": 6.7667,
            "timestamp": datetime(2026, 9, 24, 4, 45, tzinfo=timezone.utc).isoformat(),
            "water_level_m": 1.6, "danger_level_m": 2.0,
            "threshold_type": "prototype_demo", "rainfall_mm_hr": None,
            "flow_rate_m3s": None, "battery_pct": None, "signal": "online",
        }
        self.assertEqual(self.client.post("/api/telemetry", json=seed).status_code, 200)

    def delete_legacy_telemetry(self):
        with self.database.SessionLocal() as db:
            db.query(self.models.TelemetryRecord).delete(); db.commit()

    def test_dispatch_uses_normalized_current_state_when_legacy_rows_are_absent(self):
        self.delete_legacy_telemetry()
        response = self.client.post(
            "/api/alerts/dispatch", json={"station_id": "OPS-NORM"}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["event"]["station_id"], "OPS-NORM")
        self.assertEqual(body["event"]["data_source"], "hardware")
        self.assertEqual(body["event"]["risk_level"], "High")

    def test_scenario_can_start_from_normalized_state_without_legacy_row(self):
        self.delete_legacy_telemetry()
        with patch.object(self.main.random, "uniform", return_value=30.0):
            response = self.client.post(
                "/api/scenario/run",
                json={"station_id": "OPS-NORM", "scenario": "flood"},
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["station_id"], "OPS-NORM")
        statuses = self.client.get("/api/risk-status?data_source=simulated").json()
        self.assertTrue(any(row["station_id"] == "OPS-NORM" for row in statuses))


if __name__ == "__main__":
    unittest.main()
