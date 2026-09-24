"""Regression test: operator scenarios must remain visible after normalized read promotion."""

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient


class ScenarioNormalizedPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/scenario_normalized.db"
        os.environ["FLOOD_EWS_NEWS_PROVIDER"] = "off"
        import database, models, main
        from manage_operator import assign_role
        cls.database, cls.models, cls.main, cls.assign_role = database, models, main, assign_role
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
            "first_name": "Scenario", "last_name": "Operator",
            "email": "scenario.operator@example.com", "phone_number": "+2348000000001",
            "password": "ScenarioPass!42",
        })
        self.assertEqual(registration.status_code, 201, registration.text)
        with self.database.SessionLocal() as db:
            self.assign_role(db, "scenario.operator@example.com", "operator")
        login = self.client.post("/api/auth/login", json={
            "email": "scenario.operator@example.com", "password": "ScenarioPass!42"
        })
        self.assertEqual(login.status_code, 200, login.text)
        self.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        seed = {
            "station_id": "SCN-NORM", "station_name": "Scenario normalized station",
            "data_source": "hardware", "lat": 7.8, "lon": 6.7667,
            "timestamp": datetime(2026, 9, 24, 4, 30, tzinfo=timezone.utc).isoformat(),
            "water_level_m": 1.0, "danger_level_m": 2.0,
            "threshold_type": "prototype_demo", "rainfall_mm_hr": None,
            "flow_rate_m3s": None, "battery_pct": None, "signal": "online",
        }
        self.assertEqual(self.client.post("/api/telemetry", json=seed).status_code, 200)

    def test_scenario_dual_writes_and_is_visible_to_normalized_risk_status(self):
        with patch.object(self.main.random, "uniform", return_value=30.0):
            response = self.client.post(
                "/api/scenario/run",
                json={"station_id": "SCN-NORM", "scenario": "flood"},
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        db = self.database.SessionLocal()
        try:
            self.assertEqual(db.query(self.models.TelemetryRecord).count(), 2)
            simulated = db.query(self.models.TelemetryRecord).filter_by(data_source="simulated").one()
            station = db.query(self.models.Station).filter_by(station_code="SCN-NORM").one()
            simulated_source = db.query(self.models.DataSource).filter_by(code="SIMULATED").one()
            stage = db.query(self.models.Variable).filter_by(code="river_stage").one()
            normalized = db.query(self.models.Observation).filter_by(
                station_id=station.id, source_id=simulated_source.id, variable_id=stage.id
            ).one()
            self.assertEqual(normalized.value, simulated.water_level_m)
        finally:
            db.close()
        statuses = self.client.get("/api/risk-status?data_source=simulated").json()
        row = next(item for item in statuses if item["station_id"] == "SCN-NORM")
        self.assertEqual(row["data_source"], "simulated")
        self.assertEqual(row["water_level_m"], response.json()["water_level_m"])


if __name__ == "__main__":
    unittest.main()
